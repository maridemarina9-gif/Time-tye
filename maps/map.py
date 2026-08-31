from __future__ import annotations

from typing import Iterable

import pandas as pd
import pydeck as pdk
import streamlit as st


TIME_TYE_MAP_STYLE = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json"


def _deck(*, initial_view_state: pdk.ViewState, layers: list[pdk.Layer], tooltip: dict, height: int) -> None:
    """Render a map with the TIME TYE branded Carto basemap."""
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


def render_route_map(points: Iterable[dict], precision: str = "exact", height: int = 360) -> None:
    rows = []
    for point in points:
        lat, lon = _safe_public_point(float(point["latitude"]), float(point["longitude"]), precision)
        rows.append({"latitude": lat, "longitude": lon})
    if not rows:
        st.info("O mapa aparecerá assim que o GPS registrar um ponto válido.")
        return
    path = [[row["longitude"], row["latitude"]] for row in rows]
    center = rows[-1]
    _deck(
        initial_view_state=pdk.ViewState(latitude=center["latitude"], longitude=center["longitude"], zoom=14, pitch=0),
        layers=[
            pdk.Layer("PathLayer", data=[{"path": path}], get_path="path", get_color=[22, 163, 74], width_min_pixels=5),
            pdk.Layer("ScatterplotLayer", data=rows, get_position="[longitude, latitude]", get_fill_color=[15, 118, 110], get_radius=10, radius_min_pixels=4),
            pdk.Layer("ScatterplotLayer", data=[rows[0]], get_position="[longitude, latitude]", get_fill_color=[22, 163, 74], get_radius=24, radius_min_pixels=8),
            pdk.Layer("ScatterplotLayer", data=[rows[-1]], get_position="[longitude, latitude]", get_fill_color=[220, 38, 38], get_radius=24, radius_min_pixels=8),
        ],
        tooltip={"text": "Percurso"},
        height=height,
    )


def render_live_map(locations: list[dict]) -> None:
    if not locations:
        st.info("Não há corredores públicos ativos no momento.")
        return
    rows = []
    for location in locations:
        lat, lon = _safe_public_point(location["latitude"], location["longitude"], location.get("location_precision", "exact"))
        rows.append({**location, "latitude": lat, "longitude": lon})
    data = pd.DataFrame(rows)
    center = data.iloc[0]
    _deck(
        initial_view_state=pdk.ViewState(latitude=float(center["latitude"]), longitude=float(center["longitude"]), zoom=12),
        layers=[pdk.Layer("ScatterplotLayer", data=data, get_position="[longitude, latitude]", get_fill_color=[34, 197, 94], get_radius=100, radius_min_pixels=10, pickable=True)],
        tooltip={"html": "<b>{name}</b><br/>Status: {status}<br/>{distance:.2f} km"},
        height=460,
    )