from __future__ import annotations

from statistics import mean
from typing import Any

from tracking.distance import GPSPoint, filter_gps_points, route_distance_km


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
    return {
        "distance_km": distance_km,
        "duration_seconds": duration_seconds,
        "average_pace": average_pace,
        "average_speed": average_speed,
        "max_speed": max_speed,
        "calories": calories,
        "elevation_gain": elevation_gain,
        "points": clean_points,
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
