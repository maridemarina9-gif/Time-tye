from __future__ import annotations

from tracking.gps_component import get_browser_location


def get_current_location(key: str = "time_tye_gps", interval_ms: int = 5000) -> dict:
    raw = get_browser_location(key=key, interval_ms=interval_ms, active=True)

    if raw.get("available"):
        return raw

    error = raw.get("error") or {}
    code = error.get("code")
    if code == 1:
        message = "Localização bloqueada. No Chrome, permita a localização para este site e recarregue a página."
    elif code == 2:
        message = "O aparelho não conseguiu determinar sua localização. Ative o GPS/localização do celular."
    elif code == 3:
        message = "O GPS demorou para responder. Deixe a localização do celular ligada e aguarde alguns segundos."
    elif error:
        message = f"GPS: {error.get('message', 'erro desconhecido')}."
    else:
        message = "Iniciando GPS automaticamente... permita a localização quando o navegador solicitar."

    return {"available": False, "message": message, "error": error}
