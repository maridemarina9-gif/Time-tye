from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import pydeck as pdk
except ImportError:
    pdk = None

try:
    import streamlit as st
except ImportError:
    st = None

from tracking.metrics import format_pace

# Carto basemap styles natively supported by PyDeck
TIME_TYE_MAP_STYLE = "carto-voyager"


@dataclass
class _FallbackViewState:
    latitude: float
    longitude: float
    zoom: int
    pitch: int = 0


def _create_view_state(latitude: float, longitude: float, zoom: int, pitch: int = 0):
    if pdk is not None:
        return pdk.ViewState(latitude=latitude, longitude=longitude, zoom=zoom, pitch=pitch)
    return _FallbackViewState(latitude=latitude, longitude=longitude, zoom=zoom, pitch=pitch)


def _deck(*, initial_view_state, layers: list, tooltip: dict | None, height: int) -> None:
    """Render a map with the TIME TYE Carto basemap."""
    if st is None or pdk is None:
        return
    deck = pdk.Deck(
        map_style=TIME_TYE_MAP_STYLE,
        initial_view_state=initial_view_state,
        layers=layers,
        tooltip=tooltip,
    )
    st.pydeck_chart(deck, use_container_width=True, height=height)


def _safe_public_point(latitude: float, longitude: float, precision: str) -> tuple[float, float]:
    if precision == "approximate":
        return round(latitude, 3), round(longitude, 3)
    return latitude, longitude


def _calculate_view_state(rows: list[dict], default_zoom: int = 15):
    if not rows:
        return _create_view_state(latitude=0, longitude=0, zoom=default_zoom, pitch=0)
    if len(rows) == 1:
        return _create_view_state(latitude=rows[0]["latitude"], longitude=rows[0]["longitude"], zoom=16, pitch=0)

    lats = [r["latitude"] for r in rows]
    lons = [r["longitude"] for r in rows]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2

    max_diff = max(max_lat - min_lat, max_lon - min_lon)
    if max_diff < 0.003:
        zoom = 16
    elif max_diff < 0.01:
        zoom = 15
    elif max_diff < 0.03:
        zoom = 14
    elif max_diff < 0.08:
        zoom = 13
    elif max_diff < 0.2:
        zoom = 12
    elif max_diff < 0.5:
        zoom = 11
    else:
        zoom = 9

    return _create_view_state(latitude=center_lat, longitude=center_lon, zoom=zoom, pitch=0)


def render_route_map(points: Iterable[dict], precision: str = "exact", height: int = 360) -> None:
    rows = []
    for point in points:
        lat = point.get("latitude")
        lon = point.get("longitude")
        if lat is None or lon is None:
            continue
        try:
            flat, flon = float(lat), float(lon)
        except (ValueError, TypeError):
            continue
        safe_lat, safe_lon = _safe_public_point(flat, flon, precision)
        rows.append({"latitude": safe_lat, "longitude": safe_lon})

    if not rows:
        if st is not None:
            st.info("O mapa aparecerá assim que o GPS registrar um ponto válido.")
        return

    if pdk is None or st is None:
        return

    # If only 1 point is available, render a single marker (PathLayer requires >= 2 vertices)
    if len(rows) == 1:
        single_df = pd.DataFrame(rows) if pd is not None else rows
        view_state = _create_view_state(latitude=rows[0]["latitude"], longitude=rows[0]["longitude"], zoom=16, pitch=0)
        layers = [
            pdk.Layer(
                "ScatterplotLayer",
                data=single_df,
                get_position="[longitude, latitude]",
                get_fill_color=[22, 163, 74],
                get_radius=20,
                radius_min_pixels=9,
            ),
        ]
        _deck(
            initial_view_state=view_state,
            layers=layers,
            tooltip={"text": "Ponto de partida / Posição atual"},
            height=height,
        )
        return

    path = [[row["longitude"], row["latitude"]] for row in rows]
    route_df = pd.DataFrame(rows) if pd is not None else rows
    start_df = pd.DataFrame([rows[0]]) if pd is not None else [rows[0]]
    end_df = pd.DataFrame([rows[-1]]) if pd is not None else [rows[-1]]

    view_state = _calculate_view_state(rows, default_zoom=15)
    layers = [
        pdk.Layer(
            "PathLayer",
            data=[{"path": path}],
            get_path="path",
            get_color=[22, 163, 74],
            width_min_pixels=5,
            get_width=5,
        ),
        pdk.Layer(
            "ScatterplotLayer",
            data=route_df,
            get_position="[longitude, latitude]",
            get_fill_color=[15, 118, 110, 160],
            get_radius=8,
            radius_min_pixels=3,
        ),
        pdk.Layer(
            "ScatterplotLayer",
            data=start_df,
            get_position="[longitude, latitude]",
            get_fill_color=[22, 163, 74],
            get_radius=24,
            radius_min_pixels=8,
        ),
        pdk.Layer(
            "ScatterplotLayer",
            data=end_df,
            get_position="[longitude, latitude]",
            get_fill_color=[220, 38, 38],
            get_radius=24,
            radius_min_pixels=8,
        ),
    ]

    _deck(
        initial_view_state=view_state,
        layers=layers,
        tooltip={"text": "Percurso"},
        height=height,
    )


def render_live_map(locations: list[dict]) -> None:
    if not locations:
        if st is not None:
            st.info("Não há corredores públicos ativos no momento.")
        return

    rows = []
    for location in locations:
        lat = location.get("latitude")
        lon = location.get("longitude")
        if lat is None or lon is None:
            continue
        try:
            flat, flon = float(lat), float(lon)
        except (ValueError, TypeError):
            continue
        precision = location.get("location_precision", "exact")
        safe_lat, safe_lon = _safe_public_point(flat, flon, precision)

        dist = float(location.get("distance", 0) or 0)
        pace = float(location.get("pace", 0) or 0)
        speed = location.get("speed")

        rows.append({
            **location,
            "latitude": safe_lat,
            "longitude": safe_lon,
            "formatted_distance": f"{dist:.2f} km",
            "formatted_pace": format_pace(pace),
            "formatted_speed": f"{float(speed):.1f} km/h" if speed is not None else "—",
        })

    if not rows:
        if st is not None:
            st.info("Não há corredores públicos com localização válida no momento.")
        return

    if pdk is None or st is None:
        return

    data = pd.DataFrame(rows) if pd is not None else rows
    view_state = _calculate_view_state(rows, default_zoom=13)
    layers = [
        pdk.Layer(
            "ScatterplotLayer",
            data=data,
            get_position="[longitude, latitude]",
            get_fill_color=[34, 197, 94],
            get_radius=100,
            radius_min_pixels=10,
            pickable=True,
        )
    ]

    _deck(
        initial_view_state=view_state,
        layers=layers,
        tooltip={"html": "<b>{name}</b><br/>Status: {status}<br/>Distância: {formatted_distance}<br/>Ritmo: {formatted_pace}"},
        height=460,
    )