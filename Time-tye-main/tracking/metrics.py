from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import Any

from tracking.distance import GPSPoint, filter_gps_points, haversine_km, route_distance_km


def _parse_ts(ts_str: str) -> float | None:
    if not ts_str:
        return None
    try:
        dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return None


def calculate_splits(points: list[GPSPoint]) -> list[dict[str, Any]]:
    """Calculate per-kilometer split times and pace from recorded GPS points."""
    clean = filter_gps_points(points)
    if len(clean) < 2:
        return []

    splits: list[dict[str, Any]] = []
    km_target = 1.0
    accumulated_km = 0.0
    split_start_ts = _parse_ts(clean[0].get("timestamp", ""))
    split_start_idx = 0
    current_km_index = 1

    for i in range(len(clean) - 1):
        p1 = clean[i]
        p2 = clean[i + 1]
        dist = haversine_km(p1["latitude"], p1["longitude"], p2["latitude"], p2["longitude"])
        accumulated_km += dist

        if accumulated_km >= km_target:
            t1 = split_start_ts
            t2 = _parse_ts(p2.get("timestamp", ""))
            if t1 is not None and t2 is not None and t2 >= t1:
                split_duration = max(1, int(t2 - t1))
            else:
                split_duration = 0

            split_pace = (split_duration / 60) / 1.0 if split_duration else 0
            splits.append({
                "km": current_km_index,
                "distance_km": 1.0,
                "duration_seconds": split_duration,
                "pace": split_pace,
                "formatted_pace": format_pace(split_pace),
                "formatted_time": format_duration(split_duration),
                "is_partial": False,
            })
            accumulated_km -= 1.0
            split_start_ts = t2
            split_start_idx = i + 1
            current_km_index += 1

    # Remaining partial km (if >= 0.05 km)
    if accumulated_km >= 0.05:
        last_ts = _parse_ts(clean[-1].get("timestamp", ""))
        if split_start_ts is not None and last_ts is not None and last_ts >= split_start_ts:
            partial_duration = max(1, int(last_ts - split_start_ts))
        else:
            partial_duration = 0

        partial_pace = (partial_duration / 60) / accumulated_km if (accumulated_km and partial_duration) else 0
        splits.append({
            "km": current_km_index,
            "distance_km": round(accumulated_km, 2),
            "duration_seconds": partial_duration,
            "pace": partial_pace,
            "formatted_pace": format_pace(partial_pace),
            "formatted_time": format_duration(partial_duration),
            "is_partial": True,
        })

    return splits


def calculate_metrics(points: list[GPSPoint], duration_seconds: int, weight_kg: float = 70) -> dict[str, Any]:
    clean_points = filter_gps_points(points)
    distance_km = route_distance_km(clean_points)
    speeds = [float(point["speed"]) * 3.6 for point in clean_points if point.get("speed") is not None and point["speed"] >= 0]
    altitudes = [float(point["altitude"]) for point in clean_points if point.get("altitude") is not None]
    elevation_gain = sum(max(0, current - previous) for previous, current in zip(altitudes, altitudes[1:]))
    hours = duration_seconds / 3600 if duration_seconds else 0
    average_speed = distance_km / hours if hours else (mean(speeds) if speeds else 0)
    average_pace = duration_seconds / 60 / distance_km if distance_km else 0
    max_speed = max(speeds, default=0)
    calories = distance_km * weight_kg * 1.036
    splits = calculate_splits(clean_points)
    return {
        "distance_km": distance_km,
        "duration_seconds": duration_seconds,
        "average_pace": average_pace,
        "average_speed": average_speed,
        "max_speed": max_speed,
        "calories": calories,
        "elevation_gain": elevation_gain,
        "points": clean_points,
        "splits": splits,
    }


def format_duration(seconds: int | float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_pace(minutes_per_km: float) -> str:
    if not minutes_per_km:
        return "—"
    minutes = int(minutes_per_km)
    seconds = round((minutes_per_km - minutes) * 60)
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d}/km"
