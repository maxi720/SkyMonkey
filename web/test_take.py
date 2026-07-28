"""Server-side test taking: drawing questions and scoring, done with a
privileged Supabase client so the answer key never reaches the trainee.

Every function here takes an already-privileged `svc` client (service role).
Authorisation — that this user is actually allowed to take this test — is
checked by the caller with the user's own token (RLS), before these run.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone


class TakeError(Exception):
    """A taking rule was violated; `key` is an i18n message key."""

    def __init__(self, key: str):
        super().__init__(key)
        self.key = key


CORRECT_SEPARATOR = "|"


def _correct_set(value) -> set:
    """The set of correct answers from a stored `correct` field (a string with
    CORRECT_SEPARATOR between multiple, or already a list)."""
    if isinstance(value, list):
        return {str(v) for v in value}
    return {c for c in str(value).split(CORRECT_SEPARATOR) if c}


def _sanitise(questions: list[dict]) -> list[dict]:
    """Drop the answer key — what the client is allowed to see. `multi` tells
    the client to allow more than one selection, without revealing which."""
    out = []
    for q in questions:
        out.append({
            "prompt": q["prompt"],
            "options": q["options"],
            "multi": len(_correct_set(q["correct"])) > 1,
        })
    return out


def attempt_status(svc, test: dict, uid: str) -> dict:
    """The trainee's standing on a test: attempts used, passed, locked, etc."""
    rows = (
        svc.table("test_attempts")
        .select("attempt_no, status, score_percent, passed")
        .eq("test_id", test["id"]).eq("user_id", uid)
        .order("attempt_no").execute().data or []
    )
    completed = [r for r in rows if r["status"] == "completed"]
    in_progress = next((r for r in rows if r["status"] == "in_progress"), None)
    passed_row = next((r for r in completed if r["passed"]), None)
    best = max((r["score_percent"] or 0) for r in completed) if completed else None
    used = len(completed)
    locked = (passed_row is None) and used >= test["max_attempts"]
    return {
        "used": used,
        "attempts_left": max(0, test["max_attempts"] - used),
        "passed": passed_row is not None,
        "passed_attempt": passed_row["attempt_no"] if passed_row else None,
        "best": best,
        "locked": locked,
        "in_progress": in_progress,
        "done": passed_row is not None or locked,
    }


def _build_questions(svc, test: dict, uid: str, completed: list[dict]) -> list[dict]:
    tid = test["id"]
    # Manual picks and 'fixed' random both use the frozen set everyone shares.
    if test["selection_mode"] == "manual" or test["draw_scope"] == "fixed":
        rows = (
            svc.table("test_questions")
            .select("prompt, options, correct, position")
            .eq("test_id", tid).order("position").execute().data or []
        )
        return [{"prompt": r["prompt"], "options": r["options"],
                 "correct": r["correct"]} for r in rows]

    # per-trainee random: same questions again, if that is the rule.
    if test["retry_mode"] == "same" and completed:
        last = (
            svc.table("test_attempts").select("questions")
            .eq("test_id", tid).eq("user_id", uid).eq("status", "completed")
            .order("attempt_no", desc=True).limit(1).execute().data
        )
        if last:
            return last[0]["questions"]

    # per-trainee random: a fresh draw from the pool, per source target count.
    sources = (
        svc.table("test_sources").select("source_no, target_count")
        .eq("test_id", tid).order("source_no").execute().data or []
    )
    pool = (
        svc.table("test_pool").select("source_no, prompt, options, correct")
        .eq("test_id", tid).execute().data or []
    )
    by_source: dict[int, list[dict]] = {}
    for p in pool:
        by_source.setdefault(p["source_no"], []).append(p)

    picked: list[dict] = []
    for s in sources:
        cands = by_source.get(s["source_no"], [])
        n = min(s["target_count"], len(cands))
        chosen = cands if n >= len(cands) else random.sample(cands, n)
        for c in chosen:
            picked.append({"prompt": c["prompt"], "options": c["options"],
                           "correct": c["correct"]})
    random.shuffle(picked)
    return picked


def start_attempt(svc, test: dict, uid: str) -> dict:
    """Return the trainee's current attempt (resumed or newly created), with the
    questions already sanitised for sending to the client.

    Enforces the attempt rules: a passed test is finished; once all attempts are
    used without passing, the test is locked.
    """
    tid = test["id"]
    ongoing = (
        svc.table("test_attempts").select("*")
        .eq("test_id", tid).eq("user_id", uid).eq("status", "in_progress")
        .execute().data
    )
    if ongoing:
        a = ongoing[0]
        return {"id": a["id"], "attempt_no": a["attempt_no"],
                "questions": _sanitise(a["questions"]),
                "started_at": a["started_at"]}

    completed = (
        svc.table("test_attempts")
        .select("attempt_no, passed").eq("test_id", tid).eq("user_id", uid)
        .eq("status", "completed").order("attempt_no").execute().data or []
    )
    if any(a["passed"] for a in completed):
        raise TakeError("err.test_passed")
    if len(completed) >= test["max_attempts"]:
        raise TakeError("err.test_locked")

    questions = _build_questions(svc, test, uid, completed)
    if not questions:
        raise TakeError("err.test_empty")

    inserted = (
        svc.table("test_attempts").insert({
            "test_id": tid, "user_id": uid,
            "attempt_no": len(completed) + 1, "status": "in_progress",
            "questions": questions,
        }).execute().data[0]
    )
    return {"id": inserted["id"], "attempt_no": inserted["attempt_no"],
            "questions": _sanitise(questions), "started_at": inserted["started_at"]}


def load_running_attempt(svc, attempt_id: str, uid: str) -> dict:
    """Fetch an in-progress attempt owned by this user, sanitised for the run
    page. Raises TakeError if missing, not theirs, or already completed."""
    rows = (
        svc.table("test_attempts").select("*").eq("id", attempt_id).execute().data
    )
    if not rows or rows[0]["user_id"] != uid:
        raise TakeError("err.attempt_not_found")
    a = rows[0]
    if a["status"] != "in_progress":
        raise TakeError("err.attempt_done")
    return {"id": a["id"], "test_id": a["test_id"], "attempt_no": a["attempt_no"],
            "questions": _sanitise(a["questions"]), "started_at": a["started_at"]}


def score_attempt(svc, attempt_id: str, uid: str, answers: dict, test: dict) -> dict:
    """Score a submission server-side and record the result. `answers` maps the
    question index (as a string) to the chosen option text."""
    rows = (
        svc.table("test_attempts").select("*").eq("id", attempt_id).execute().data
    )
    if not rows or rows[0]["user_id"] != uid:
        raise TakeError("err.attempt_not_found")
    a = rows[0]
    questions = a["questions"]
    total = len(questions)
    correct = 0
    for i, q in enumerate(questions):
        given = answers.get(str(i))
        given_set = set(given) if isinstance(given, list) else ({given} if given else set())
        # A question counts only when exactly the correct answers are chosen —
        # no missing ones, no extra ones (no partial credit).
        if given_set == _correct_set(q["correct"]):
            correct += 1
    percent = round(100 * correct / total) if total else 0
    passed = percent >= test["pass_percent"]

    # Only the first completion counts; a resubmit of an already-scored attempt
    # returns the stored result rather than overwriting it.
    if a["status"] == "completed":
        return {"percent": a["score_percent"], "passed": a["passed"],
                "attempt_no": a["attempt_no"]}

    svc.table("test_attempts").update({
        "status": "completed", "answers": answers,
        "score_percent": percent, "passed": passed,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", attempt_id).execute()
    return {"percent": percent, "passed": passed, "attempt_no": a["attempt_no"]}
