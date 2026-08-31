from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Iterable


def generate_gpx(
    points: Iterable[dict],
    track_name: str = "TIME TYE Corrida",
    description: str = "Treino gravado pelo aplicativo TIME TYE",
    creator: str = "TIME TYE Running Tracker",
) -> str:
    """Generate a standard GPX 1.1 XML document from GPS points."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    safe_name = html.escape(track_name)
    safe_desc = html.escape(description)
    safe_creator = html.escape(creator)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1"',
        f'     creator="{safe_creator}"',
        '     xmlns="http://www.topografix.com/GPX/1/1"',
        '     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '     xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">',
        '  <metadata>',
        f'    <name>{safe_name}</name>',
        f'    <desc>{safe_desc}</desc>',
        f'    <time>{now_str}</time>',
        '  </metadata>',
        '  <trk>',
        f'    <name>{safe_name}</name>',
        '    <trkseg>',
    ]

    for pt in points:
        lat = pt.get("latitude")
        lon = pt.get("longitude")
        if lat is None or lon is None:
            continue
        try:
            flat = float(lat)
            flon = float(lon)
        except (ValueError, TypeError):
            continue

        ele_tag = ""
        alt = pt.get("altitude")
        if alt is not None:
            try:
                ele_tag = f"        <ele>{float(alt):.1f}</ele>\n"
            except (ValueError, TypeError):
                pass

        time_tag = ""
        ts = pt.get("timestamp")
        if ts:
            ts_str = str(ts).replace("+00:00", "Z")
            if not ts_str.endswith("Z") and "T" in ts_str:
                ts_str += "Z"
            time_tag = f"        <time>{html.escape(ts_str)}</time>\n"

        speed_tag = ""
        spd = pt.get("speed")
        if spd is not None:
            try:
                speed_tag = f"        <speed>{float(spd):.2f}</speed>\n"
            except (ValueError, TypeError):
                pass

        lines.append(f'      <trkpt lat="{flat:.7f}" lon="{flon:.7f}">')
        if ele_tag:
            lines.append(ele_tag.rstrip())
        if time_tag:
            lines.append(time_tag.rstrip())
        if speed_tag:
            lines.append(speed_tag.rstrip())
        lines.append('      </trkpt>')

    lines.append('    </trkseg>')
    lines.append('  </trk>')
    lines.append('</gpx>')

    return '\n'.join(lines)
