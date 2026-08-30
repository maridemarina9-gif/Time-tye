from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st


GPS_JS = r'''
const GPS_KEY = "__time_tye_gps_watch__";

export default function(component) {
  const { data, setStateValue } = component;
  const active = Boolean(data?.active);
  const intervalMs = Number(data?.interval_ms) || 5000;

  if (!window[GPS_KEY]) {
    window[GPS_KEY] = {
      watchId: null,
      lastSent: 0,
      active: false,
    };
  }

  const gps = window[GPS_KEY];

  function publishLocation(position) {
    if (!gps.active) return;
    const now = Date.now();
    if (now - gps.lastSent < intervalMs) return;
    gps.lastSent = now;

    const c = position.coords;
    setStateValue("location", {
      latitude: c.latitude,
      longitude: c.longitude,
      altitude: c.altitude,
      altitudeAccuracy: c.altitudeAccuracy,
      accuracy: c.accuracy,
      heading: c.heading,
      speed: c.speed,
      timestamp_ms: position.timestamp || now,
    });
    setStateValue("error", null);
  }

  function publishError(error) {
    if (!gps.active) return;
    setStateValue("error", {
      code: error.code,
      message: error.message || "Não foi possível obter a localização.",
    });
  }

  function stop() {
    gps.active = false;
    if (gps.watchId !== null && navigator.geolocation) {
      navigator.geolocation.clearWatch(gps.watchId);
    }
    gps.watchId = null;
  }

  function start() {
    if (!navigator.geolocation) {
      publishError({ code: 0, message: "Este navegador não oferece geolocalização." });
      return;
    }
    if (gps.watchId !== null) return;

    gps.active = true;
    gps.watchId = navigator.geolocation.watchPosition(
      publishLocation,
      publishError,
      {
        enableHighAccuracy: true,
        maximumAge: 2000,
        timeout: 15000,
      }
    );
  }

  if (active) {
    start();
  } else if (gps.watchId !== null) {
    stop();
  }

  return () => {
    // Stop the browser watcher when the component is actually unmounted
    // (for example, when leaving the running screen).
    if (gps.watchId !== null) {
      navigator.geolocation.clearWatch(gps.watchId);
      gps.watchId = null;
    }
    gps.active = false;
  };
}
'''

_gps_component = st.components.v2.component(
    "time_tye_browser_gps_v2",
    html='<div aria-hidden="true" style="height:1px;width:1px;overflow:hidden"></div>',
    js=GPS_JS,
    isolate_styles=False,
)


def get_browser_location(key: str, interval_ms: int = 5000, active: bool = True) -> dict:
    result = _gps_component(
        key=key,
        data={"active": active, "interval_ms": interval_ms},
        default={"location": None, "error": None},
        on_location_change=lambda: None,
        on_error_change=lambda: None,
    )

    location = getattr(result, "location", None)
    error = getattr(result, "error", None)

    if not location:
        return {"available": False, "error": error}

    return {
        "available": True,
        "timestamp": datetime.fromtimestamp(
            float(location.get("timestamp_ms", 0)) / 1000,
            tz=timezone.utc,
        ).isoformat(),
        "latitude": float(location["latitude"]),
        "longitude": float(location["longitude"]),
        "altitude": float(location["altitude"]) if location.get("altitude") is not None else None,
        "speed": float(location["speed"]) if location.get("speed") is not None else None,
        "accuracy": float(location["accuracy"]) if location.get("accuracy") is not None else None,
    }
