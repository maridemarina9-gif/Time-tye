from __future__ import annotations

from database.database import get_connection
from maps.map import render_live_map


def get_public_live_locations() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """SELECT live_locations.*, users.name, users.username,
                      user_settings.location_precision
               FROM live_locations
               JOIN users ON users.id = live_locations.user_id
               JOIN user_settings ON user_settings.user_id = users.id
               WHERE live_locations.visibility = 'public'
                 AND live_locations.status = 'running'
                 AND datetime(live_locations.last_update) >= datetime('now', '-5 minutes')
               ORDER BY live_locations.last_update DESC"""
        ).fetchall()
    return [dict(row) for row in rows]


def show_live_map() -> list[dict]:
    locations = get_public_live_locations()
    render_live_map(locations)
    return locations