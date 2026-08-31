from __future__ import annotations

import re
import secrets
import hashlib
from datetime import datetime, timedelta, timezone

from database.database import get_connection
from auth.password import hash_password, verify_password

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_registration(name: str, username: str, email: str, password: str, confirmation: str) -> list[str]:
    errors: list[str] = []
    if len(name.strip()) < 2:
        errors.append("Informe seu nome completo.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,24}", username.strip()):
        errors.append("O nome de usuário deve ter 3–24 caracteres e usar apenas letras, números, ponto, hífen ou sublinhado.")
    if not EMAIL_PATTERN.fullmatch(email.strip()):
        errors.append("Informe um e-mail válido.")
    if len(password) < 8:
        errors.append("A senha precisa ter pelo menos 8 caracteres.")
    if password != confirmation:
        errors.append("A confirmação da senha não confere.")
    return errors


def register_user(name: str, username: str, email: str, password: str, phone: str | None = None, profile_photo: bytes | None = None) -> tuple[bool, str]:
    username = username.strip()
    email = email.strip().lower()
    errors = validate_registration(name, username, email, password, password)
    if errors:
        return False, errors[0]
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """INSERT INTO users (username, name, email, password_hash, phone, profile_photo)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (username, name.strip(), email, hash_password(password), phone or None, profile_photo),
            )
            user_id = cursor.lastrowid
            connection.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))
        return True, "Conta criada com sucesso."
    except Exception as error:
        if "users.username" in str(error):
            return False, "Esse nome de usuário já está em uso."
        if "users.email" in str(error):
            return False, "Esse e-mail já está cadastrado."
        return False, "Não foi possível criar sua conta agora."


def authenticate(email_or_username: str, password: str):
    with get_connection() as connection:
        user = connection.execute(
            """SELECT * FROM users
               WHERE email = ? COLLATE NOCASE OR username = ? COLLATE NOCASE""",
            (email_or_username.strip(), email_or_username.strip()),
        ).fetchone()
    if user and verify_password(password, user["password_hash"]):
        return dict(user)
    return None


def _session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(user_id: int, days: int = 30) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (_session_token_hash(token), user_id, expires_at),
        )
    return token


def get_user_by_session(token: str):
    if not token:
        return None
    with get_connection() as connection:
        user = connection.execute(
            """SELECT users.* FROM users
               JOIN auth_sessions ON auth_sessions.user_id = users.id
               WHERE auth_sessions.token_hash = ? AND auth_sessions.expires_at > ?""",
            (_session_token_hash(token), datetime.now(timezone.utc).isoformat()),
        ).fetchone()
    return dict(user) if user else None


def revoke_session(token: str | None) -> None:
    if not token:
        return
    with get_connection() as connection:
        connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (_session_token_hash(token),))


def get_user(user_id: int):
    with get_connection() as connection:
        user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(user) if user else None


def create_reset_token(email: str) -> str | None:
    with get_connection() as connection:
        user = connection.execute("SELECT id FROM users WHERE email = ? COLLATE NOCASE", (email.strip(),)).fetchone()
        if not user:
            return None
        token = secrets.token_urlsafe(20)
        token_hash = hash_password(token)
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        connection.execute(
            "INSERT INTO password_reset_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
            (user["id"], token_hash, expires_at),
        )
        return token


def reset_password(token: str, new_password: str) -> bool:
    if len(new_password) < 8:
        return False
    with get_connection() as connection:
        candidates = connection.execute(
            """SELECT * FROM password_reset_tokens
               WHERE used_at IS NULL AND expires_at > ? ORDER BY id DESC""",
            (datetime.now(timezone.utc).isoformat(),),
        ).fetchall()
        for candidate in candidates:
            if verify_password(token, candidate["token_hash"]):
                connection.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_password), candidate["user_id"]))
                connection.execute("UPDATE password_reset_tokens SET used_at = CURRENT_TIMESTAMP WHERE id = ?", (candidate["id"],))
                return True
    return False