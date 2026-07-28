"""QuizMonkey web app — the trainer side.

FastAPI + Jinja2 + HTMX, server-rendered. Every request that touches data runs
through Supabase with the *user's own* access token, so the Row Level Security
policies in supabase/migrations/0001_init.sql are what actually enforce who may
see and change what. The web app never uses the service role key.

Privacy notes (GDPR / DSGVO):
  * No third-party requests at all. Fonts come from the operating system,
    htmx is served from web/static. A Content Security Policy enforces this,
    so no visitor IP can leak to a CDN.
  * No analytics, no tracking, no profiling.
  * One strictly necessary session cookie (see web/auth.py) — no consent
    banner required under § 165 TKG 2021.
"""

from __future__ import annotations

import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Reuse the mobile app's credential loading and error wording.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import quiz_csv  # noqa: E402
import test_build  # noqa: E402
import test_take  # noqa: E402
from backend import _friendly_auth_error, _load_dotenv, _to_profile  # noqa: E402

# Must happen before anything reads the environment.
_load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from email_out import send_invitation_email, smtp_configured  # noqa: E402

from i18n import LANG_COOKIE, LANGUAGES, pick_language, translate  # noqa: E402

from auth import (  # noqa: E402
    COOKIE_NAME,
    SessionTokens,
    dump_session,
    load_session,
    secret_configured,
)

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="QuizMonkey", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()
# Server-only. Bypasses RLS so the server can draw test questions and score
# attempts without ever exposing the answer key to the trainee's client. Never
# shipped in the mobile app; only this trusted server holds it.
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()


def _service_client():
    """A privileged Supabase client for server-side test operations, or None
    when the service key is not configured."""
    if create_client is None or not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Everything is same-origin; this is the technical guarantee behind the
# "no third-party requests" claim in the privacy policy (Art. 25 GDPR,
# privacy by design).
CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = CSP
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    return response


# ---------------------------------------------------------------------------
# Supabase per request, authenticated as the signed-in user
# ---------------------------------------------------------------------------
def _client_for(tokens: SessionTokens | None):
    """A Supabase client bound to this user's token, or None when signed out."""
    if create_client is None or not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return None
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    if tokens is not None:
        try:
            client.auth.set_session(tokens.access_token, tokens.refresh_token)
        except Exception:
            return None
    return client


def _current(request: Request):
    """Return (client, profile) for the signed-in user, or (None, None)."""
    tokens = load_session(request.cookies.get(COOKIE_NAME))
    if tokens is None:
        return None, None
    client = _client_for(tokens)
    if client is None:
        return None, None
    try:
        user = client.auth.get_user()
        if user is None or user.user is None:
            return None, None
        rows = (
            client.table("profiles")
            .select("id, email, first_name, last_name, role, active_view")
            .eq("id", user.user.id)
            .execute()
        )
    except Exception:
        return None, None
    if not rows.data:
        return client, None
    return client, _to_profile(rows.data[0])


def _lang(request: Request) -> str:
    return pick_language(
        request.cookies.get(LANG_COOKIE), request.headers.get("accept-language")
    )


# Appearance. Light is the product's design on both front ends (the mobile app
# is fixed to light); dark is an explicit choice, never inferred from the OS.
THEME_COOKIE = "qm_theme"
THEMES = ("light", "dark")
DEFAULT_THEME = "light"


def _theme(request: Request) -> str:
    value = request.cookies.get(THEME_COOKIE)
    return value if value in THEMES else DEFAULT_THEME


def _asset_version(name: str) -> str:
    """Cache buster for a file in static/: its modification time.

    Without it a browser happily keeps serving a stylesheet from cache after a
    redeploy, so a restyle appears not to have happened at all.
    """
    try:
        return str(int((BASE_DIR / "static" / name).stat().st_mtime))
    except OSError:
        return "0"


def _render(request: Request, template: str, **context) -> HTMLResponse:
    """Render with the language helpers every template needs.

    `notice` and `error` arrive as translation keys in the query string, so a
    redirect never has to carry a language-specific sentence around.
    """
    lang = _lang(request)
    context.setdefault("lang", lang)
    context.setdefault("theme", _theme(request))
    context["t"] = lambda key, *args: translate(key, lang, *args)
    context.setdefault("asset_v", _asset_version)

    for slot in ("notice", "error"):
        raw = context.get(slot)
        if raw:
            translated = translate(raw, lang)
            # Unknown key -> show the raw text (used for backend error details).
            context[slot] = translated
    return templates.TemplateResponse(
        request=request, name=template, context=context
    )


def _redirect(target: str) -> RedirectResponse:
    # 303 so the browser switches to GET after a form POST.
    return RedirectResponse(target, status_code=303)


def _fmt_dt(value) -> str:
    """Format an ISO timestamp from Supabase as 'YYYY-MM-DD HH:MM'. Empty
    string when missing or unparseable, so the template can just hide it."""
    if not value:
        return ""
    try:
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(value)


def _parse_iso(value):
    """Supabase ISO timestamp -> aware datetime, or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------
def _trainer_overview(client, profile) -> dict:
    """Counts and recent rows for the trainer dashboard.

    Every part is optional: a dashboard that renders with a missing tile is far
    better than one that 500s because a single query failed, so each block
    swallows its own error and leaves the value at its default.
    """
    data = {
        "groups": [], "quizzes": [], "tests": [],
        "group_count": 0, "trainee_count": 0, "quiz_count": 0, "test_count": 0,
    }

    try:
        rows = (
            client.table("groups")
            .select("id, name, group_members(count)")
            .eq("owner_id", profile.id).order("created_at").execute()
        )
        groups = []
        for g in rows.data or []:
            # Supabase returns the aggregate as [{"count": N}].
            agg = g.get("group_members") or []
            groups.append({
                "id": g["id"], "name": g["name"],
                "member_count": agg[0]["count"] if agg else 0,
            })
        data["groups"] = groups
        data["group_count"] = len(groups)
        data["trainee_count"] = sum(g["member_count"] for g in groups)
    except Exception:
        pass

    try:
        rows = (
            client.table("quizzes").select("id, name, updated_at, created_at")
            .eq("owner_id", profile.id).execute()
        )
        quizzes = sorted(
            rows.data or [],
            key=lambda q: q.get("updated_at") or q.get("created_at") or "",
            reverse=True,
        )
        data["quiz_count"] = len(quizzes)
        data["quizzes"] = [
            {**q, "changed": _fmt_dt(q.get("updated_at") or q.get("created_at"))}
            for q in quizzes[:5]
        ]
    except Exception:
        pass

    try:
        rows = (
            client.table("tests")
            .select("id, name, pass_percent, question_count, created_at")
            .eq("owner_id", profile.id).execute()
        )
        tests = sorted(
            rows.data or [], key=lambda x: x.get("created_at") or "", reverse=True
        )
        data["test_count"] = len(tests)
        data["tests"] = [
            {**x, "created": _fmt_dt(x.get("created_at"))} for x in tests[:5]
        ]
    except Exception:
        pass

    return data


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    client, profile = _current(request)
    if profile is None:
        return _redirect("/login")

    if profile.is_trainer:
        return _render(
            request, "dashboard.html", profile=profile,
            **_trainer_overview(client, profile),
        )

    # Trainee: the one thing that matters is which tests are waiting.
    svc = _service_client()
    tests = []
    try:
        rows = (
            client.table("tests").select(_TEST_TAKE_FIELDS)
            .neq("owner_id", profile.id).order("name").execute().data or []
        )
        for t in rows:
            tests.append(
                {**t, "status": test_take.attempt_status(svc, t, profile.id)
                 if svc else None}
            )
    except Exception:
        pass

    open_tests = [
        t for t in tests if not (t.get("status") or {}).get("done")
    ]
    return _render(
        request, "dashboard.html", profile=profile, tests=tests[:5],
        test_count=len(tests), open_count=len(open_tests),
    )


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, error: str | None = None, notice: str | None = None):
    _, profile = _current(request)
    if profile is not None:
        return _redirect("/")
    return _render(
        request,
        "login.html",
        error=error,
        notice=notice,
        configured=bool(SUPABASE_URL and SUPABASE_ANON_KEY and secret_configured()),
    )


@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    client = _client_for(None)
    if client is None:
        return _redirect("/login?error=err.backend")
    try:
        result = client.auth.sign_in_with_password(
            {"email": email.strip(), "password": password}
        )
    except Exception as ex:
        return _redirect(f"/login?error={_friendly_auth_error(ex)}")

    session = result.session
    if session is None:
        return _redirect("/login?error=err.signin_failed")

    response = _redirect("/")
    response.set_cookie(
        COOKIE_NAME,
        dump_session(
            SessionTokens(
                access_token=session.access_token,
                refresh_token=session.refresh_token,
            )
        ),
        httponly=True,
        samesite="lax",
        # Set QUIZMONKEY_HTTPS=1 in production so the cookie is TLS-only.
        secure=os.environ.get("QUIZMONKEY_HTTPS") == "1",
        max_age=60 * 60 * 24 * 14,
        path="/",
    )
    return response


@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request, error: str | None = None):
    return _render(
        request,
        "register.html",
        error=error,
        configured=bool(SUPABASE_URL and SUPABASE_ANON_KEY and secret_configured()),
    )


@app.post("/register")
def register(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    privacy: str = Form(None),
):
    if not privacy:
        return _redirect("/register?error=err.privacy_required")

    client = _client_for(None)
    if client is None:
        return _redirect("/register?error=err.backend")
    try:
        # Everyone starts as a trainee. Becoming a trainer is a switch in the
        # settings — free for now, planned as a paid upgrade later.
        client.auth.sign_up(
            {
                "email": email.strip(),
                "password": password,
                "options": {
                    "data": {
                        "first_name": first_name.strip(),
                        "last_name": last_name.strip(),
                        "role": "trainee",
                    }
                },
            }
        )
    except Exception as ex:
        return _redirect(f"/register?error={_friendly_auth_error(ex)}")

    return _redirect(
        "/login?notice=msg.registered"
    )


@app.post("/logout")
def logout():
    response = _redirect("/login")
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@app.get("/settings", response_class=HTMLResponse)
def settings(request: Request, notice: str | None = None, error: str | None = None):
    _, profile = _current(request)
    if profile is None:
        return _redirect("/login")
    return _render(
        request, "settings.html", profile=profile, notice=notice, error=error
    )


@app.post("/settings/role")
def change_role(request: Request, role: str = Form(...)):
    client, profile = _current(request)
    if profile is None or client is None:
        return _redirect("/login")
    if role not in ("trainer", "trainee"):
        return _redirect("/settings?error=err.unknown_role")
    try:
        client.table("profiles").update(
            {"role": role, "active_view": role}
        ).eq("id", profile.id).execute()
    except Exception as ex:
        return _redirect(f"/settings?error=Could+not+save:+{ex}")
    return _redirect(f"/settings?notice=msg.role_{role}")


# ---------------------------------------------------------------------------
# Groups (trainer only)
#
# RLS already restricts every query to the signed-in trainer's own groups, so
# the _require_trainer gate here is about showing the right UI, not about
# security — the database is the real boundary.
# ---------------------------------------------------------------------------
def _require_trainer(request: Request):
    """(client, profile) for a trainer, or (None, None, redirect) otherwise."""
    client, profile = _current(request)
    if profile is None:
        return None, None, _redirect("/login")
    if not profile.is_trainer:
        return None, None, _redirect(
            "/settings?error=err.need_trainer"
        )
    return client, profile, None


@app.get("/groups", response_class=HTMLResponse)
def groups(request: Request, error: str | None = None, notice: str | None = None):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    try:
        rows = (
            client.table("groups")
            .select("id, name, created_at, group_members(count)")
            .eq("owner_id", profile.id)
            .order("created_at")
            .execute()
        )
    except Exception as ex:
        return _render(
            request, "groups.html", profile=profile, groups=[],
            error=f"Could not load groups: {ex}",
        )

    groups_data = []
    for g in rows.data or []:
        # Supabase returns the aggregate as [{"count": N}].
        count_field = g.get("group_members") or []
        member_count = count_field[0]["count"] if count_field else 0
        groups_data.append(
            {"id": g["id"], "name": g["name"], "member_count": member_count}
        )

    return _render(
        request, "groups.html", profile=profile, groups=groups_data,
        error=error, notice=notice,
    )


@app.post("/groups")
def create_group(request: Request, name: str = Form(...)):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    name = name.strip()
    if not name:
        return _redirect("/groups?error=err.group_name_required")
    try:
        client.table("groups").insert(
            {"name": name, "owner_id": profile.id}
        ).execute()
    except Exception as ex:
        return _redirect(f"/groups?error=Could+not+create+group:+{ex}")
    return _redirect("/groups?notice=msg.group_created")


@app.post("/groups/{group_id}/delete")
def delete_group(request: Request, group_id: str):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    try:
        client.table("groups").delete().eq("id", group_id).eq(
            "owner_id", profile.id
        ).execute()
    except Exception as ex:
        return _redirect(f"/groups?error=Could+not+delete:+{ex}")
    return _redirect("/groups?notice=msg.group_deleted")


@app.get("/groups/{group_id}", response_class=HTMLResponse)
def group_detail(
    request: Request, group_id: str,
    error: str | None = None, notice: str | None = None,
):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect

    try:
        grows = (
            client.table("groups")
            .select("id, name")
            .eq("id", group_id)
            .eq("owner_id", profile.id)
            .execute()
        )
    except Exception:
        grows = None
    if not grows or not grows.data:
        return _redirect("/groups?error=err.group_not_found")
    group = grows.data[0]

    try:
        mrows = (
            client.table("group_members")
            .select("id, email, status, user_id")
            .eq("group_id", group_id)
            .order("status")
            .execute()
        )
        members = mrows.data or []
    except Exception as ex:
        members = []
        error = error or f"Could not load members: {ex}"

    # Attach display names where the invitee already has a profile. A separate
    # lookup keeps this readable and stays within the RLS "fellow member" rule.
    ids = [m["user_id"] for m in members if m.get("user_id")]
    names: dict[str, str] = {}
    if ids:
        try:
            prows = (
                client.table("profiles")
                .select("id, first_name, last_name")
                .in_("id", ids)
                .execute()
            )
            for p in prows.data or []:
                full = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
                if full:
                    names[p["id"]] = full
        except Exception:
            pass
    for m in members:
        m["name"] = names.get(m.get("user_id") or "", "")

    # Which quizzes are released to this group? Two steps rather than an
    # embedded join keeps it within the plain RLS policies (owner reads shares,
    # owner reads own quizzes).
    shared_quizzes = []
    try:
        srows = (
            client.table("quiz_shares").select("quiz_id")
            .eq("group_id", group_id).execute()
        )
        quiz_ids = [r["quiz_id"] for r in (srows.data or [])]
        if quiz_ids:
            qrows = (
                client.table("quizzes").select("id, name")
                .in_("id", quiz_ids).order("name").execute()
            )
            shared_quizzes = qrows.data or []
    except Exception:
        pass

    return _render(
        request, "group_detail.html", profile=profile, group=group,
        members=members, shared_quizzes=shared_quizzes, error=error, notice=notice,
    )


@app.post("/groups/{group_id}/invite")
def invite_member(
    request: Request,
    group_id: str,
    background: BackgroundTasks,
    email: str = Form(...),
):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    email = email.strip().lower()
    if "@" not in email:
        return _redirect(
            f"/groups/{group_id}?error=err.invalid_email"
        )
    try:
        # If this person already has an account, link the invitation to it so
        # they see it immediately; otherwise the trigger links it on sign-up.
        prows = (
            client.table("profiles").select("id").eq("email", email).execute()
        )
        user_id = prows.data[0]["id"] if prows.data else None
        client.table("group_members").insert(
            {"group_id": group_id, "email": email, "user_id": user_id,
             "status": "invited"}
        ).execute()
    except Exception as ex:
        message = str(ex)
        if "duplicate key" in message or "unique" in message.lower():
            return _redirect(
                f"/groups/{group_id}?error=err.already_invited"
            )
        return _redirect(f"/groups/{group_id}?error=Could+not+invite:+{ex}")

    # Tell the invitee. Especially important for people without an account:
    # without this mail they have no way of knowing they should sign up.
    # Runs after the response so a slow mail server never delays the trainer,
    # and a failing send never breaks the invitation that is already stored.
    group_name = ""
    try:
        grow = (
            client.table("groups").select("name").eq("id", group_id).execute()
        )
        group_name = (grow.data[0]["name"] if grow.data else "") or ""
    except Exception:
        pass

    background.add_task(
        send_invitation_email, email, group_name, profile.display_name
    )

    if smtp_configured():
        notice = f"Invitation+sent+to+{email}."
    else:
        notice = (
            f"{email}+was+invited,+but+no+e-mail+was+sent+"
            "(SMTP+is+not+configured)."
        )
    return _redirect(f"/groups/{group_id}?notice={notice}")


# ---------------------------------------------------------------------------
# Quizzes: build in the browser, import CSV, export CSV, release to groups
# ---------------------------------------------------------------------------
@app.get("/quizzes", response_class=HTMLResponse)
def quizzes(request: Request, error: str | None = None, notice: str | None = None):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    try:
        rows = (
            client.table("quizzes")
            .select("id, name, csv, notes, created_at, updated_at")
            .eq("owner_id", profile.id)
            .order("created_at")
            .execute()
        )
    except Exception as ex:
        return _render(
            request, "quizzes.html", profile=profile, quizzes=[],
            error=f"Could not load quizzes: {ex}",
        )

    # Which groups is each quiz released to? One lookup for all of them, mapped
    # back per quiz. Group names come from the trainer's own groups.
    quiz_ids = [r["id"] for r in rows.data or []]
    shares_by_quiz: dict[str, list[str]] = {}
    try:
        grows = (
            client.table("groups").select("id, name")
            .eq("owner_id", profile.id).execute()
        )
        gname = {g["id"]: g["name"] for g in (grows.data or [])}
        if quiz_ids:
            srows = (
                client.table("quiz_shares").select("quiz_id, group_id")
                .in_("quiz_id", quiz_ids).execute()
            )
            for s in srows.data or []:
                name = gname.get(s["group_id"])
                if name:
                    shares_by_quiz.setdefault(s["quiz_id"], []).append(name)
    except Exception:
        pass

    items = []
    for r in rows.data or []:
        questions, _ = quiz_csv.parse(r.get("csv") or "")
        items.append({
            "id": r["id"], "name": r["name"],
            "count": len(questions), "notes": r.get("notes") or "",
            "groups": sorted(shares_by_quiz.get(r["id"], [])),
            "created": _fmt_dt(r.get("created_at")),
            "updated": _fmt_dt(r.get("updated_at")),
        })

    return _render(
        request, "quizzes.html", profile=profile, quizzes=items,
        error=error, notice=notice,
    )


@app.get("/quizzes/new", response_class=HTMLResponse)
def new_quiz(request: Request, error: str | None = None):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    return _render(request, "quiz_edit.html", profile=profile, quiz=None,
                   questions=[], error=error)


@app.get("/quiz-question-row", response_class=HTMLResponse)
def quiz_question_row(request: Request, index: int = 0):
    """One empty question block, fetched by htmx when adding a question."""
    return _render(request, "_question_row.html", index=index, question=None)


def _questions_from_form(form) -> tuple[list[quiz_csv.Question], list[str]]:
    """Rebuild questions from the repeated form fields of the editor."""
    questions: list[quiz_csv.Question] = []
    errors: list[str] = []

    indexes = sorted(
        {
            int(k.split("-")[1])
            for k in form.keys()
            if k.startswith("q-") and k.split("-")[1].isdigit()
        }
    )
    for i in indexes:
        text = (form.get(f"q-{i}-text") or "").strip()
        raw = [(form.get(f"q-{i}-a{n}") or "").strip() for n in range(1, 5)]
        answers = [a for a in raw if a]
        # Checkboxes: one or more answer slots (1..4) marked correct.
        selected = form.getlist(f"q-{i}-correct")

        if not text and not answers:
            continue  # untouched block
        position = len(questions) + 1
        if not text:
            errors.append(f"Question {position}: no question text.")
            continue
        if len(answers) < quiz_csv.MIN_ANSWERS:
            errors.append(
                f"Question {position}: needs at least {quiz_csv.MIN_ANSWERS} answers."
            )
            continue
        correct = []
        for s in selected:
            try:
                slot = int(s) - 1
            except (TypeError, ValueError):
                continue
            if 0 <= slot < quiz_csv.MAX_ANSWERS and raw[slot]:
                correct.append(raw[slot])
        if not correct:
            errors.append(
                f"Question {position}: mark which answer(s) are correct."
            )
            continue
        questions.append(
            quiz_csv.Question(text=text, answers=answers, correct=correct)
        )

    if not questions and not errors:
        errors.append("Add at least one question.")
    return questions, errors


@app.post("/quizzes")
async def create_quiz(request: Request):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    form = await request.form()
    name = (form.get("name") or "").strip()
    notes = (form.get("notes") or "").strip()
    quiz_id = (form.get("quiz_id") or "").strip()

    questions, errors = _questions_from_form(form)
    if not name:
        errors.insert(0, "Give the quiz a name.")
    if errors:
        quiz_ctx = {"name": name, "notes": notes}
        if quiz_id:
            quiz_ctx["id"] = quiz_id
        return _render(
            request, "quiz_edit.html", profile=profile,
            quiz=quiz_ctx, questions=questions, error=" ".join(errors),
        )

    payload = {
        "name": name,
        "notes": notes or None,
        "csv": quiz_csv.serialise(questions),
    }
    try:
        if quiz_id:
            client.table("quizzes").update(payload).eq("id", quiz_id).execute()
        else:
            payload["owner_id"] = profile.id
            client.table("quizzes").insert(payload).execute()
    except Exception as ex:
        return _redirect(f"/quizzes?error=Could+not+save:+{ex}")
    return _redirect("/quizzes?notice=msg.quiz_saved")


@app.get("/quizzes/{quiz_id}", response_class=HTMLResponse)
def edit_quiz(request: Request, quiz_id: str, error: str | None = None,
              notice: str | None = None):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    try:
        rows = (
            client.table("quizzes").select("id, name, csv, notes")
            .eq("id", quiz_id).execute()
        )
    except Exception as ex:
        return _redirect(f"/quizzes?error=Could+not+open:+{ex}")
    if not rows.data:
        return _redirect("/quizzes?error=err.quiz_not_found")

    quiz = rows.data[0]
    questions, parse_errors = quiz_csv.parse(quiz.get("csv") or "")

    # Releasing to groups lives on its own page now (/quizzes/{id}/release).
    return _render(
        request, "quiz_edit.html", profile=profile, quiz=quiz,
        questions=questions,
        error=error or (" ".join(parse_errors) if parse_errors else None),
        notice=notice,
    )


@app.get("/quizzes/{quiz_id}/release", response_class=HTMLResponse)
def release_quiz_page(request: Request, quiz_id: str, error: str | None = None,
                      notice: str | None = None):
    """Releasing a quiz to groups lives on its own page, separate from the
    (potentially very long) quiz editor."""
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    try:
        rows = (
            client.table("quizzes").select("id, name, notes")
            .eq("id", quiz_id).execute()
        )
    except Exception as ex:
        return _redirect(f"/quizzes?error=Could+not+open:+{ex}")
    if not rows.data:
        return _redirect("/quizzes?error=err.quiz_not_found")
    quiz = rows.data[0]

    groups_all, shared_ids = [], set()
    try:
        grows = (
            client.table("groups").select("id, name")
            .eq("owner_id", profile.id).order("name").execute()
        )
        groups_all = grows.data or []
        srows = (
            client.table("quiz_shares").select("group_id")
            .eq("quiz_id", quiz_id).execute()
        )
        shared_ids = {r["group_id"] for r in (srows.data or [])}
    except Exception:
        pass

    return _render(
        request, "quiz_release.html", profile=profile, quiz=quiz,
        groups=groups_all, shared_ids=shared_ids, error=error, notice=notice,
    )


@app.get("/quizzes/{quiz_id}/export")
def export_quiz(request: Request, quiz_id: str):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    try:
        rows = (
            client.table("quizzes").select("name, csv")
            .eq("id", quiz_id).execute()
        )
    except Exception as ex:
        return _redirect(f"/quizzes?error=Could+not+export:+{ex}")
    if not rows.data:
        return _redirect("/quizzes?error=err.quiz_not_found")

    quiz = rows.data[0]
    safe = "".join(
        c for c in quiz["name"] if c.isalnum() or c in (" ", "-", "_")
    ).strip() or "quiz"
    # UTF-8 BOM so Excel opens the umlauts correctly.
    body = "﻿" + (quiz.get("csv") or "")
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe}.csv"'},
    )


@app.post("/quizzes/import")
async def import_quiz(request: Request, file: UploadFile = File(...),
                      name: str = Form(""), notes: str = Form("")):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect

    raw = await file.read()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        return _redirect("/quizzes?error=err.encoding")

    questions, errors = quiz_csv.parse(text)
    if errors:
        first = errors[0]
        more = f"+(and+{len(errors) - 1}+more)" if len(errors) > 1 else ""
        return _redirect(f"/quizzes?error={first}{more}".replace(" ", "+"))

    quiz_name = name.strip() or Path(file.filename or "Imported quiz").stem
    try:
        client.table("quizzes").insert(
            {
                "owner_id": profile.id,
                "name": quiz_name,
                "notes": notes.strip() or None,
                "csv": quiz_csv.serialise(questions),
            }
        ).execute()
    except Exception as ex:
        return _redirect(f"/quizzes?error=Could+not+save:+{ex}")
    return _redirect("/quizzes?notice=msg.imported")


@app.post("/quizzes/{quiz_id}/delete")
def delete_quiz(request: Request, quiz_id: str):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    try:
        client.table("quizzes").delete().eq("id", quiz_id).execute()
    except Exception as ex:
        return _redirect(f"/quizzes?error=Could+not+delete:+{ex}")
    return _redirect("/quizzes?notice=msg.quiz_deleted")


@app.post("/quizzes/{quiz_id}/share")
def share_quiz(request: Request, quiz_id: str, group_id: str = Form(...),
               shared: str = Form(None)):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    try:
        if shared:
            client.table("quiz_shares").insert(
                {"quiz_id": quiz_id, "group_id": group_id}
            ).execute()
            message = "msg.quiz_released"
        else:
            client.table("quiz_shares").delete().eq("quiz_id", quiz_id).eq(
                "group_id", group_id
            ).execute()
            message = "msg.quiz_withdrawn"
    except Exception as ex:
        return _redirect(
            f"/quizzes/{quiz_id}/release?error=Could+not+change+sharing:+{ex}"
        )
    return _redirect(f"/quizzes/{quiz_id}/release?notice={message}")


@app.post("/groups/{group_id}/members/{member_id}/remove")
def remove_member(request: Request, group_id: str, member_id: str):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    try:
        client.table("group_members").delete().eq("id", member_id).eq(
            "group_id", group_id
        ).execute()
    except Exception as ex:
        return _redirect(f"/groups/{group_id}?error=Could+not+remove:+{ex}")
    return _redirect(f"/groups/{group_id}?notice=msg.member_removed")


# ---------------------------------------------------------------------------
# Tests (formal assessments). Stage 2: the trainer builds and manages them.
# Taking a test (server-side drawing + scoring) comes in a later stage.
# ---------------------------------------------------------------------------
def _trainer_quizzes(client, profile) -> list[dict]:
    """The trainer's quizzes as {id, name, count} — the pickable test sources."""
    try:
        rows = (
            client.table("quizzes").select("id, name, csv")
            .eq("owner_id", profile.id).order("name").execute()
        )
    except Exception:
        return []
    out = []
    for r in rows.data or []:
        questions, _ = quiz_csv.parse(r.get("csv") or "")
        out.append({"id": r["id"], "name": r["name"], "count": len(questions)})
    return out


def _trainer_quizzes_full(client, profile) -> list[dict]:
    """Like _trainer_quizzes but with each quiz's questions, for the manual
    question picker: {id, name, questions: [{index, text}]}."""
    try:
        rows = (
            client.table("quizzes").select("id, name, csv")
            .eq("owner_id", profile.id).order("name").execute()
        )
    except Exception:
        return []
    out = []
    for r in rows.data or []:
        questions, _ = quiz_csv.parse(r.get("csv") or "")
        out.append({
            "id": r["id"], "name": r["name"],
            "questions": [{"index": i, "text": q.text} for i, q in enumerate(questions)],
        })
    return out


def _parse_quizzes_by_id(client, profile, quiz_ids: list[str]) -> dict[str, list]:
    """Parsed questions for the given quiz ids owned by this trainer."""
    if not quiz_ids:
        return {}
    rows = (
        client.table("quizzes").select("id, csv")
        .eq("owner_id", profile.id).in_("id", quiz_ids).execute()
    )
    return {r["id"]: quiz_csv.parse(r.get("csv") or "")[0] for r in (rows.data or [])}


@app.get("/tests", response_class=HTMLResponse)
def tests(request: Request, error: str | None = None, notice: str | None = None):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    try:
        rows = (
            client.table("tests")
            .select("id, name, notes, pass_percent, max_attempts, question_count, "
                    "selection_mode, time_limit_seconds, created_at, updated_at")
            .eq("owner_id", profile.id).order("created_at").execute()
        )
    except Exception as ex:
        return _render(request, "tests.html", profile=profile, tests=[],
                       error=f"Could not load tests: {ex}")

    test_ids = [r["id"] for r in rows.data or []]
    shares_by_test: dict[str, list[str]] = {}
    try:
        grows = (
            client.table("groups").select("id, name")
            .eq("owner_id", profile.id).execute()
        )
        gname = {g["id"]: g["name"] for g in (grows.data or [])}
        if test_ids:
            srows = (
                client.table("test_shares").select("test_id, group_id")
                .in_("test_id", test_ids).execute()
            )
            for s in srows.data or []:
                name = gname.get(s["group_id"])
                if name:
                    shares_by_test.setdefault(s["test_id"], []).append(name)
    except Exception:
        pass

    items = []
    for r in rows.data or []:
        secs = r.get("time_limit_seconds")
        items.append({
            **r,
            "groups": sorted(shares_by_test.get(r["id"], [])),
            "created": _fmt_dt(r.get("created_at")),
            "updated": _fmt_dt(r.get("updated_at")),
            "time_limit_min": (secs // 60) if secs else 0,
        })
    return _render(request, "tests.html", profile=profile, tests=items,
                   error=error, notice=notice)


@app.get("/tests/new", response_class=HTMLResponse)
def new_test(request: Request, error: str | None = None):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    return _render(request, "test_edit.html", profile=profile,
                   quizzes=_trainer_quizzes(client, profile),
                   quizzes_full=_trainer_quizzes_full(client, profile),
                   form=None, picked=[], editing=False, error=error)


@app.get("/tests/{test_id}/edit", response_class=HTMLResponse)
def edit_test(request: Request, test_id: str, error: str | None = None):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    rows = (
        client.table("tests").select("*")
        .eq("id", test_id).eq("owner_id", profile.id).execute().data
    )
    if not rows:
        return _redirect("/tests?error=err.test_not_found")
    t = rows[0]

    secs = t.get("time_limit_seconds")
    form = {
        "test_id": t["id"], "name": t["name"], "notes": t.get("notes") or "",
        "pass_percent": str(t["pass_percent"]), "max_attempts": str(t["max_attempts"]),
        "question_count": str(t["question_count"]),
        "selection_mode": t["selection_mode"], "retry_mode": t["retry_mode"],
        "draw_scope": t["draw_scope"],
        "time_limit_min": str(secs // 60) if secs else "",
    }

    quizzes_full = _trainer_quizzes_full(client, profile)
    picked: set[str] = set()

    if t["selection_mode"] == "random":
        srows = (
            client.table("test_sources").select("quiz_id, weight_percent")
            .eq("test_id", test_id).execute().data or []
        )
        for s in srows:
            form[f"weight-{s['quiz_id']}"] = str(s["weight_percent"])
    else:
        # Manual: match the frozen questions back to their quiz + index by text,
        # so the original picks come back checked. Snapshots don't store the
        # source reference, so this is best-effort (first match on prompt wins).
        prompt_lookup: dict[str, str] = {}
        for q in quizzes_full:
            for item in q["questions"]:
                prompt_lookup.setdefault(item["text"], f"{q['id']}:{item['index']}")
        qrows = (
            client.table("test_questions").select("prompt")
            .eq("test_id", test_id).execute().data or []
        )
        for qq in qrows:
            token = prompt_lookup.get(qq["prompt"])
            if token:
                picked.add(token)

    return _render(request, "test_edit.html", profile=profile,
                   quizzes=_trainer_quizzes(client, profile),
                   quizzes_full=quizzes_full, form=form, picked=picked,
                   editing=True, error=error)


def _clear_test_children(client, test_id: str) -> None:
    """Drop a test's composition rows so an edit can rebuild them."""
    for table in ("test_sources", "test_questions", "test_pool"):
        client.table(table).delete().eq("test_id", test_id).execute()


def _save_test_row(client, profile, test_id: str, payload: dict) -> str:
    """Insert a new test, or update an existing one (and clear its old
    composition rows). Returns the test id to build children under."""
    if test_id:
        client.table("tests").update(payload).eq("id", test_id).eq(
            "owner_id", profile.id
        ).execute()
        _clear_test_children(client, test_id)
        return test_id
    row = {**payload, "owner_id": profile.id}
    return client.table("tests").insert(row).execute().data[0]["id"]


@app.post("/tests")
async def create_test(request: Request):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    form = await request.form()

    def as_int(key: str, default: int = 0) -> int:
        try:
            return int((form.get(key) or "").strip())
        except ValueError:
            return default

    name = (form.get("name") or "").strip()
    notes = (form.get("notes") or "").strip()
    test_id = (form.get("test_id") or "").strip()
    pass_percent = as_int("pass_percent", 60)
    max_attempts = as_int("max_attempts", 1)
    question_count = as_int("question_count", 0)
    retry_mode = form.get("retry_mode") or "new"
    draw_scope = form.get("draw_scope") or "per_trainee"
    tl_min = (form.get("time_limit_min") or "").strip()
    time_limit_seconds = int(tl_min) * 60 if tl_min.isdigit() and int(tl_min) > 0 else None

    selection_mode = form.get("selection_mode") or "random"

    def rerender(errs: list[str]):
        return _render(
            request, "test_edit.html", profile=profile,
            quizzes=_trainer_quizzes(client, profile),
            quizzes_full=_trainer_quizzes_full(client, profile),
            form=dict(form), picked=set(form.getlist("pick")),
            editing=bool(test_id), error=" ".join(errs),
        )

    errors: list[str] = []
    if not name:
        errors.append("Give the test a name.")
    if pass_percent < 0 or pass_percent > 100:
        errors.append("Pass percentage must be between 0 and 100.")
    if max_attempts < 1:
        errors.append("Allow at least one attempt.")

    # ----- manual: the trainer hand-picks questions across quizzes -----
    if selection_mode == "manual":
        pairs: list[tuple[str, int]] = []
        for token in form.getlist("pick"):
            qid, _, idx = token.rpartition(":")
            if qid and idx.isdigit():
                pairs.append((qid, int(idx)))
        if not pairs:
            errors.append("Pick at least one question.")
        parsed = _parse_quizzes_by_id(client, profile, list({q for q, _ in pairs}))
        questions = []
        for qid, idx in pairs:
            qs = parsed.get(qid) or []
            if 0 <= idx < len(qs):
                questions.append(qs[idx])
        if pairs and not questions:
            errors.append("The picked questions could not be found.")
        if errors:
            return rerender(errors)
        payload = {
            "name": name, "notes": notes or None, "pass_percent": pass_percent,
            "max_attempts": max_attempts, "selection_mode": "manual",
            "question_count": len(questions), "retry_mode": "same",
            "draw_scope": "fixed", "time_limit_seconds": time_limit_seconds,
        }
        try:
            tid = _save_test_row(client, profile, test_id, payload)
            client.table("test_questions").insert([
                {"test_id": tid, "position": p, **test_build.question_to_row(q)}
                for p, q in enumerate(questions)
            ]).execute()
        except Exception as ex:
            return _redirect(f"/tests?error=Could+not+save+test:+{ex}")
        return _redirect(f"/tests?notice={'msg.test_saved' if test_id else 'msg.test_created'}")

    # ----- random: weighted draw across quizzes -----
    chosen: list[tuple[str, int]] = []
    for key in form.keys():
        if key.startswith("weight-"):
            try:
                w = int(form.get(key) or 0)
            except ValueError:
                w = 0
            if w > 0:
                chosen.append((key[len("weight-"):], w))

    if question_count < 1:
        errors.append("Set how many questions the test has.")
    if not chosen:
        errors.append("Pick at least one quiz and give it a weight.")
    elif sum(w for _, w in chosen) != 100:
        errors.append("The weights of the chosen quizzes must add up to 100%.")

    parsed = {}
    qmap: dict[str, dict] = {}
    if chosen and not errors:
        qrows = (
            client.table("quizzes").select("id, name, csv")
            .eq("owner_id", profile.id)
            .in_("id", [qid for qid, _ in chosen]).execute()
        )
        qmap = {r["id"]: r for r in (qrows.data or [])}
        for qid, _ in chosen:
            row = qmap.get(qid)
            if not row:
                errors.append("A selected quiz could not be found.")
                continue
            parsed[qid] = quiz_csv.parse(row.get("csv") or "")[0]

    targets: list[int] = []
    if chosen and not errors:
        targets = test_build.allocate([w for _, w in chosen], question_count)
        for (qid, _), t in zip(chosen, targets):
            avail = len(parsed.get(qid, []))
            if t > avail:
                errors.append(
                    f"{qmap[qid]['name']}: needs {t} question(s) but only has {avail}."
                )

    if errors:
        return rerender(errors)

    payload = {
        "name": name, "notes": notes or None, "pass_percent": pass_percent,
        "max_attempts": max_attempts, "selection_mode": "random",
        "question_count": question_count, "retry_mode": retry_mode,
        "draw_scope": draw_scope, "time_limit_seconds": time_limit_seconds,
    }
    try:
        tid = _save_test_row(client, profile, test_id, payload)

        client.table("test_sources").insert([
            {"test_id": tid, "quiz_id": qid, "weight_percent": w,
             "target_count": targets[i], "source_no": i}
            for i, (qid, w) in enumerate(chosen)
        ]).execute()

        if draw_scope == "fixed":
            # Freeze one shared set now.
            picked = []
            for i, (qid, _) in enumerate(chosen):
                picked.extend(test_build.draw(parsed[qid], targets[i]))
            random.shuffle(picked)
            client.table("test_questions").insert([
                {"test_id": tid, "position": p, **test_build.question_to_row(q)}
                for p, q in enumerate(picked)
            ]).execute()
        else:
            # Store the full candidate pool; the server draws per trainee later.
            pool = []
            for i, (qid, _) in enumerate(chosen):
                for q in parsed[qid]:
                    pool.append({"test_id": tid, "source_no": i,
                                 **test_build.question_to_row(q)})
            if pool:
                client.table("test_pool").insert(pool).execute()
    except Exception as ex:
        return _redirect(f"/tests?error=Could+not+save+test:+{ex}")
    return _redirect(f"/tests?notice={'msg.test_saved' if test_id else 'msg.test_created'}")


@app.post("/tests/{test_id}/delete")
def delete_test(request: Request, test_id: str):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    try:
        client.table("tests").delete().eq("id", test_id).eq(
            "owner_id", profile.id
        ).execute()
    except Exception as ex:
        return _redirect(f"/tests?error=Could+not+delete:+{ex}")
    return _redirect("/tests?notice=msg.test_deleted")


@app.get("/tests/{test_id}/release", response_class=HTMLResponse)
def release_test_page(request: Request, test_id: str, error: str | None = None,
                      notice: str | None = None):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    try:
        rows = client.table("tests").select("id, name").eq("id", test_id).execute()
    except Exception as ex:
        return _redirect(f"/tests?error=Could+not+open:+{ex}")
    if not rows.data:
        return _redirect("/tests?error=err.test_not_found")
    test = rows.data[0]

    groups_all, shared_ids = [], set()
    try:
        grows = (
            client.table("groups").select("id, name")
            .eq("owner_id", profile.id).order("name").execute()
        )
        groups_all = grows.data or []
        srows = (
            client.table("test_shares").select("group_id")
            .eq("test_id", test_id).execute()
        )
        shared_ids = {r["group_id"] for r in (srows.data or [])}
    except Exception:
        pass

    return _render(request, "test_release.html", profile=profile, test=test,
                   groups=groups_all, shared_ids=shared_ids,
                   error=error, notice=notice)


@app.post("/tests/{test_id}/share")
def share_test(request: Request, test_id: str, group_id: str = Form(...),
               shared: str = Form(None)):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    try:
        if shared:
            client.table("test_shares").insert(
                {"test_id": test_id, "group_id": group_id}
            ).execute()
            message = "msg.test_released"
        else:
            client.table("test_shares").delete().eq("test_id", test_id).eq(
                "group_id", group_id
            ).execute()
            message = "msg.test_withdrawn"
    except Exception as ex:
        return _redirect(f"/tests/{test_id}/release?error=Could+not+change+sharing:+{ex}")
    return _redirect(f"/tests/{test_id}/release?notice={message}")


@app.get("/tests/{test_id}/results", response_class=HTMLResponse)
def test_results(request: Request, test_id: str, error: str | None = None,
                 notice: str | None = None):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    trows = (
        client.table("tests").select("id, name, pass_percent, max_attempts")
        .eq("id", test_id).eq("owner_id", profile.id).execute().data
    )
    if not trows:
        return _redirect("/tests?error=err.test_not_found")
    test = trows[0]

    attempts = (
        client.table("test_attempts")
        .select("user_id, attempt_no, status, score_percent, passed")
        .eq("test_id", test_id).execute().data or []
    )
    uids = list({a["user_id"] for a in attempts})
    names: dict[str, str] = {}
    if uids:
        prows = (
            client.table("profiles").select("id, first_name, last_name, email")
            .in_("id", uids).execute().data or []
        )
        for p in prows:
            full = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
            names[p["id"]] = full or p.get("email", "")

    by_user: dict[str, dict] = {}
    for a in attempts:
        if a["status"] != "completed":
            continue
        u = by_user.setdefault(a["user_id"], {
            "attempts": 0, "passed": False, "passed_attempt": None, "best": None,
        })
        u["attempts"] += 1
        sp = a["score_percent"] or 0
        u["best"] = sp if u["best"] is None else max(u["best"], sp)
        if a["passed"] and not u["passed"]:
            u["passed"] = True
            u["passed_attempt"] = a["attempt_no"]

    results = []
    for uid, v in by_user.items():
        results.append({
            "user_id": uid, "name": names.get(uid, uid),
            "attempts": v["attempts"], "passed": v["passed"],
            "passed_attempt": v["passed_attempt"], "best": v["best"],
            "locked": (not v["passed"]) and v["attempts"] >= test["max_attempts"],
        })
    results.sort(key=lambda r: r["name"].lower())

    return _render(request, "test_results.html", profile=profile, test=test,
                   results=results, error=error, notice=notice)


@app.post("/tests/{test_id}/results/{user_id}/reset")
def reset_attempts(request: Request, test_id: str, user_id: str):
    client, profile, redirect = _require_trainer(request)
    if redirect is not None:
        return redirect
    owned = (
        client.table("tests").select("id")
        .eq("id", test_id).eq("owner_id", profile.id).execute().data
    )
    if not owned:
        return _redirect("/tests?error=err.test_not_found")
    svc = _service_client()
    if svc is None:
        return _redirect(f"/tests/{test_id}/results?error=err.tests_not_configured")
    try:
        svc.table("test_attempts").delete().eq("test_id", test_id).eq(
            "user_id", user_id
        ).execute()
    except Exception as ex:
        return _redirect(f"/tests/{test_id}/results?error=Could+not+reset:+{ex}")
    return _redirect(f"/tests/{test_id}/results?notice=msg.attempts_reset")


# ---------------------------------------------------------------------------
# Taking a test (trainee). Drawing and scoring run on the server so the answer
# key never reaches the client — see test_take.py. Needs the service key.
# ---------------------------------------------------------------------------
_TEST_TAKE_FIELDS = (
    "id, name, pass_percent, max_attempts, question_count, selection_mode, "
    "draw_scope, retry_mode, time_limit_seconds, owner_id"
)


def _visible_test(user_client, test_id: str) -> dict | None:
    """A test the current user may take (RLS: owns it, or it's shared)."""
    if user_client is None:
        return None
    try:
        rows = (
            user_client.table("tests").select(_TEST_TAKE_FIELDS)
            .eq("id", test_id).execute().data
        )
    except Exception:
        return None
    return rows[0] if rows else None


@app.get("/take", response_class=HTMLResponse)
def take_list(request: Request, error: str | None = None, notice: str | None = None):
    user_client, profile = _current(request)
    if profile is None:
        return _redirect("/login")
    svc = _service_client()
    rows = []
    try:
        rows = (
            user_client.table("tests")
            .select(_TEST_TAKE_FIELDS).neq("owner_id", profile.id)
            .order("name").execute().data or []
        )
    except Exception as ex:
        error = error or f"Could not load tests: {ex}"

    items = []
    for t in rows:
        secs = t.get("time_limit_seconds")
        items.append({
            **t,
            "status": test_take.attempt_status(svc, t, profile.id) if svc else None,
            "time_limit_min": (secs // 60) if secs else 0,
        })
    return _render(request, "take_list.html", profile=profile, tests=items,
                   configured=svc is not None, error=error, notice=notice)


@app.get("/take/{test_id}", response_class=HTMLResponse)
def take_intro(request: Request, test_id: str, error: str | None = None):
    user_client, profile = _current(request)
    if profile is None:
        return _redirect("/login")
    t = _visible_test(user_client, test_id)
    if not t:
        return _redirect("/take?error=err.test_not_found")
    svc = _service_client()
    secs = t.get("time_limit_seconds")
    t = {**t, "time_limit_min": (secs // 60) if secs else 0}
    status = test_take.attempt_status(svc, t, profile.id) if svc else None
    return _render(request, "take_intro.html", profile=profile, test=t,
                   status=status, configured=svc is not None, error=error)


@app.post("/take/{test_id}/start")
def take_start(request: Request, test_id: str):
    user_client, profile = _current(request)
    if profile is None:
        return _redirect("/login")
    t = _visible_test(user_client, test_id)
    if not t:
        return _redirect("/take?error=err.test_not_found")
    svc = _service_client()
    if svc is None:
        return _redirect(f"/take/{test_id}?error=err.tests_not_configured")
    try:
        attempt = test_take.start_attempt(svc, t, profile.id)
    except test_take.TakeError as e:
        return _redirect(f"/take/{test_id}?error={e.key}")
    return _redirect(f"/take/attempt/{attempt['id']}")


@app.get("/take/attempt/{attempt_id}", response_class=HTMLResponse)
def take_run(request: Request, attempt_id: str):
    user_client, profile = _current(request)
    if profile is None:
        return _redirect("/login")
    svc = _service_client()
    if svc is None:
        return _redirect("/take?error=err.tests_not_configured")
    try:
        attempt = test_take.load_running_attempt(svc, attempt_id, profile.id)
    except test_take.TakeError as e:
        if e.key == "err.attempt_done":
            return _redirect(f"/take/attempt/{attempt_id}/result")
        return _redirect(f"/take?error={e.key}")

    t = _visible_test(user_client, attempt["test_id"])
    remaining = None
    secs = t.get("time_limit_seconds") if t else None
    if secs:
        started = _parse_iso(attempt["started_at"])
        if started is not None:
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            remaining = max(0, int(secs - elapsed))
    return _render(request, "take_run.html", profile=profile, test=t,
                   attempt=attempt, remaining=remaining)


@app.post("/take/attempt/{attempt_id}/submit")
async def take_submit(request: Request, attempt_id: str):
    user_client, profile = _current(request)
    if profile is None:
        return _redirect("/login")
    svc = _service_client()
    if svc is None:
        return _redirect("/take?error=err.tests_not_configured")
    try:
        running = test_take.load_running_attempt(svc, attempt_id, profile.id)
    except test_take.TakeError as e:
        if e.key == "err.attempt_done":
            return _redirect(f"/take/attempt/{attempt_id}/result")
        return _redirect(f"/take?error={e.key}")

    t = _visible_test(user_client, running["test_id"])
    if not t:
        return _redirect("/take?error=err.test_not_found")

    form = await request.form()
    # Each question may have one (radio) or several (checkbox) selected answers.
    idxs = {k[2:] for k in form.keys() if k.startswith("a-") and k[2:].isdigit()}
    answers = {i: form.getlist(f"a-{i}") for i in idxs}
    try:
        test_take.score_attempt(svc, attempt_id, profile.id, answers, t)
    except test_take.TakeError as e:
        return _redirect(f"/take?error={e.key}")
    return _redirect(f"/take/attempt/{attempt_id}/result")


@app.get("/take/attempt/{attempt_id}/result", response_class=HTMLResponse)
def take_result(request: Request, attempt_id: str):
    user_client, profile = _current(request)
    if profile is None:
        return _redirect("/login")
    svc = _service_client()
    if svc is None:
        return _redirect("/take?error=err.tests_not_configured")
    rows = (
        svc.table("test_attempts").select("*").eq("id", attempt_id).execute().data
    )
    if not rows or rows[0]["user_id"] != profile.id:
        return _redirect("/take?error=err.attempt_not_found")
    a = rows[0]
    if a["status"] != "completed":
        return _redirect(f"/take/attempt/{attempt_id}")
    t = _visible_test(user_client, a["test_id"])
    status = test_take.attempt_status(svc, t, profile.id) if t else None
    return _render(request, "take_result.html", profile=profile, test=t,
                   percent=a["score_percent"], passed=a["passed"],
                   attempt_no=a["attempt_no"], status=status)


# ---------------------------------------------------------------------------
# JSON API for the mobile app to take tests. Same server-side drawing and
# scoring as the browser flow, so the answer key never reaches the device. The
# app authenticates with its Supabase access token as a Bearer header.
# ---------------------------------------------------------------------------
def _bearer(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    return auth[7:].strip() if auth.lower().startswith("bearer ") else None


def _api_client_and_uid(token: str | None):
    """A user-scoped Supabase client and the user id for a Bearer token."""
    if not token or create_client is None or not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return None, None
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    try:
        user = client.auth.get_user(token)
    except Exception:
        return None, None
    if user is None or user.user is None:
        return None, None
    # Scope PostgREST queries to this user so RLS applies.
    client.postgrest.auth(token)
    return client, user.user.id


@app.get("/api/tests")
def api_tests(request: Request):
    client, uid = _api_client_and_uid(_bearer(request))
    if not uid:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    svc = _service_client()
    if svc is None:
        return JSONResponse({"error": "tests_not_configured"}, status_code=503)
    try:
        rows = (
            client.table("tests").select(_TEST_TAKE_FIELDS)
            .neq("owner_id", uid).order("name").execute().data or []
        )
    except Exception as ex:
        return JSONResponse({"error": str(ex)}, status_code=500)
    out = []
    for t in rows:
        st = test_take.attempt_status(svc, t, uid)
        out.append({
            "id": t["id"], "name": t["name"], "pass_percent": t["pass_percent"],
            "question_count": t["question_count"], "max_attempts": t["max_attempts"],
            "time_limit_seconds": t.get("time_limit_seconds"),
            "passed": st["passed"], "locked": st["locked"], "used": st["used"],
            "attempts_left": st["attempts_left"], "best": st["best"],
            "done": st["done"], "in_progress": bool(st["in_progress"]),
        })
    return {"tests": out}


@app.post("/api/tests/{test_id}/start")
def api_start(request: Request, test_id: str):
    client, uid = _api_client_and_uid(_bearer(request))
    if not uid:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    t = _visible_test(client, test_id)
    if not t:
        return JSONResponse({"error": "test_not_found"}, status_code=404)
    svc = _service_client()
    if svc is None:
        return JSONResponse({"error": "tests_not_configured"}, status_code=503)
    try:
        attempt = test_take.start_attempt(svc, t, uid)
    except test_take.TakeError as e:
        return JSONResponse({"error": e.key}, status_code=409)

    secs = t.get("time_limit_seconds")
    remaining = None
    if secs:
        started = _parse_iso(attempt["started_at"])
        if started is not None:
            remaining = max(0, int(secs - (datetime.now(timezone.utc) - started).total_seconds()))
    return {
        "attempt_id": attempt["id"], "attempt_no": attempt["attempt_no"],
        "name": t["name"], "pass_percent": t["pass_percent"],
        "time_limit_seconds": secs, "remaining_seconds": remaining,
        "questions": attempt["questions"],
    }


@app.post("/api/attempts/{attempt_id}/submit")
async def api_submit(request: Request, attempt_id: str):
    client, uid = _api_client_and_uid(_bearer(request))
    if not uid:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    svc = _service_client()
    if svc is None:
        return JSONResponse({"error": "tests_not_configured"}, status_code=503)
    try:
        running = test_take.load_running_attempt(svc, attempt_id, uid)
    except test_take.TakeError as e:
        return JSONResponse({"error": e.key}, status_code=409)
    t = _visible_test(client, running["test_id"])
    if not t:
        return JSONResponse({"error": "test_not_found"}, status_code=404)
    try:
        body = await request.json()
    except Exception:
        body = {}
    # Accept either a single value or a list per question; normalise to lists.
    answers = {}
    for k, v in (body.get("answers") or {}).items():
        answers[str(k)] = v if isinstance(v, list) else ([v] if v else [])
    try:
        result = test_take.score_attempt(svc, attempt_id, uid, answers, t)
    except test_take.TakeError as e:
        return JSONResponse({"error": e.key}, status_code=409)
    return result


# ---------------------------------------------------------------------------
# Legal pages (Art. 13 GDPR / § 5 ECG)
# ---------------------------------------------------------------------------
@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    _, profile = _current(request)
    return _render(request, "privacy.html", profile=profile)


@app.get("/imprint", response_class=HTMLResponse)
def imprint(request: Request):
    _, profile = _current(request)
    return _render(request, "imprint.html", profile=profile)


@app.post("/language")
def set_language(request: Request, lang: str = Form(...), next: str = Form("/")):
    """Switch the interface language.

    Stores only the two-letter code, no identifier — a strictly necessary
    preference cookie, so no consent banner is required.
    """
    if lang not in LANGUAGES:
        lang = "de"
    # Only ever redirect within this site.
    target = next if next.startswith("/") and not next.startswith("//") else "/"
    response = _redirect(target)
    response.set_cookie(
        LANG_COOKIE,
        lang,
        max_age=60 * 60 * 24 * 365,
        samesite="lax",
        secure=os.environ.get("QUIZMONKEY_HTTPS") == "1",
        path="/",
    )
    return response


@app.post("/theme")
def set_theme(request: Request, theme: str = Form(...), next: str = Form("/")):
    """Switch between the light and dark appearance.

    Same shape as the language switch: a two-value preference cookie with no
    identifier, strictly necessary for the interface to look as the user asked,
    so it needs no consent banner either. Rendering happens server-side via
    data-theme on <html>, which keeps it working under the strict CSP with no
    JavaScript and no flash of the wrong theme.
    """
    if theme not in THEMES:
        theme = DEFAULT_THEME
    target = next if next.startswith("/") and not next.startswith("//") else "/"
    response = _redirect(target)
    response.set_cookie(
        THEME_COOKIE,
        theme,
        max_age=60 * 60 * 24 * 365,
        samesite="lax",
        secure=os.environ.get("QUIZMONKEY_HTTPS") == "1",
        path="/",
    )
    return response


@app.get("/health")
def health() -> Response:
    return Response("ok", media_type="text/plain")
