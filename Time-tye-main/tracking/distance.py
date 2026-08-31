from __future__ import annotations

import math
from typing import TypedDict


class GPSPoint(TypedDict, total=False):
    timestamp: str
    latitude: float
    longitude: float
    altitude: float | None
    speed: float | None
    accuracy: float | None


EARTH_RADIUS_KM = 6371.0088


def haversine_km(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    lat_a, lat_b = math.radians(latitude_a), math.radians(latitude_b)
    delta_lat = math.radians(latitude_b - latitude_a)
    delta_lon = math.radians(longitude_b - longitude_a)
    value = math.sin(delta_lat / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(value))


def valid_coordinate(latitude: float | None, longitude: float | None) -> bool:
    return latitude is not None and longitude is not None and -90 <= latitude <= 90 and -180 <= longitude <= 180


def filter_gps_points(points: list[GPSPoint], max_speed_kmh: float = 45) -> list[GPSPoint]:
    filtered: list[GPSPoint] = []
    for point in points:
        latitude = point.get("latitude")
        longitude = point.get("longitude")
        accuracy = point.get("accuracy")
        if not valid_coordinate(latitude, longitude):
            continue
        if accuracy is not None and accuracy > 100:
            continue
        if filtered:
            previous = filtered[-1]
            delta_km = haversine_km(previous["latitude"], previous["longitude"], latitude, longitude)
            speed = point.get("speed")
            if speed is not None and speed * 3.6 > max_speed_kmh:
                continue
            if delta_km > 1.0:
                continue
            if delta_km == 0 and point.get("timestamp") == previous.get("timestamp"):
                continue
        filtered.append(point)
    return filtered


def route_distance_km(points: list[GPSPoint]) -> float:
    return sum(
        haversine_km(a["latitude"], a["longitude"], b["latitude"], b["longitude"])
        for a, b in zip(points, points[1:])
    )