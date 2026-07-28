"""Supabase access for QuizMonkey.

Everything that talks to the backend lives here, so the UI never touches the
Supabase client directly and the app keeps working when no backend is
configured at all ("continue without login").

Credentials come from SUPABASE_URL / SUPABASE_ANON_KEY, read from the
environment or from a .env file next to the project root. They are never
hard-coded: the anon key is public but still belongs to the deployment, not to
the source tree.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # supabase is optional: the offline mode must work without it
    from supabase import Client, create_client
except ImportError:  # pragma: no cover - only hit in trimmed-down builds
    Client = None  # type: ignore[assignment]
    create_client = None  # type: ignore[assignment]


class BackendError(Exception):
    """A backend call failed in a way worth showing to the user."""


@dataclass
class Profile:
    """The signed-in user, as the UI needs to know them."""

    id: str
    email: str
    first_name: str
    last_name: str
    role: str  # account role: "trainer" or "trainee"
    active_view: str  # which UI the user currently wants to see

    @property
    def display_name(self) -> str:
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.email

    @property
    def is_trainer(self) -> bool:
        return self.role == "trainer"

    @property
    def sees_trainer_ui(self) -> bool:
        return self.role == "trainer" and self.active_view == "trainer"


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader.

    A dependency like python-dotenv would do this too, but it is a handful of
    lines and this keeps the packaged app's dependency list short. Existing
    environment variables always win, so a real deployment can just set them.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _read_api_base() -> str:
    """Base URL of the test API server (no trailing slash)."""
    _load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    base = os.environ.get("QM_API_BASE", "").strip()
    if not base:
        try:
            import app_config

            base = getattr(app_config, "API_BASE", "").strip()
        except Exception:
            base = ""
    if not base:
        base = os.environ.get("PUBLIC_BASE_URL", "").strip()
    return (base or "http://127.0.0.1:8000").rstrip("/")


def _read_credentials() -> tuple[str, str]:
    # src/ -> project root
    _load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_ANON_KEY", "").strip()

    # Packaged builds (iOS/Android) have no .env inside the bundle, so fall
    # back to the compiled-in config module. Env / .env still win, so a dev
    # machine or a server deployment overrides it.
    if not url or not key:
        try:
            import app_config  # bundled with src/, git-ignored

            url = url or getattr(app_config, "SUPABASE_URL", "").strip()
            key = key or getattr(app_config, "SUPABASE_ANON_KEY", "").strip()
        except Exception:
            pass
    return url, key


class Backend:
    """Thin wrapper around the Supabase client.

    `available` is False when no credentials are configured or the client
    library is missing. The app then hides the login screen instead of showing
    a form that could never succeed.
    """

    def __init__(self) -> None:
        url, key = _read_credentials()
        self._client: Client | None = None
        self.config_error: str | None = None
        # Base URL of the web server that hosts the test API. Tests run through
        # it so answer keys stay server-side (unlike quizzes, tests need a
        # connection). Configurable for packaged builds via app_config/env.
        self.api_base = _read_api_base()

        if not url or not key:
            self.config_error = (
                "No Supabase credentials found. Copy .env.example to .env and "
                "fill in SUPABASE_URL and SUPABASE_ANON_KEY."
            )
            return
        if create_client is None:
            self.config_error = "The 'supabase' package is not installed."
            return

        try:
            self._client = create_client(url, key)
        except Exception as ex:
            self.config_error = f"Could not reach Supabase: {ex}"

    @property
    def available(self) -> bool:
        return self._client is not None

    @property
    def client(self) -> Client:
        if self._client is None:
            raise BackendError(self.config_error or "Backend is not configured.")
        return self._client

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def sign_up(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        role: str,
    ) -> Profile | None:
        """Register a new account.

        Returns the profile when Supabase signed the user straight in, or None
        when the project requires e-mail confirmation first — in that case the
        caller should tell the user to check their inbox.
        """
        if role not in ("trainer", "trainee"):
            role = "trainee"
        try:
            result = self.client.auth.sign_up(
                {
                    "email": email,
                    "password": password,
                    # The database trigger reads these to build the profile row.
                    "options": {
                        "data": {
                            "first_name": first_name,
                            "last_name": last_name,
                            "role": role,
                        }
                    },
                }
            )
        except Exception as ex:
            raise BackendError(_friendly_auth_error(ex)) from ex

        if result.session is None:
            return None
        return self.current_profile()

    def sign_in(self, email: str, password: str) -> Profile:
        try:
            self.client.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
        except Exception as ex:
            raise BackendError(_friendly_auth_error(ex)) from ex

        profile = self.current_profile()
        if profile is None:
            raise BackendError("Signed in, but no profile was found.")
        return profile

    def access_token(self) -> str | None:
        """The current session's access token, for calling the test API."""
        if not self.available:
            return None
        try:
            session = self.client.auth.get_session()
        except Exception:
            return None
        return session.access_token if session else None

    def sign_out(self) -> None:
        try:
            self.client.auth.sign_out()
        except Exception:
            # Losing the local session is enough; a failing round trip here
            # must not trap the user in a signed-in state.
            pass

    def send_password_reset(self, email: str) -> None:
        try:
            self.client.auth.reset_password_for_email(email)
        except Exception as ex:
            raise BackendError(_friendly_auth_error(ex)) from ex

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------
    def current_profile(self) -> Profile | None:
        if not self.available:
            return None
        try:
            user = self.client.auth.get_user()
        except Exception:
            return None
        if user is None or user.user is None:
            return None

        user_id = user.user.id
        try:
            rows = (
                self.client.table("profiles")
                .select("id, email, first_name, last_name, role, active_view")
                .eq("id", user_id)
                .execute()
            )
        except Exception as ex:
            raise BackendError(f"Could not load your profile: {ex}") from ex

        if not rows.data:
            return None
        return _to_profile(rows.data[0])

    def set_active_view(self, profile: Profile, view: str) -> Profile:
        """Remember whether a trainer is currently using the trainee UI."""
        if view not in ("trainer", "trainee"):
            view = "trainee"
        try:
            self.client.table("profiles").update({"active_view": view}).eq(
                "id", profile.id
            ).execute()
        except Exception as ex:
            raise BackendError(f"Could not switch view: {ex}") from ex
        profile.active_view = view
        return profile

    # ------------------------------------------------------------------
    # Groups and invitations (trainee side)
    # ------------------------------------------------------------------
    def pending_invitations(self) -> list[dict]:
        """Group invitations addressed to the signed-in user, not yet accepted.

        Each dict: {id, group_id, group_name, trainer_name}. RLS lets a trainee
        read only rows addressed to them (by id or e-mail), so this is safe to
        query broadly.
        """
        try:
            rows = (
                self.client.table("group_members")
                .select("id, group_id, groups(name, profiles(first_name, last_name))")
                .eq("status", "invited")
                .execute()
            )
        except Exception as ex:
            raise BackendError(f"Could not load invitations: {ex}") from ex

        out: list[dict] = []
        for r in rows.data or []:
            group = r.get("groups") or {}
            trainer = group.get("profiles") or {}
            trainer_name = (
                f"{trainer.get('first_name', '')} {trainer.get('last_name', '')}"
            ).strip()
            out.append(
                {
                    "id": r["id"],
                    "group_id": r["group_id"],
                    "group_name": group.get("name") or "a group",
                    "trainer_name": trainer_name,
                }
            )
        return out

    def accept_invitation(self, member_id: str) -> None:
        from datetime import datetime, timezone

        try:
            self.client.table("group_members").update(
                {
                    "status": "accepted",
                    "accepted_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", member_id).execute()
        except Exception as ex:
            raise BackendError(f"Could not accept invitation: {ex}") from ex

    def decline_invitation(self, member_id: str) -> None:
        # Declining simply removes the pending membership row.
        try:
            self.client.table("group_members").delete().eq(
                "id", member_id
            ).execute()
        except Exception as ex:
            raise BackendError(f"Could not decline invitation: {ex}") from ex

    def my_groups(self) -> list[dict]:
        """Groups the signed-in user has accepted. Each: {member_id, group_id,
        group_name}."""
        try:
            rows = (
                self.client.table("group_members")
                .select("id, group_id, groups(name)")
                .eq("status", "accepted")
                .execute()
            )
        except Exception as ex:
            raise BackendError(f"Could not load your groups: {ex}") from ex

        out: list[dict] = []
        for r in rows.data or []:
            group = r.get("groups") or {}
            out.append(
                {
                    "member_id": r["id"],
                    "group_id": r["group_id"],
                    "group_name": group.get("name") or "a group",
                }
            )
        return out

    def leave_group(self, member_id: str) -> None:
        try:
            self.client.table("group_members").delete().eq(
                "id", member_id
            ).execute()
        except Exception as ex:
            raise BackendError(f"Could not leave group: {ex}") from ex


def _to_profile(row: dict) -> Profile:
    return Profile(
        id=str(row.get("id", "")),
        email=row.get("email") or "",
        first_name=row.get("first_name") or "",
        last_name=row.get("last_name") or "",
        role=row.get("role") or "trainee",
        active_view=row.get("active_view") or "trainee",
    )


def _friendly_auth_error(ex: Exception) -> str:
    """Turn Supabase's wording into something a user can act on."""
    message = str(ex)
    lowered = message.lower()
    if "invalid login credentials" in lowered:
        return "Wrong e-mail or password."
    if "user already registered" in lowered or "already been registered" in lowered:
        return "This e-mail is already registered. Try signing in instead."
    if "password should be at least" in lowered:
        return "Password is too short (at least 6 characters)."
    if "unable to validate email" in lowered or "invalid email" in lowered:
        return "That does not look like a valid e-mail address."
    if "email not confirmed" in lowered:
        return "Please confirm your e-mail address first, then sign in."
    return message
