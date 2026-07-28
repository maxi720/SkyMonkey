"""Outgoing e-mail for QuizMonkey (invitation notifications).

Provider-agnostic SMTP so it works with anything: a GMX/Gmail account, a mail
server on your own domain, or an EU transactional provider (e.g. Mailjet). If
SMTP is not configured, sending is a no-op and the invitation still works — the
trainee can be told in person, or accept once they open the app.

Config (all from the environment / .env):
    SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD,
    SMTP_FROM (defaults to SMTP_USER), SMTP_STARTTLS (default "1"),
    PUBLIC_BASE_URL (used to build links in the e-mail).

GDPR note: sending this one transactional message to the address the trainer
entered is covered by legitimate interest / contract initiation. Whichever SMTP
provider you use becomes a processor and must be named in the privacy policy
and covered by an Art. 28 agreement.
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

log = logging.getLogger("quizmonkey.email")


def smtp_configured() -> bool:
    return bool(
        os.environ.get("SMTP_HOST")
        and os.environ.get("SMTP_USER")
        and os.environ.get("SMTP_PASSWORD")
    )


def _base_url() -> str:
    return os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")


def send_invitation_email(
    to_email: str, group_name: str, trainer_name: str
) -> None:
    """Best-effort invitation notice. Never raises: a failed send must not
    break the invitation, which is already stored in the database.

    Run this from a background task — smtplib is synchronous.
    """
    if not smtp_configured():
        return

    host = os.environ["SMTP_HOST"].strip()
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"].strip()
    password = os.environ["SMTP_PASSWORD"]
    # SMTP_FROM must be an address, not a display name — an invalid one
    # produces a malformed From header that most servers reject.
    sender = os.environ.get("SMTP_FROM", "").strip()
    if "@" not in sender:
        if sender:
            log.warning(
                "SMTP_FROM=%r is not an e-mail address; falling back to "
                "SMTP_USER (%s).",
                sender,
                user,
            )
        sender = user
    use_starttls = os.environ.get("SMTP_STARTTLS", "1") != "0"

    who = trainer_name.strip() or "A trainer"
    group = group_name.strip() or "a group"
    base = _base_url()

    lines = [
        f"Hello,",
        "",
        f"{who} has invited you to the group \"{group}\" on QuizMonkey.",
        "",
        "To accept, open the QuizMonkey mobile app and sign in. If you do not "
        "have an account yet, create one using this e-mail address "
        f"({to_email}) — the invitation will then appear on the start page.",
    ]
    if base:
        lines += ["", f"You can also manage your account here: {base}"]
    lines += [
        "",
        "If you were not expecting this invitation, you can simply ignore this "
        "e-mail.",
        "",
        "— QuizMonkey",
    ]
    text_body = "\n".join(lines)

    msg = EmailMessage()
    msg["Subject"] = f'You have been invited to "{group}" on QuizMonkey'
    msg["From"] = formataddr(("QuizMonkey", sender))
    msg["To"] = to_email
    msg.set_content(text_body)

    try:
        if port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=15, context=context) as s:
                s.login(user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as s:
                if use_starttls:
                    s.starttls(context=ssl.create_default_context())
                s.login(user, password)
                s.send_message(msg)
    except Exception as ex:
        # The invitation itself already succeeded, so a failed send must not
        # raise — but it must be visible in the server log, otherwise a
        # misconfigured mail server is impossible to diagnose.
        log.warning("Could not send invitation e-mail to %s: %s", to_email, ex)
        return
    log.info("Invitation e-mail sent to %s", to_email)
