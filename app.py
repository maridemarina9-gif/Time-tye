from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from auth.authentication import (
    authenticate,
    create_reset_token,
    create_session,
    get_user,
    get_user_by_session,
    register_user,
    revoke_session,
    reset_password,
    validate_registration,
)
from components.styles import apply_styles, metric_big, stat_card
from database.database import get_connection
from database.migrations import run_migrations
from maps.live_map import get_public_live_locations
from maps.map import render_live_map, render_route_map
from tracking.distance import filter_gps_points
from tracking.gps import get_current_location
from tracking.metrics import calculate_metrics, format_duration, format_pace


APP_DIR = Path(__file__).resolve().parent


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def get_settings(user_id: int) -> dict:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else {"location_sharing": 0, "location_precision": "exact", "profile_visibility": "private"}


def update_settings(user_id: int, location_sharing: bool, location_precision: str, profile_visibility: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """UPDATE user_settings
               SET location_sharing = ?, location_precision = ?, profile_visibility = ?, updated_at = CURRENT_TIMESTAMP
               WHERE user_id = ?""",
            (int(location_sharing), location_precision, profile_visibility, user_id),
        )


def get_dashboard_stats(user_id: int) -> dict:
    with get_connection() as connection:
        row = connection.execute(
            """SELECT COUNT(*) AS runs, COALESCE(SUM(distance_km), 0) AS distance,
                      COALESCE(SUM(duration_seconds), 0) AS duration,
                      COALESCE(MIN(NULLIF(average_pace, 0)), 0) AS best_pace,
                      COALESCE(MAX(distance_km), 0) AS longest
               FROM runs WHERE user_id = ?""",
            (user_id,),
        ).fetchone()
    return dict(row)


def get_runs(user_id: int) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM runs WHERE user_id = ? ORDER BY started_at DESC", (user_id,)).fetchall()
    return [dict(row) for row in rows]


def get_run(run_id: int, user_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM runs WHERE id = ? AND user_id = ?", (run_id, user_id)).fetchone()
    return dict(row) if row else None


def get_points(run_id: int, user_id: int) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """SELECT gps_points.* FROM gps_points
               JOIN runs ON runs.id = gps_points.run_id
               WHERE gps_points.run_id = ? AND runs.user_id = ?
               ORDER BY gps_points.timestamp""",
            (run_id, user_id),
        ).fetchall()
    return [dict(row) for row in rows]


def get_open_run(user_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM runs WHERE user_id = ? AND finished_at IS NULL ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def active_run_from_record(user: dict, open_run: dict) -> dict:
    settings = get_settings(user["id"])
    return {
        "run_id": open_run["id"],
        "started_at": open_run["started_at"],
        "points": get_points(open_run["id"], user["id"]),
        "visibility": open_run["visibility"],
        "location_precision": settings["location_precision"],
        "share": open_run["visibility"] == "public",
        "paused_seconds": 0,
        "paused_at": None,
    }


def create_run(user_id: int, visibility: str) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO runs (user_id, started_at, visibility) VALUES (?, ?, ?)",
            (user_id, now_iso(), visibility),
        )
    return int(cursor.lastrowid)


def save_gps_point(run_id: int, point: dict) -> None:
    with get_connection() as connection:
        connection.execute(
            """INSERT INTO gps_points
               (run_id, timestamp, latitude, longitude, altitude, speed, accuracy)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                point["timestamp"],
                point["latitude"],
                point["longitude"],
                point.get("altitude"),
                point.get("speed"),
                point.get("accuracy"),
            ),
        )


def save_live_location(user_id: int, run_id: int, point: dict, metrics: dict, visibility: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """INSERT INTO live_locations
               (user_id, run_id, latitude, longitude, speed, distance, pace, status, visibility, last_update)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id, run_id) DO UPDATE SET
                 latitude = excluded.latitude, longitude = excluded.longitude,
                 speed = excluded.speed, distance = excluded.distance, pace = excluded.pace,
                 status = excluded.status, visibility = excluded.visibility, last_update = CURRENT_TIMESTAMP""",
            (
                user_id,
                run_id,
                point["latitude"],
                point["longitude"],
                (point.get("speed") or 0) * 3.6 if point.get("speed") is not None else None,
                metrics["distance_km"],
                metrics["average_pace"],
                visibility,
            ),
        )


def mark_live_paused(run_id: int, status: str) -> None:
    with get_connection() as connection:
        connection.execute("UPDATE live_locations SET status = ?, last_update = CURRENT_TIMESTAMP WHERE run_id = ?", (status, run_id))


def finish_run(user_id: int, run_id: int, metrics: dict, finished_at: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """UPDATE runs SET finished_at = ?, duration_seconds = ?, distance_km = ?,
               average_pace = ?, average_speed = ?, max_speed = ?, calories = ?, elevation_gain = ?
               WHERE id = ? AND user_id = ?""",
            (
                finished_at,
                metrics["duration_seconds"],
                metrics["distance_km"],
                metrics["average_pace"],
                metrics["average_speed"],
                metrics["max_speed"],
                metrics["calories"],
                metrics["elevation_gain"],
                run_id,
                user_id,
            ),
        )
        connection.execute("DELETE FROM live_locations WHERE run_id = ? AND user_id = ?", (run_id, user_id))


def delete_run(run_id: int, user_id: int) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM runs WHERE id = ? AND user_id = ?", (run_id, user_id))


def update_profile(user_id: int, name: str, photo: bytes | None) -> None:
    with get_connection() as connection:
        if photo is None:
            connection.execute("UPDATE users SET name = ? WHERE id = ?", (name.strip(), user_id))
        else:
            connection.execute("UPDATE users SET name = ?, profile_photo = ? WHERE id = ?", (name.strip(), photo, user_id))


def apply_session_defaults() -> None:
    st.session_state.setdefault("page", "Início")
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("active_run", None)
    st.session_state.setdefault("last_summary", None)
    st.session_state.setdefault("flash", None)
    st.session_state.setdefault("session_token", None)


def restore_session() -> None:
    if st.session_state.user:
        return
    token = st.query_params.get("session")
    user = get_user_by_session(token) if token else None
    if not user:
        if token:
            st.query_params.clear()
        return
    st.session_state.user = user
    st.session_state.session_token = token
    open_run = get_open_run(user["id"])
    if open_run:
        st.session_state.active_run = active_run_from_record(user, open_run)


def set_flash(message: str, kind: str = "success") -> None:
    st.session_state.flash = (message, kind)


def show_flash() -> None:
    if st.session_state.flash:
        message, kind = st.session_state.flash
        if kind == "error":
            st.error(message)
        elif kind == "warning":
            st.warning(message)
        else:
            st.success(message)
        st.session_state.flash = None


def render_brand(light: bool = False) -> None:
    name_color = "#102a27" if not light else "#efffe8"
    st.markdown(
        f'<div class="brand-mark"><div class="brand-dot">TT</div><div class="brand-name" style="color:{name_color}">TIME TYE</div></div>',
        unsafe_allow_html=True,
    )


def render_auth() -> None:
    left, center, right = st.columns([1, 2, 1])
    with center:
        render_brand(light=True)
        st.markdown('<div class="login-wrap"><div class="eyebrow">Corra. Conecte-se. Supere-se.</div><h1>Seu ritmo, do seu jeito.</h1><p style="color:#64817b">Acompanhe cada quilômetro com privacidade e clareza.</p></div>', unsafe_allow_html=True)
        login_tab, register_tab, recovery_tab = st.tabs(["Entrar", "Criar conta", "Recuperar acesso"])
        with login_tab:
            with st.form("login_form"):
                identity = st.text_input("E-mail ou nome de usuário")
                password = st.text_input("Senha", type="password")
                if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                    user = authenticate(identity, password)
                    if user:
                        st.session_state.user = user
                        st.session_state.session_token = create_session(user["id"])
                        st.query_params["session"] = st.session_state.session_token
                        open_run = get_open_run(user["id"])
                        if open_run:
                            st.session_state.active_run = active_run_from_record(user, open_run)
                        st.rerun()
                    else:
                        st.error("E-mail, usuário ou senha incorretos.")
        with register_tab:
            with st.form("register_form"):
                name = st.text_input("Nome completo")
                username = st.text_input("Nome de usuário")
                email = st.text_input("E-mail")
                phone = st.text_input("Celular (opcional)")
                password = st.text_input("Senha", type="password")
                confirmation = st.text_input("Confirme a senha", type="password")
                photo = st.file_uploader("Foto de perfil (opcional)", type=["png", "jpg", "jpeg"])
                if st.form_submit_button("Criar minha conta", type="primary", use_container_width=True):
                    errors = validate_registration(name, username, email, password, confirmation)
                    if errors:
                        for error in errors:
                            st.error(error)
                    else:
                        ok, message = register_user(name, username, email, password, phone, photo.getvalue() if photo else None)
                        if ok:
                            st.success(message + " Agora você já pode entrar.")
                        else:
                            st.error(message)
        with recovery_tab:
            st.caption("No MVP, o código de recuperação é gerado localmente. Em produção, conecte um provedor de e-mail para enviá-lo sem exibi-lo na tela.")
            with st.form("recovery_request_form"):
                recovery_email = st.text_input("E-mail cadastrado")
                if st.form_submit_button("Gerar código de recuperação", use_container_width=True):
                    token = create_reset_token(recovery_email)
                    if token:
                        st.session_state.recovery_token = token
                        st.success("Código temporário gerado para esta sessão.")
                        st.code(token)
                    else:
                        st.error("Não encontramos uma conta com esse e-mail.")
            with st.form("recovery_reset_form"):
                token_input = st.text_input("Código temporário")
                new_password = st.text_input("Nova senha", type="password")
                if st.form_submit_button("Salvar nova senha", use_container_width=True):
                    if reset_password(token_input, new_password):
                        st.success("Senha atualizada. Você já pode entrar.")
                    else:
                        st.error("Código inválido, expirado ou senha muito curta.")


def render_sidebar() -> None:
    user = st.session_state.user
    with st.sidebar:
        render_brand(light=True)
        st.caption(f"Olá, {user['name'].split()[0]}")
        pages = ["Início", "Correr", "Corredores ao vivo", "Minhas corridas", "Perfil", "Configurações"]
        selected = st.radio("Navegação", pages, index=pages.index(st.session_state.page) if st.session_state.page in pages else 0)
        st.session_state.page = selected
        st.divider()
        if st.button("Sair", use_container_width=True):
            revoke_session(st.session_state.get("session_token") or st.query_params.get("session"))
            st.query_params.clear()
            st.session_state.clear()
            apply_session_defaults()
            st.rerun()
        st.caption("Sua localização só é compartilhada com consentimento explícito.")


def render_dashboard() -> None:
    user = st.session_state.user
    stats = get_dashboard_stats(user["id"])
    st.markdown(f'<div class="hero"><div class="eyebrow" style="color:#d9f99d">Painel do corredor</div><h1>Olá, {user["name"].split()[0]}.</h1><p>Hoje é um bom dia para deixar o corpo encontrar o próprio ritmo.</p></div>', unsafe_allow_html=True)
    if st.button("COMEÇAR CORRIDA", type="primary", use_container_width=True):
        st.session_state.page = "Correr"
        st.rerun()
    st.markdown('<h3 class="section-title">Seu histórico em números</h3>', unsafe_allow_html=True)
    cols = st.columns(5)
    values = [
        ("Corridas", str(stats["runs"]), "total salvo"),
        ("Distância total", f'{stats["distance"]:.1f} km', "percurso acumulado"),
        ("Tempo total", format_duration(stats["duration"]), "em movimento"),
        ("Melhor ritmo", format_pace(stats["best_pace"]), "menor média"),
        ("Maior distância", f'{stats["longest"]:.1f} km', "em uma corrida"),
    ]
    for column, (label, value, detail) in zip(cols, values):
        with column:
            stat_card(label, value, detail)
    runs = get_runs(user["id"])
    st.markdown('<h3 class="section-title">Últimas corridas</h3>', unsafe_allow_html=True)
    if not runs:
        st.info("Você ainda não salvou nenhuma corrida. Seu primeiro percurso começa agora.")
    else:
        for run in runs[:3]:
            date = parse_iso(run["started_at"]).astimezone().strftime("%d/%m/%Y · %H:%M")
            st.markdown(f"**{date}**  ·  {run['distance_km']:.2f} km  ·  {format_duration(run['duration_seconds'])}  ·  {format_pace(run['average_pace'])}")


def start_run_form() -> None:
    settings = get_settings(st.session_state.user["id"])
    st.markdown('<div class="eyebrow">Novo treino</div><h1>Pronto para correr?</h1>', unsafe_allow_html=True)
    st.markdown("O GPS será usado somente enquanto esta tela estiver aberta. Nenhum ponto será inventado se o navegador não entregar localização.")
    with st.form("start_run_form"):
        visibility_label = st.selectbox("Quem pode ver você correndo?", ["Privado", "Amigos (em breve)", "Público"])
        share = st.checkbox(
            "Autorizo compartilhar minha localização durante esta corrida.",
            value=bool(settings["location_sharing"]),
        )
        hide_exact = st.checkbox(
            "Ocultar localização exata no mapa público.",
            value=settings["location_precision"] == "approximate",
        )
        consent = st.checkbox("Entendo que o navegador pode interromper o GPS em segundo plano.", value=False)
        if st.form_submit_button("Iniciar corrida", type="primary", use_container_width=True):
            if not consent:
                st.error("Confirme a limitação do navegador para continuar.")
                return
            visibility = {"Privado": "private", "Amigos (em breve)": "friends", "Público": "public"}[visibility_label]
            if visibility == "public" and not share:
                st.error("Para usar o mapa público, autorize o compartilhamento nesta corrida.")
                return
            run_id = create_run(st.session_state.user["id"], visibility)
            st.session_state.active_run = {
                "run_id": run_id,
                "started_at": now_iso(),
                "points": [],
                "visibility": visibility,
                "location_precision": "approximate" if hide_exact else "exact",
                "share": share,
                "paused_seconds": 0,
                "paused_at": None,
            }
            st.rerun()


def elapsed_for_active_run(active: dict) -> int:
    elapsed = (datetime.now(timezone.utc) - parse_iso(active["started_at"])).total_seconds()
    elapsed -= active.get("paused_seconds", 0)
    if active.get("paused_at"):
        elapsed -= (datetime.now(timezone.utc) - parse_iso(active["paused_at"])).total_seconds()
    return max(0, int(elapsed))


def render_active_run() -> None:
    active = st.session_state.active_run
    user = st.session_state.user
    location = get_current_location(key=f"gps_run_{active['run_id']}", interval_ms=5000)
    if location["available"] and not active.get("paused_at"):
        points = filter_gps_points(active.get("points", []) + [location])
        if len(points) > len(active.get("points", [])):
            active["points"] = points
            save_gps_point(active["run_id"], location)
            metrics = calculate_metrics(points, elapsed_for_active_run(active))
            if active.get("share") and active["visibility"] == "public":
                save_live_location(user["id"], active["run_id"], location, metrics, active["visibility"])
    if location["available"]:
        st.success("GPS conectado · precisão recebida pelo navegador" if location.get("accuracy") else "GPS conectado")
    else:
        st.warning(location["message"])

    points = active.get("points", [])
    metrics = calculate_metrics(points, elapsed_for_active_run(active))
    st.markdown('<div class="eyebrow">Corrida em andamento</div><h1>Encontre seu ritmo.</h1>', unsafe_allow_html=True)
    with st.container(border=True):
        metric_cols = st.columns(5)
        metric_values = [
            ("Tempo", format_duration(metrics["duration_seconds"]), ""),
            ("Distância", f'{metrics["distance_km"]:.2f}', "km"),
            ("Ritmo", format_pace(metrics["average_pace"]), ""),
            ("Velocidade", f'{metrics["average_speed"]:.1f}', "km/h"),
            ("Calorias", f'{metrics["calories"]:.0f}', "kcal"),
        ]
        for column, (label, value, unit) in zip(metric_cols, metric_values):
            with column:
                metric_big(label, value, unit)
    st.caption(f"Pontos GPS válidos registrados: {len(points)} · elevação acumulada: {metrics['elevation_gain']:.0f} m")
    render_route_map(points, active.get("location_precision", "exact"))
    buttons = st.columns(3)
    with buttons[0]:
        if not active.get("paused_at"):
            if st.button("Pausar", use_container_width=True):
                active["paused_at"] = now_iso()
                mark_live_paused(active["run_id"], "paused")
                st.rerun()
        else:
            if st.button("Continuar", type="primary", use_container_width=True):
                active["paused_seconds"] += int((datetime.now(timezone.utc) - parse_iso(active["paused_at"])).total_seconds())
                active["paused_at"] = None
                mark_live_paused(active["run_id"], "running")
                st.rerun()
    with buttons[1]:
        st.caption("GPS automático")
    with buttons[2]:
        if st.button("Finalizar", use_container_width=True):
            active["confirm_finalize"] = True
    if active.get("confirm_finalize"):
        st.warning("Tem certeza que deseja finalizar sua corrida?")
        confirm, cancel = st.columns(2)
        with confirm:
            if st.button("Sim, finalizar", type="primary", use_container_width=True):
                metrics = calculate_metrics(active["points"], elapsed_for_active_run(active))
                finish_run(user["id"], active["run_id"], metrics, now_iso())
                st.session_state.last_summary = {"run_id": active["run_id"], **metrics}
                st.session_state.active_run = None
                st.session_state.page = "Minhas corridas"
                st.rerun()
        with cancel:
            if st.button("Continuar corrida", use_container_width=True):
                active["confirm_finalize"] = False
                st.rerun()


def render_run_page() -> None:
    active = st.session_state.active_run
    if active:
        render_active_run()
    else:
        start_run_form()


def render_run_detail(run: dict) -> None:
    user_id = st.session_state.user["id"]
    points = get_points(run["id"], user_id)
    st.markdown(f'<div class="hero"><div class="eyebrow" style="color:#d9f99d">Detalhes do percurso</div><h1>{run["distance_km"]:.2f} km</h1><p>{parse_iso(run["started_at"]).astimezone().strftime("%d de %B de %Y · %H:%M")}</p></div>', unsafe_allow_html=True)
    cols = st.columns(5)
    values = [
        ("Tempo", format_duration(run["duration_seconds"]), ""),
        ("Ritmo médio", format_pace(run["average_pace"]), ""),
        ("Velocidade média", f'{run["average_speed"]:.1f}', "km/h"),
        ("Velocidade máxima", f'{run["max_speed"]:.1f}', "km/h"),
        ("Calorias", f'{run["calories"]:.0f}', "kcal"),
    ]
    for column, (label, value, unit) in zip(cols, values):
        with column:
            metric_big(label, value, unit)
    render_route_map(points, "exact")
    if points:
        chart = pd.DataFrame(points)
        chart["timestamp"] = pd.to_datetime(chart["timestamp"])
        chart = chart.set_index("timestamp")
        available = [column for column in ["speed", "altitude"] if column in chart and chart[column].notna().any()]
        if available:
            st.markdown("#### Dados registrados pelo GPS")
            st.line_chart(chart[available], height=220)


def render_history() -> None:
    st.markdown('<div class="eyebrow">Seu progresso</div><h1>Minhas corridas</h1>', unsafe_allow_html=True)
    runs = get_runs(st.session_state.user["id"])
    if not runs:
        st.info("As corridas que você salvar aparecerão aqui.")
        return
    options = {f"{parse_iso(run['started_at']).astimezone().strftime('%d/%m/%Y %H:%M')} · {run['distance_km']:.2f} km": run for run in runs}
    selected_label = st.selectbox("Escolha uma corrida", list(options))
    selected = options[selected_label]
    render_run_detail(selected)
    st.divider()
    if st.button("Excluir esta corrida", type="secondary"):
        st.session_state.confirm_delete = selected["id"]
    if st.session_state.get("confirm_delete") == selected["id"]:
        st.warning("Essa ação apaga a corrida e todos os pontos GPS associados.")
        confirm, cancel = st.columns(2)
        with confirm:
            if st.button("Confirmar exclusão", type="primary"):
                delete_run(selected["id"], st.session_state.user["id"])
                st.session_state.confirm_delete = None
                st.rerun()
        with cancel:
            if st.button("Cancelar exclusão"):
                st.session_state.confirm_delete = None
                st.rerun()


def render_live_runners() -> None:
    st.markdown('<div class="eyebrow">Agora</div><h1>Corredores ao vivo</h1>', unsafe_allow_html=True)
    st.caption("Apenas pessoas em corrida, com consentimento público e atualização recente, aparecem aqui.")
    st_autorefresh(interval=30000, key="live_runners_refresh")
    locations = get_public_live_locations()
    render_live_map(locations)
    if locations:
        for location in locations:
            pace = format_pace(location.get("pace") or 0)
            st.markdown(f"**{location['name']}** · correndo · {location['distance']:.2f} km · {pace}")
    else:
        st.info("O mapa está tranquilo agora. Você pode ser o primeiro corredor público.")


def render_profile() -> None:
    user = get_user(st.session_state.user["id"])
    st.session_state.user = user or st.session_state.user
    stats = get_dashboard_stats(user["id"])
    st.markdown('<div class="eyebrow">Identidade do corredor</div><h1>Perfil</h1>', unsafe_allow_html=True)
    if user.get("profile_photo"):
        st.image(user["profile_photo"], width=96)
    with st.form("profile_form"):
        name = st.text_input("Nome", value=user["name"])
        photo = st.file_uploader("Atualizar foto", type=["png", "jpg", "jpeg"])
        if st.form_submit_button("Salvar perfil", type="primary"):
            update_profile(user["id"], name, photo.getvalue() if photo else None)
            st.session_state.user = get_user(user["id"])
            st.success("Perfil atualizado.")
    cols = st.columns(4)
    for column, (label, value) in zip(cols, [("Corridas", stats["runs"]), ("Distância", f'{stats["distance"]:.1f} km'), ("Tempo", format_duration(stats["duration"])), ("Maior distância", f'{stats["longest"]:.1f} km')]):
        with column:
            stat_card(label, str(value))
    st.markdown("#### Dados privados")
    st.caption(f"E-mail: {user['email']} · telefone: {'cadastrado' if user.get('phone') else 'não informado'}")
    st.caption("Esses dados nunca são exibidos no mapa ou para outros corredores.")


def render_settings() -> None:
    user_id = st.session_state.user["id"]
    current = get_settings(user_id)
    st.markdown('<div class="eyebrow">Controle e privacidade</div><h1>Configurações</h1>', unsafe_allow_html=True)
    with st.form("settings_form"):
        share = st.checkbox("Compartilhar minha localização durante a corrida", value=bool(current["location_sharing"]))
        precision = st.selectbox("Proteção da localização pública", ["exact", "approximate"], index=0 if current["location_precision"] == "exact" else 1, format_func=lambda value: "Mostrar localização exata" if value == "exact" else "Aproximar localização no mapa")
        profile_visibility = st.selectbox("Visibilidade do meu perfil", ["private", "friends", "public"], index=["private", "friends", "public"].index(current["profile_visibility"]), format_func=lambda value: {"private": "Privado", "friends": "Amigos", "public": "Público"}[value])
        if st.form_submit_button("Salvar configurações", type="primary"):
            update_settings(user_id, share, precision, profile_visibility)
            st.success("Preferências salvas. O padrão continua sendo privado.")
    st.info("O navegador pode limitar o GPS quando a tela é bloqueada, o app vai para segundo plano ou a bateria entra em economia. Para rastreamento contínuo em segundo plano, o próximo passo é um app Android/iOS conectado a uma API.")


def render_app() -> None:
    apply_session_defaults()
    restore_session()
    apply_styles(login=not st.session_state.user)
    if not st.session_state.user:
        render_auth()
        return
    render_sidebar()
    show_flash()
    page = st.session_state.page
    if page == "Início":
        render_dashboard()
    elif page == "Correr":
        render_run_page()
    elif page == "Corredores ao vivo":
        render_live_runners()
    elif page == "Minhas corridas":
        render_history()
    elif page == "Perfil":
        render_profile()
    else:
        render_settings()


st.set_page_config(page_title="TIME TYE", page_icon="🏃", layout="wide", initial_sidebar_state="expanded")
run_migrations()
render_app()