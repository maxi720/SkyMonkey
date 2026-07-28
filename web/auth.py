"""Session handling for the web app.

The Supabase tokens are kept in a signed, HttpOnly cookie. Signed so the
client cannot tamper with it, HttpOnly so no script can read it, SameSite=Lax
so it is not sent along on cross-site requests (CSRF protection for the
plain-form POSTs used throughout).

The cookie is strictly necessary for the login to work at all, so under
§ 165 TKG 2021 it needs no consent banner. Nothing else is stored client-side.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from itsdangerous import BadSignature, URLSafeSerializer

COOKIE_NAME = "qm_session"


class SessionError(Exception):
    pass


def _secret() -> str:
    # Read on every use rather than at import: main.py loads the .env file
    # after this module is imported, and a value cached here would be empty.
    return os.environ.get("WEB_SESSION_SECRET", "").strip()


def secret_configured() -> bool:
    return bool(_secret())


def _serializer() -> URLSafeSerializer:
    secret = _secret()
    if not secret:
        raise SessionError(
            "WEB_SESSION_SECRET is not set. Generate one with "
            "`python -c \"import secrets; print(secrets.token_urlsafe(48))\"` "
            "and put it in .env."
        )
    return URLSafeSerializer(secret, salt="quizmonkey-session")


@dataclass
class SessionTokens:
    access_token: str
    refresh_token: str


def dump_session(tokens: SessionTokens) -> str:
    return _serializer().dumps(
        {"at": tokens.access_token, "rt": tokens.refresh_token}
    )


def load_session(raw: str | None) -> SessionTokens | None:
    if not raw:
        return None
    try:
        data = _serializer().loads(raw)
    except (BadSignature, SessionError):
        return None
    if not isinstance(data, dict):
        return None
    access = data.get("at")
    refresh = data.get("rt")
    if not access or not refresh:
        return None
    return SessionTokens(access_token=access, refresh_token=refresh)
