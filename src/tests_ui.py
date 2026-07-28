"""Taking tests in the mobile app.

Tests are the one thing the app does NOT do offline: drawing questions and
scoring happen on the web server so the answer key never reaches the device.
The app talks to that server's JSON API (see web/main.py, /api/*) using the
signed-in user's Supabase access token.

This screen is only reachable for a signed-in trainee; offline users never see
it. It reuses the host QuizApp for rendering (`app._set_root`) and styling.
"""

from __future__ import annotations

import threading

import flet as ft

try:
    import httpx
except Exception:  # pragma: no cover - httpx ships with supabase
    httpx = None

# Server error keys -> plain English (the mobile app is English only).
_MESSAGES = {
    "unauthorized": "Please sign in again.",
    "tests_not_configured": "Tests are not available yet. Please try later.",
    "test_not_found": "This test is no longer available.",
    "err.test_passed": "You have already passed this test.",
    "err.test_locked": "No attempts left for this test.",
    "err.test_empty": "This test has no questions.",
    "err.attempt_not_found": "That attempt could not be found.",
    "err.attempt_done": "This attempt is already finished.",
}


def _message(key: str) -> str:
    return _MESSAGES.get(key, "Something went wrong. Please try again.")


class TestsView:
    def __init__(self, app):
        self.app = app
        self.page = app.page
        self.backend = app.backend
        self._timer_stop = threading.Event()

    # ------------------------------------------------------------------ net
    def _request(self, method: str, path: str, payload=None):
        """Call the test API. Returns (ok: bool, data_or_error_message)."""
        if httpx is None:
            return False, "Networking is unavailable in this build."
        token = self.backend.access_token()
        if not token:
            return False, "Please sign in again."
        url = f"{self.backend.api_base}{path}"
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = httpx.request(method, url, headers=headers, json=payload, timeout=20)
        except Exception:
            return False, "No connection to the server. Tests need internet access."
        try:
            data = resp.json()
        except Exception:
            data = {}
        if resp.status_code >= 400:
            return False, _message((data or {}).get("error", ""))
        return True, data

    # --------------------------------------------------------------- layout
    def _header(self, title: str, on_back) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        icon_color=self.app.color_text,
                        on_click=lambda e: on_back(),
                    ),
                    ft.Text(
                        title,
                        size=self.app._get_text_size(22),
                        weight=ft.FontWeight.W_800,
                        color=self.app.color_text,
                        expand=True,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.only(left=8, right=16, top=8, bottom=4),
        )

    def _pad(self) -> int:
        return self.app._get_pad(20)

    def _text(self, value: str, size: int = 16, weight=None, color=None) -> ft.Text:
        return ft.Text(
            value,
            size=self.app._get_text_size(size),
            weight=weight or ft.FontWeight.NORMAL,
            color=color or self.app.color_text,
        )

    def _primary_button(self, label: str, handler, color=None) -> ft.Button:
        return ft.Button(
            content=label,
            on_click=handler,
            height=self.app._get_pad(52),
            style=self.app.make_button_style(color or self.app.color_success, radius=12),
        )

    # ------------------------------------------------------------- screens
    def open(self) -> None:
        """Entry point: the list of tests released to this trainee."""
        self._timer_stop.set()  # cancel any running countdown
        ok, data = self._request("GET", "/api/tests")
        if not ok:
            self.app.show_startpage()
            self.app.show_message(data)
            return

        tests = data.get("tests", [])
        cards: list[ft.Control] = []
        if not tests:
            cards.append(self._text("No test has been released to you yet.",
                                    color=self.app.color_muted))
        for t in tests:
            cards.append(self._test_card(t))

        body = ft.Container(
            content=ft.Column(controls=cards, scroll=ft.ScrollMode.AUTO,
                              expand=True, spacing=self.app._get_pad(10)),
            padding=self._pad(),
            expand=True,
        )
        self.app._set_root(self._header("Tests", self.app.show_startpage), body)
        self.page.update()

    def _test_card(self, t: dict) -> ft.Control:
        status_bits = []
        if t.get("passed"):
            status_bits.append(("Passed", self.app.color_success))
        elif t.get("locked"):
            status_bits.append(("Locked", self.app.color_danger))
        elif t.get("in_progress"):
            status_bits.append(("In progress", self.app.color_stat))
        elif t.get("used"):
            status_bits.append((f"{t['used']}/{t['max_attempts']} attempts",
                                self.app.color_muted))

        secs = t.get("time_limit_seconds")
        meta = f"Pass {t['pass_percent']}% · {t['question_count']} questions"
        if secs:
            meta += f" · {secs // 60} min"

        info = [self._text(t["name"], size=18, weight=ft.FontWeight.W_700),
                self._text(meta, size=13, color=self.app.color_muted)]
        for label, color in status_bits:
            info.append(self._text(label, size=13, weight=ft.FontWeight.W_700,
                                   color=color))

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(controls=info, spacing=2, expand=True),
                    ft.IconButton(
                        icon=ft.Icons.CHEVRON_RIGHT_ROUNDED,
                        icon_color=self.app.color_text,
                        on_click=lambda e, tid=t["id"]: self._intro(tid),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=self.app._get_pad(14),
            bgcolor=self.app.color_surface,
            border=ft.Border.all(1, self.app.color_border),
            border_radius=14,
        )

    def _intro(self, test_id: str) -> None:
        # The list already has what we need, but re-fetch to get fresh status.
        ok, data = self._request("GET", "/api/tests")
        if not ok:
            self.open()
            self.app.show_message(data)
            return
        test = next((x for x in data.get("tests", []) if x["id"] == test_id), None)
        if test is None:
            self.open()
            return

        secs = test.get("time_limit_seconds")
        rows = [
            self._text(test["name"], size=22, weight=ft.FontWeight.W_800),
            self._text(f"You need at least {test['pass_percent']}% to pass.", size=16),
            self._text(f"{test['question_count']} questions", size=14,
                       color=self.app.color_muted),
            self._text(f"Time limit: {secs // 60} min" if secs else "No time limit",
                       size=14, color=self.app.color_muted),
            self._text(f"Attempts left: {test['attempts_left']}/{test['max_attempts']}",
                       size=14, color=self.app.color_muted),
        ]

        if test.get("passed"):
            rows.append(self._text("You passed this test.", size=16,
                                   weight=ft.FontWeight.W_800,
                                   color=self.app.color_success))
        elif test.get("locked"):
            rows.append(self._text("All attempts used, not passed.", size=16,
                                   weight=ft.FontWeight.W_800,
                                   color=self.app.color_danger))
        else:
            rows.append(self._text(
                "The test cannot be paused, and you only see your result at the end.",
                size=13, color=self.app.color_muted))
            rows.append(self._primary_button(
                "Start test", lambda e, tid=test_id: self._start(tid)))

        body = ft.Container(
            content=ft.Column(controls=rows, scroll=ft.ScrollMode.AUTO,
                              expand=True, spacing=self.app._get_pad(12)),
            padding=self._pad(),
            expand=True,
        )
        self.app._set_root(self._header("Test", self.open), body)
        self.page.update()

    def _start(self, test_id: str) -> None:
        ok, data = self._request("POST", f"/api/tests/{test_id}/start")
        if not ok:
            self._intro(test_id)
            self.app.show_message(data)
            return
        self._run(data)

    def _run(self, attempt: dict) -> None:
        self._timer_stop.set()
        self._timer_stop = threading.Event()

        # Each entry is ("radio", RadioGroup) or ("multi", [Checkbox, ...]).
        groups: list[tuple] = []
        controls: list[ft.Control] = []

        remaining = attempt.get("remaining_seconds")
        timer_text = None
        if remaining is not None:
            timer_text = self._text("", size=18, weight=ft.FontWeight.W_800)
            controls.append(
                ft.Container(content=timer_text,
                             alignment=ft.Alignment.CENTER_RIGHT)
            )

        controls.append(self._text(attempt["name"], size=20, weight=ft.FontWeight.W_800))
        controls.append(self._text("Pick one answer per question.", size=13,
                                   color=self.app.color_muted))

        for i, q in enumerate(attempt["questions"]):
            head = [self._text(f"{i + 1}. {q['prompt']}", size=16,
                               weight=ft.FontWeight.W_700)]
            if q.get("multi"):
                checks = [ft.Checkbox(label=opt, value=False,
                                        active_color=self.app.color_primary) for opt in q["options"]]
                groups.append(("multi", checks))
                head.append(self._text("Select all correct answers.", size=13,
                                       color=self.app.color_muted))
                answer_control = ft.Column(controls=checks, spacing=2)
            else:
                radios = [ft.Radio(value=opt, label=opt,
                                     active_color=self.app.color_primary) for opt in q["options"]]
                group = ft.RadioGroup(content=ft.Column(controls=radios, spacing=2))
                groups.append(("radio", group))
                answer_control = group
            controls.append(
                ft.Container(
                    content=ft.Column(controls=head + [answer_control], spacing=6),
                    padding=self.app._get_pad(12),
                    bgcolor=self.app.color_surface,
                    border=ft.Border.all(1, self.app.color_border),
                    border_radius=14,
                )
            )

        submitting = {"busy": False}

        def do_submit(_=None):
            if submitting["busy"]:
                return
            submitting["busy"] = True
            self._timer_stop.set()
            answers = {}
            for i, (kind, obj) in enumerate(groups):
                if kind == "radio":
                    if obj.value:
                        answers[str(i)] = [obj.value]
                else:
                    picked = [c.label for c in obj if c.value]
                    if picked:
                        answers[str(i)] = picked
            ok, data = self._request(
                "POST", f"/api/attempts/{attempt['attempt_id']}/submit",
                {"answers": answers})
            if not ok:
                self.open()
                self.app.show_message(data)
                return
            self._result(data, attempt.get("pass_percent"))

        controls.append(self._primary_button("Submit test", do_submit))

        body = ft.Container(
            content=ft.Column(controls=controls, scroll=ft.ScrollMode.AUTO,
                              expand=True, spacing=self.app._get_pad(12)),
            padding=self._pad(),
            expand=True,
        )
        # No back button: a test should not be casually abandoned.
        self.app._set_root(
            ft.Container(
                content=self._text("Test", size=22, weight=ft.FontWeight.W_800),
                padding=ft.Padding.only(left=16, right=16, top=10, bottom=4),
            ),
            body,
        )
        self.page.update()

        if remaining is not None and timer_text is not None:
            self._run_countdown(remaining, timer_text, do_submit)

    def _run_countdown(self, seconds: int, label: ft.Text, on_timeout) -> None:
        stop = self._timer_stop

        def loop():
            left = seconds
            while left >= 0 and not stop.is_set():
                mins, secs = divmod(left, 60)
                label.value = f"Time left: {mins}:{secs:02d}"
                try:
                    label.update()
                except Exception:
                    return
                stop.wait(1)
                left -= 1
            if not stop.is_set():
                on_timeout()

        threading.Thread(target=loop, daemon=True).start()

    def _result(self, res: dict, pass_percent) -> None:
        self._timer_stop.set()
        passed = bool(res.get("passed"))
        color = self.app.color_success if passed else self.app.color_danger
        rows = [
            ft.Text(f"{res.get('percent', 0)}%",
                    size=self.app._get_text_size(48),
                    weight=ft.FontWeight.W_800, color=color),
            ft.Text("Passed" if passed else "Not passed",
                    size=self.app._get_text_size(22),
                    weight=ft.FontWeight.W_800, color=color),
            self._text(f"Attempt {res.get('attempt_no', 1)}", size=14,
                       color=self.app.color_muted),
        ]
        body = ft.Container(
            content=ft.Column(
                controls=rows + [self._primary_button(
                    "Back to tests", lambda e: self.open(),
                    color=self.app.color_stat)],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=self.app._get_pad(12),
            ),
            padding=self._pad(),
            alignment=ft.Alignment.CENTER,
            expand=True,
        )
        self.app._set_root(body)
        self.page.update()
