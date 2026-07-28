import csv
import io
import json
import os
import shutil
from pathlib import Path

import flet as ft

from auth_ui import AuthView
from backend import Backend, Profile
from tests_ui import TestsView


class QuizApp:
    def __init__(self, page: ft.Page):
        self.page = page

        self.page.title = "QuizMonkey"
        # Self-hosted font bundled in assets — no runtime fetch from Google
        # Fonts servers, so no user IP is leaked (GDPR/DSGVO compliant).
        self.page.fonts = {"Fredoka": "fonts/Fredoka.ttf"}
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
        self.page.padding = 0

        # Swiss-modernist palette — the same tokens the web app uses in
        # web/static/app.css, so both halves stay one product. Neutrals carry no
        # colour cast, so the single indigo accent is the only chroma; green and
        # red mean only right and wrong.
        self.color_bg = "#FAFAFA"
        self.color_surface = "#FFFFFF"
        self.color_surface_2 = "#F4F4F5"
        self.color_border = "#E4E4E7"
        self.color_border_strong = "#D4D4D8"
        self.color_text = "#18181B"
        self.color_muted = "#71717A"
        # Label colour for anything sitting on a filled accent surface.
        self.color_on_primary = "#FFFFFF"

        self.color_primary = "#4F46E5"
        self.color_primary_press = "#3730A3"
        self.color_primary_soft = "#EEF2FF"
        self.color_primary_ink = "#312E81"

        self.color_info = "#1D4ED8"
        self.color_success = "#15803D"
        self.color_success_ink = "#14532D"
        self.color_danger = "#B91C1C"
        self.color_danger_ink = "#7F1D1D"
        self.color_warning = "#A16207"
        self.color_answer = self.color_surface
        self.color_answer_border = self.color_border
        self.color_stat = "#9A5B06"
        self.logo_src = "icon.png"
        self.page.bgcolor = self.color_bg

        platform = self.page.platform
        self.is_mobile = platform is not None and platform.is_mobile()

        if not self.is_mobile and not self.page.web:
            self.page.window.min_width = 320
            self.page.window.width = 600
            self.page.window.height = 700

        data_dir = os.environ.get("FLET_APP_STORAGE_DATA")
        if data_dir:
            self.quiz_folder = os.path.join(data_dir, "quizzes")
        else:
            self.quiz_folder = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "quizzes"
            )

        self.default_quiz_folder = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "quizzes"
        )

        os.makedirs(self.quiz_folder, exist_ok=True)
        self._ensure_default_quizzes()

        # Persisted app state (completion stats + in-progress quiz runs) stored
        # as a JSON file in the app's data directory.
        state_root = data_dir or os.path.dirname(os.path.abspath(__file__))
        self.state_file = os.path.join(state_root, "state.json")
        self.state = self._load_state()

        self.fragen: list[list[str]] = []
        self.current_question = 0
        self.correct_answer = ""
        self.correct_set: set[str] = set()
        self.is_multi = False
        self.selected_set: set[str] = set()
        # Tinted fills for the answer feedback. `success_soft` marks an answer
        # the user got right; `success_faint` is the much softer green for a
        # correct answer they did not pick (multiple choice only), so the two
        # never read the same.
        # Two clearly distinct greens: the answer the user got right is filled
        # noticeably, the correct one they missed only tinted. On the web the
        # same distinction is carried by a border rule, which the Flet buttons
        # do not have, so these fills need more separation than the web tokens.
        self.color_success_soft = "#DCFCE7"
        self.color_success_faint = "#F0FDF4"
        self.color_danger_soft = "#FEE2E2"
        self.action_button: ft.Button | None = None
        self.correct_count = 0
        self.selected_answer: str | None = None
        self.answer_locked = False
        self.wrong_questions: list[list[str]] = []
        # Filename key of the quiz currently being played; None during a
        # retry-wrong-questions session (those never touch stats/progress).
        self.active_quiz_key: str | None = None
        self.quiz_buttons: list[ft.Control] = []
        self.answer_buttons: list[ft.Button] = []
        self.next_button: ft.Button | None = None

        self.file_picker = ft.FilePicker()
        self.page.services.append(self.file_picker)

        self.page.on_resize = self._on_resize
        self._current_view = "start"
        self._layout_cache: dict[str, float | int | str] = {
            "width": 0,
            "height": 0,
            "scale": 1.0,
            "mode": "medium",
        }
        self._last_resize_signature: tuple[int, int, str] | None = None

        # Signed-in user, or None while offline ("continue without login").
        self.backend = Backend()
        self.profile: Profile | None = None
        self.auth_view = AuthView(self)
        # Cached pending group invitations; None means "not loaded yet".
        self._pending_invites: list[dict] | None = None

        self._refresh_layout_cache(force=True)

        self._start()

    # ------------------------------------------------------------------
    # Startup: restore a session, or ask the user to sign in
    # ------------------------------------------------------------------
    def _start(self) -> None:
        if not self.backend.available:
            # Without a configured backend the login form could never succeed,
            # so go straight to the quizzes instead of showing a dead end.
            self.continue_offline()
            return

        if self._restore_session():
            return

        self.auth_view.show()

    def _restore_session(self) -> bool:
        """Sign back in with the tokens kept from the last run."""
        session = self.state.get("session")
        if not isinstance(session, dict):
            return False
        access = session.get("access_token")
        refresh = session.get("refresh_token")
        if not access or not refresh:
            return False

        try:
            self.backend.client.auth.set_session(access, refresh)
            profile = self.backend.current_profile()
        except Exception:
            profile = None

        if profile is None:
            self._store_session(None)
            return False

        self.profile = profile
        self.show_startpage()
        return True

    def _store_session(self, session) -> None:
        """Persist (or clear) the tokens needed to stay signed in.

        Stored in the app's own sandboxed data directory. Not the Keychain —
        good enough for a quiz app, but worth revisiting if the account ever
        holds anything sensitive.
        """
        if session is None:
            self.state.pop("session", None)
        else:
            self.state["session"] = {
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
            }
        self._save_state()

    def enter_signed_in(self, profile: Profile) -> None:
        self.profile = profile
        self._pending_invites = None
        # Clear the login form's spinner state; otherwise a later sign-out
        # returns to a login button still stuck on "Please wait...".
        self.auth_view.busy = False
        try:
            session = self.backend.client.auth.get_session()
        except Exception:
            session = None
        self._store_session(session)
        self.show_startpage()
        self.show_message(f"Welcome, {profile.first_name or profile.display_name}!")

    def continue_offline(self) -> None:
        """Use the app without an account: local quizzes only."""
        self.profile = None
        self.show_startpage()

    def sign_out(self) -> None:
        if self.backend.available:
            self.backend.sign_out()
        self.profile = None
        self._pending_invites = None
        self._store_session(None)
        self.auth_view.busy = False
        self.auth_view.show()

    def show_message(self, text: str) -> None:
        self.page.show_dialog(
            ft.SnackBar(
                content=ft.Text(text, text_align=ft.TextAlign.CENTER),
                duration=3000,
            )
        )
        self.page.update()

    def _dismiss_dialog(self) -> None:
        self.page.pop_dialog()
        self.page.update()

    def _centered_dialog(
        self, title: str, body: ft.Control, actions: list[ft.Control]
    ) -> ft.AlertDialog:
        """Build a modal dialog whose title, body and actions are centred."""
        return ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Text(
                        title,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            content=ft.Column(
                controls=[body],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
                width=self._get_pad(300),
            ),
            actions=actions,
            actions_alignment=ft.MainAxisAlignment.CENTER,
        )

    # ------------------------------------------------------------------
    # Persisted state: completion statistics and in-progress quiz runs
    # ------------------------------------------------------------------
    def _load_state(self) -> dict:
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("stats", {})
        data.setdefault("progress", {})
        return data

    def _save_state(self) -> None:
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False)
        except OSError:
            pass

    def _record_completion(self, quiz_key: str) -> None:
        stats = self.state["stats"]
        stats[quiz_key] = int(stats.get(quiz_key, 0)) + 1
        self._save_state()

    def _get_completion_count(self, quiz_key: str) -> int:
        return int(self.state["stats"].get(quiz_key, 0))

    def _save_progress(self) -> None:
        if not self.active_quiz_key:
            return
        self.state["progress"][self.active_quiz_key] = {
            "fragen": self.fragen,
            "current_question": self.current_question,
            "correct_count": self.correct_count,
            "wrong_questions": self.wrong_questions,
        }
        self._save_state()

    def _get_progress(self, quiz_key: str) -> dict | None:
        progress = self.state["progress"].get(quiz_key)
        if isinstance(progress, dict) and progress.get("fragen"):
            return progress
        return None

    def _clear_progress(self, quiz_key: str | None) -> None:
        if quiz_key and quiz_key in self.state["progress"]:
            del self.state["progress"][quiz_key]
            self._save_state()

    def _get_scale(self) -> float:
        self._refresh_layout_cache()
        return float(self._layout_cache["scale"])

    def _get_view_mode(self) -> str:
        self._refresh_layout_cache()
        return str(self._layout_cache["mode"])

    def _refresh_layout_cache(self, force: bool = False) -> None:
        width = int(self.page.width or 600)
        height = int(self.page.height or 800)

        cached_width = int(self._layout_cache["width"])
        cached_height = int(self._layout_cache["height"])

        if not force and width == cached_width and height == cached_height:
            return

        if width < 520:
            mode = "compact"
        elif width < 880:
            mode = "medium"
        else:
            mode = "expanded"

        scale = max(0.5, min(1.5, min(width / 600, height / 750)))
        self._layout_cache = {
            "width": width,
            "height": height,
            "scale": scale,
            "mode": mode,
        }

    def _side_padding(self) -> int:
        mode = self._get_view_mode()
        if mode == "compact":
            return 10
        if mode == "medium":
            return 16
        return 24

    def _get_text_size(self, base: int) -> int:
        return max(10, int(base * self._get_scale()))

    def _get_pad(self, base: int) -> int:
        return max(2, int(base * self._get_scale()))

    def _icon_button(
        self, icon, color, handler, size: int = 52, pad: int = 20, radius: int = 22
    ) -> ft.Button:
        """A compact button sized to its (large) icon with rounded corners.
        Material icons render from the bundled font — no network (DSGVO safe)."""
        return ft.Button(
            content=ft.Icon(
                icon, color=self.color_on_primary, size=self._get_text_size(size)
            ),
            on_click=handler,
            style=self.make_button_style(
                color, radius=radius, padding=ft.Padding.all(self._get_pad(pad))
            ),
        )

    def _logo(self, base_size: int = 120) -> ft.Container:
        mode = self._get_view_mode()
        size = base_size
        if mode == "compact":
            size = int(base_size * 0.68)
        elif mode == "medium":
            size = int(base_size * 0.82)

        logo_size = self._get_pad(size)
        return ft.Container(
            content=ft.Image(
                src=self.logo_src,
                width=logo_size,
                height=logo_size,
                fit=ft.BoxFit.CONTAIN,
                error_content=ft.Container(width=logo_size, height=logo_size),
            ),
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.only(top=self._get_pad(8), bottom=self._get_pad(8)),
        )

    def make_button_style(
        self,
        bgcolor,
        text_size=20,
        radius=8,
        padding=None,
        side=None,
        weight=ft.FontWeight.W_600,
        font_family=None,
        color=None,
    ) -> ft.ButtonStyle:
        """Filled button. The label defaults to `on_primary` because these sit
        on an accent colour; pass `color` explicitly for buttons on a surface."""
        return ft.ButtonStyle(
            text_style=ft.TextStyle(
                size=text_size, weight=weight, font_family=font_family
            ),
            color=color or self.color_on_primary,
            bgcolor=bgcolor,
            padding=padding,
            shape=ft.RoundedRectangleBorder(radius=radius),
            side=side,
        )

    def _fit_action_button(
        self, button_width: float, label_len: int = 6
    ) -> tuple[int, int]:
        """Return the largest bold font size whose label fits inside a button
        of the given width (leaving a little horizontal breathing room), plus a
        matching button height."""
        side_margin = button_width * 0.16  # "ein wenig Seitenabstand"
        usable = max(1.0, button_width - 2 * side_margin)
        char_factor = 0.60  # approx. em-width per bold character
        fit = int(usable / (label_len * char_factor))
        text_size = max(14, min(fit, self._get_text_size(34)))
        height = int(text_size * 2.1)
        return text_size, height

    def _render_current_view(self) -> None:
        self._refresh_layout_cache(force=True)
        if self._current_view == "start":
            self.show_startpage()
        elif self._current_view == "result":
            self.show_result()
        elif self._current_view == "question":
            self.show_question_page()
        elif self._current_view == "statistics":
            self.show_statistics()
        elif self._current_view == "auth":
            self.auth_view.show()

    def _set_root(self, *controls: ft.Control) -> None:
        """Mount a view inside a SafeArea so content never overlaps the
        notch/dynamic island at the top or the home indicator at the bottom."""
        self.page.controls.clear()
        self.page.controls.append(
            ft.SafeArea(
                content=ft.Column(
                    controls=list(controls),
                    expand=True,
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
                expand=True,
            )
        )

    def _list_quiz_files(self) -> list[str]:
        quiz_path = Path(self.quiz_folder)
        return sorted(
            entry.name
            for entry in quiz_path.iterdir()
            if entry.is_file() and entry.suffix.lower() == ".csv"
        )

    def _ensure_default_quizzes(self) -> None:
        source_dir = Path(self.default_quiz_folder)
        target_dir = Path(self.quiz_folder)

        if source_dir == target_dir or not source_dir.exists():
            return

        for source_file in source_dir.glob("*.csv"):
            target_file = target_dir / source_file.name
            if target_file.exists():
                continue
            try:
                shutil.copy(source_file, target_file)
            except OSError:
                continue

    def _parse_quiz_text(self, quiz_text: str) -> tuple[list[list[str]], list[str]]:
        reader = csv.reader(io.StringIO(quiz_text), delimiter=";")
        return self._parse_quiz_rows(reader)

    def _get_quiz_destination(self, original_filename: str) -> str:
        safe_name = os.path.basename(original_filename)
        if not safe_name.lower().endswith(".csv"):
            safe_name = f"{safe_name}.csv"

        destination = Path(self.quiz_folder) / safe_name
        if not destination.exists():
            return str(destination)

        stem = destination.stem
        suffix = destination.suffix
        index = 1
        while True:
            candidate = destination.with_name(f"{stem}_{index}{suffix}")
            if not candidate.exists():
                return str(candidate)
            index += 1

    def _validate_row(self, row: list[str], row_number: int) -> tuple[bool, str | None]:
        if len(row) != 6:
            return (
                False,
                f"Row {row_number}: Expected 6 columns, found {len(row)}.",
            )

        row[0] = row[0].lstrip("\ufeff")

        if not row[0].strip():
            return False, f"Row {row_number}: Question is empty."

        answers = row[1:5]
        non_empty_answers = [answer for answer in answers if answer != ""]
        if len(non_empty_answers) < 2:
            return (
                False,
                f"Row {row_number}: At least 2 answer options required.",
            )

        # correctAnswer may list several correct answers separated by "|"
        # (multiple choice). Each must match one of the answer columns.
        correct = [c.strip() for c in row[5].split("|") if c.strip()]
        if not correct:
            return False, f"Row {row_number}: no correct answer given."
        for c in correct:
            if c not in answers:
                return (
                    False,
                    f"Row {row_number}: every correctAnswer must exactly match "
                    "one answer.",
                )

        return True, None

    def _parse_quiz_rows(self, reader: csv.reader) -> tuple[list[list[str]], list[str]]:
        questions: list[list[str]] = []
        errors: list[str] = []

        for row_number, row in enumerate(reader, start=1):
            if not any(cell.strip() for cell in row):
                continue

            is_valid, error = self._validate_row(row, row_number)
            if is_valid:
                questions.append(row)
            elif error:
                errors.append(error)

        if not questions and not errors:
            errors.append("No questions found.")

        return questions, errors

    def _show_validation_errors(self, errors: list[str]) -> None:
        first_error = errors[0]
        if len(errors) > 1:
            self.show_message(f"File error ({len(errors)}): {first_error}")
        else:
            self.show_message(f"File error: {first_error}")

    def show_startpage(self) -> None:
        self._current_view = "start"
        self._refresh_layout_cache(force=True)
        self.next_button = None
        self.selected_answer = None
        self.answer_locked = False
        self.load_custom_quizzes()

        side_padding = self._side_padding()
        page_w = int(self.page.width or 600)
        page_h = int(self.page.height or 800)

        # Quiz area: a large logo watermark centred behind a scrollable list of
        # quizzes. When more quizzes are imported than fit on screen, the list
        # scrolls while the logo stays centred in the same window.
        logo_bg_size = int(min(page_w, page_h) * 0.7)
        background_logo = ft.Container(
            content=ft.Image(
                src="logo_watermark.png",
                width=logo_bg_size,
                height=logo_bg_size,
                fit=ft.BoxFit.CONTAIN,
                opacity=0.22,
                error_content=ft.Container(),
            ),
            alignment=ft.Alignment.CENTER,
            expand=True,
        )
        # Breathing room above the first quiz, now that the wordmark heading is
        # gone. Padded on the list only, so the watermark stays centred.
        quiz_scroll = ft.Container(
            content=ft.Column(
                controls=self.quiz_buttons,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
                spacing=0,
            ),
            padding=ft.Padding.only(top=self._get_pad(28)),
            expand=True,
        )
        quiz_area = ft.Stack(
            controls=[background_logo, quiz_scroll],
            expand=True,
        )

        invites_banner = self._invitations_banner()

        # Bottom actions: Import (left) + Delete (right), always side by side,
        # equal size, rectangular, with bold text scaled to fit the button.
        container_pad = self._get_pad(side_padding)
        btn_spacing = self._get_pad(12)
        btn_w = max(80.0, (page_w - 2 * container_pad - btn_spacing) / 2)
        action_text_size, action_height = self._fit_action_button(btn_w)

        def action_btn(label: str, color: str, handler) -> ft.Button:
            return ft.Button(
                content=label,
                on_click=handler,
                expand=True,
                height=action_height,
                style=self.make_button_style(
                    color,
                    text_size=action_text_size,
                    radius=8,  # matches the web button radius
                    weight=ft.FontWeight.W_800,
                    padding=ft.Padding.symmetric(horizontal=self._get_pad(6)),
                ),
            )

        # Statistic button sits above the Import/Delete row (amber accent).
        stat_button = ft.Button(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.BAR_CHART_ROUNDED,
                        color=self.color_on_primary,
                        size=action_text_size,
                    ),
                    ft.Text(
                        "Statistic",
                        weight=ft.FontWeight.W_800,
                        size=action_text_size,
                        color=self.color_on_primary,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=self._get_pad(8),
            ),
            on_click=lambda e: self.show_statistics(),
            height=action_height,
            style=self.make_button_style(self.color_stat, radius=8),
        )

        # A signed-in trainee can also take tests their trainer released. Tests
        # run against the server (not offline), so this only appears when signed
        # in with a working backend.
        tests_button = ft.Button(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.ASSIGNMENT_TURNED_IN_ROUNDED,
                        color=self.color_on_primary,
                        size=action_text_size,
                    ),
                    ft.Text(
                        "Tests",
                        weight=ft.FontWeight.W_800,
                        size=action_text_size,
                        color=self.color_on_primary,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=self._get_pad(8),
            ),
            on_click=lambda e: self.open_tests(),
            height=action_height,
            style=self.make_button_style(self.color_info, radius=8),
        )

        # Offline users manage their own CSV files. A signed-in trainee gets
        # quizzes from their trainer instead, so importing and deleting would
        # only be confusing — statistics and the quiz list are enough.
        bottom_controls: list[ft.Control] = []
        if self.profile is not None and self.backend.available:
            bottom_controls.append(tests_button)
        bottom_controls.append(stat_button)
        if self.profile is None:
            bottom_controls.append(
                ft.Row(
                    controls=[
                        action_btn("Import", self.color_success, self.upload_csv),
                        action_btn("Delete", self.color_danger, self.remove_csv),
                    ],
                    spacing=btn_spacing,
                )
            )

        action_buttons = ft.Container(
            content=ft.Column(
                controls=bottom_controls,
                spacing=btn_spacing,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=ft.Padding.only(
                left=container_pad,
                right=container_pad,
                top=self._get_pad(10),
                bottom=self._get_pad(20),
            ),
        )

        root_controls = [self._account_bar()]
        if invites_banner is not None:
            root_controls.append(invites_banner)
        root_controls += [quiz_area, action_buttons]
        self._set_root(*root_controls)
        self.page.update()

    def open_tests(self) -> None:
        """Open the server-backed tests screen (signed-in trainees only)."""
        TestsView(self).open()

    # ------------------------------------------------------------------
    # Group invitations (trainee side)
    # ------------------------------------------------------------------
    def _invitations_banner(self) -> ft.Control | None:
        """A card per pending group invitation, with Accept / Decline.

        Only for signed-in users. Loaded lazily and cached, so the repeated
        start-page renders triggered by window resizes don't hammer the
        network — the cache is cleared whenever an invitation is acted on.
        """
        if self.profile is None or not self.backend.available:
            return None

        if self._pending_invites is None:
            try:
                self._pending_invites = self.backend.pending_invitations()
            except Exception:
                self._pending_invites = []

        if not self._pending_invites:
            return None

        cards: list[ft.Control] = []
        for inv in self._pending_invites:
            who = inv["trainer_name"] or "A trainer"
            cards.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                f"{who} invited you to",
                                size=self._get_text_size(13),
                                color=self.color_muted,
                            ),
                            ft.Text(
                                inv["group_name"],
                                size=self._get_text_size(18),
                                weight=ft.FontWeight.BOLD,
                                color=self.color_text,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Button(
                                        content="Accept",
                                        on_click=lambda e, m=inv["id"]: self._accept_invite(m),
                                        expand=True,
                                        style=self.make_button_style(
                                            self.color_success, radius=8
                                        ),
                                    ),
                                    ft.Button(
                                        content="Decline",
                                        on_click=lambda e, m=inv["id"]: self._decline_invite(m),
                                        expand=True,
                                        style=self.make_button_style(
                                            self.color_surface,
                                            radius=8,
                                            color=self.color_text,
                                            side=ft.BorderSide(
                                                1, self.color_border_strong
                                            ),
                                        ),
                                    ),
                                ],
                                spacing=self._get_pad(8),
                            ),
                        ],
                        spacing=self._get_pad(6),
                        tight=True,
                    ),
                    bgcolor=self.color_surface,
                    border=ft.Border.all(1, self.color_border),
                    border_radius=10,
                    padding=self._get_pad(14),
                    margin=ft.Margin.only(bottom=self._get_pad(8)),
                )
            )

        return ft.Container(
            content=ft.Column(controls=cards, spacing=0, tight=True),
            padding=ft.Padding.only(
                left=self._get_pad(self._side_padding()),
                right=self._get_pad(self._side_padding()),
                top=self._get_pad(8),
            ),
        )

    def _accept_invite(self, member_id: str) -> None:
        try:
            self.backend.accept_invitation(member_id)
            self.show_message("Invitation accepted.")
        except Exception as ex:
            self.show_message(f"Could not accept: {ex}")
        self._pending_invites = None
        self.show_startpage()

    def _decline_invite(self, member_id: str) -> None:
        try:
            self.backend.decline_invitation(member_id)
            self.show_message("Invitation declined.")
        except Exception as ex:
            self.show_message(f"Could not decline: {ex}")
        self._pending_invites = None
        self.show_startpage()

    def _account_bar(self) -> ft.Control:
        """Top-right account button: the entry point to profile actions."""
        if self.profile is not None:
            icon = ft.Icons.ACCOUNT_CIRCLE_ROUNDED
            handler = lambda e: self._show_account_menu()  # noqa: E731
        elif self.backend.available:
            # Offline by choice — offer the way back to the login screen.
            icon = ft.Icons.LOGIN_ROUNDED
            handler = lambda e: self.auth_view.show()  # noqa: E731
        else:
            return ft.Container(height=self._get_pad(4))

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.IconButton(
                        icon=icon,
                        icon_color=self.color_muted,
                        icon_size=self._get_text_size(30),
                        on_click=handler,
                    )
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
            padding=ft.Padding.only(
                right=self._get_pad(self._side_padding()),
                top=self._get_pad(2),
            ),
        )

    def _show_account_menu(self) -> None:
        """Minimal account sheet.

        Password change, account deletion and the trainer/trainee switch land
        here in the next step; for now it identifies the user and offers a way
        back out.
        """
        if self.profile is None:
            return
        profile = self.profile

        def sign_out(_):
            self._dismiss_dialog()
            self.sign_out()

        dialog = self._centered_dialog(
            "Account",
            ft.Column(
                controls=[
                    ft.Text(
                        profile.display_name,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(profile.email, text_align=ft.TextAlign.CENTER),
                    ft.Text(
                        f"Role: {profile.role}",
                        color=self.color_muted,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
            actions=[
                ft.Button(
                    content="My groups",
                    on_click=lambda _: self._show_my_groups(),
                ),
                ft.Button(content="Sign out", on_click=sign_out),
                ft.Button(content="Close", on_click=lambda _: self._dismiss_dialog()),
            ],
        )
        self.page.show_dialog(dialog)
        self.page.update()

    def _show_my_groups(self) -> None:
        """List the groups the trainee has joined, with a Leave button each."""
        self._dismiss_dialog()
        try:
            groups = self.backend.my_groups()
        except Exception as ex:
            self.show_message(f"Could not load groups: {ex}")
            return

        if not groups:
            body: ft.Control = ft.Text(
                "You are not in any group yet. When a trainer invites you, the "
                "invitation shows up on the start page.",
                text_align=ft.TextAlign.CENTER,
            )
            rows: list[ft.Control] = []
        else:
            rows = []
            for g in groups:
                rows.append(
                    ft.Row(
                        controls=[
                            ft.Text(
                                g["group_name"],
                                weight=ft.FontWeight.W_600,
                                color=self.color_text,
                                expand=True,
                            ),
                            ft.Button(
                                content="Leave",
                                on_click=lambda e, m=g["member_id"]: self._leave_group(m),
                                style=self.make_button_style(
                                    self.color_danger, radius=8
                                ),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )
            body = ft.Column(controls=rows, tight=True, spacing=self._get_pad(10))

        dialog = self._centered_dialog(
            "My groups",
            body,
            actions=[
                ft.Button(content="Close", on_click=lambda _: self._dismiss_dialog()),
            ],
        )
        self.page.show_dialog(dialog)
        self.page.update()

    def _leave_group(self, member_id: str) -> None:
        self._dismiss_dialog()
        try:
            self.backend.leave_group(member_id)
            self.show_message("You left the group.")
        except Exception as ex:
            self.show_message(f"Could not leave: {ex}")
        self._pending_invites = None
        self.show_startpage()

    def load_custom_quizzes(self) -> None:
        self.quiz_buttons.clear()
        side_padding = self._side_padding()

        try:
            files = self._list_quiz_files()
        except OSError:
            return

        for file_name in files:
            filepath = str(Path(self.quiz_folder) / file_name)
            button_text = Path(file_name).stem

            quiz_button = ft.Button(
                content=button_text,
                data=filepath,
                expand=True,
                on_click=lambda e, f=filepath: self.start_quiz(f),
                style=self.make_button_style(
                    self.color_primary,
                    text_size=self._get_text_size(31),
                    weight=ft.FontWeight.W_700,
                    padding=ft.Padding.symmetric(
                        horizontal=self._get_pad(12),
                        vertical=self._get_pad(18),
                    ),
                ),
            )

            self.quiz_buttons.append(
                ft.Container(
                    content=ft.Row([quiz_button]),
                    padding=ft.Padding.symmetric(
                        horizontal=self._get_pad(side_padding),
                        vertical=self._get_pad(4),
                    ),
                )
            )

    def show_statistics(self) -> None:
        self._current_view = "statistics"
        self._refresh_layout_cache(force=True)
        side_padding = self._side_padding()
        container_pad = self._get_pad(side_padding)

        header = ft.Container(
            content=ft.Text(
                "Statistics",
                font_family="Fredoka",
                size=self._get_text_size(44),
                weight=ft.FontWeight.BOLD,
                color=self.color_text,
            ),
            padding=ft.Padding.only(top=self._get_pad(16), bottom=self._get_pad(6)),
            alignment=ft.Alignment.CENTER,
        )

        subtitle = ft.Container(
            content=ft.Text(
                "How often you've completed each quiz",
                size=self._get_text_size(16),
                color=self.color_muted,
                text_align=ft.TextAlign.CENTER,
            ),
            padding=ft.Padding.only(bottom=self._get_pad(10)),
            alignment=ft.Alignment.CENTER,
        )

        try:
            files = self._list_quiz_files()
        except OSError:
            files = []

        rows: list[ft.Control] = []
        if not files:
            rows.append(
                ft.Container(
                    content=ft.Text(
                        "No quizzes yet.",
                        size=self._get_text_size(20),
                        color=self.color_muted,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    alignment=ft.Alignment.CENTER,
                    padding=self._get_pad(30),
                )
            )
        else:
            for file_name in files:
                name = Path(file_name).stem
                path = str(Path(self.quiz_folder) / file_name)
                count = self._get_completion_count(file_name)
                card = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text(
                                name,
                                size=self._get_text_size(24),
                                weight=ft.FontWeight.W_700,
                                color=self.color_text,
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    f"{count}×",
                                    size=self._get_text_size(24),
                                    weight=ft.FontWeight.BOLD,
                                    color=self.color_primary_ink,
                                ),
                                bgcolor=self.color_primary_soft,
                                border_radius=6,
                                padding=ft.Padding.symmetric(
                                    horizontal=self._get_pad(14),
                                    vertical=self._get_pad(6),
                                ),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=self.color_surface,
                    border=ft.Border.all(1, self.color_border),
                    border_radius=10,
                    padding=ft.Padding.symmetric(
                        horizontal=self._get_pad(16), vertical=self._get_pad(14)
                    ),
                    on_click=lambda e, p=path, n=name: self._ask_start_quiz(p, n),
                )
                rows.append(
                    ft.Container(
                        content=card,
                        padding=ft.Padding.symmetric(
                            horizontal=container_pad, vertical=self._get_pad(5)
                        ),
                    )
                )

        stat_list = ft.Column(
            controls=rows,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
        )

        # Home button styled like the one on the result page: a compact,
        # rounded icon button, centred. Next to it a reset button that clears
        # all completion counts (behind a confirmation).
        home = ft.Container(
            content=ft.Row(
                controls=[
                    self._icon_button(
                        ft.Icons.HOME_ROUNDED,
                        self.color_info,
                        lambda e: self.show_startpage(),
                        size=100,
                        pad=38,
                        radius=28,
                    ),
                    self._icon_button(
                        ft.Icons.RESTART_ALT_ROUNDED,
                        self.color_danger,
                        lambda e: self._ask_reset_statistics(),
                        size=100,
                        pad=38,
                        radius=28,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=self._get_pad(16),
            ),
            padding=ft.Padding.only(
                left=container_pad,
                right=container_pad,
                top=self._get_pad(10),
                bottom=self._get_pad(24),
            ),
        )

        self._set_root(header, subtitle, stat_list, home)
        self.page.update()

    def _ask_reset_statistics(self) -> None:
        def reset(_):
            self._dismiss_dialog()
            self._reset_statistics()

        dialog = self._centered_dialog(
            "Reset statistics?",
            ft.Text(
                "This will set the completion count of every quiz back to "
                "zero. This cannot be undone.",
                text_align=ft.TextAlign.CENTER,
            ),
            actions=[
                ft.Button(content="Reset", on_click=reset),
                ft.Button(content="Cancel", on_click=lambda _: self._dismiss_dialog()),
            ],
        )
        self.page.show_dialog(dialog)
        self.page.update()

    def _reset_statistics(self) -> None:
        self.state["stats"] = {}
        self._save_state()
        self.show_statistics()
        self.show_message("Statistics have been reset.")

    async def upload_csv(self, e) -> None:
        try:
            files = await self.file_picker.pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["csv"],
                with_data=True,
            )

            if not files:
                return

            selected_file = files[0]
            original_filename = selected_file.name or "upload.csv"

            if not original_filename.lower().endswith(".csv"):
                self.show_message("Error: Only CSV files can be imported!")
                return

            file_path = getattr(selected_file, "path", None)
            destination = self._get_quiz_destination(original_filename)

            if file_path:
                quiz_text = Path(file_path).read_text(encoding="utf-8")
            elif selected_file.bytes is not None:
                quiz_text = selected_file.bytes.decode("utf-8")
            else:
                self.show_message("Error: No access to file content.")
                return

            questions, errors = self._parse_quiz_text(quiz_text)
            if errors:
                self._show_validation_errors(errors)
                return

            if file_path:
                shutil.copy(file_path, destination)
            else:
                Path(destination).write_text(quiz_text, encoding="utf-8")

            self.fragen = questions
            self.current_question = 0
            self.correct_count = 0
            self.wrong_questions = []
            self.selected_answer = None
            self.answer_locked = False

            imported_name = os.path.basename(destination)
            self.show_message(f"Quiz '{imported_name}' imported!")
            self.show_startpage()

        except UnicodeDecodeError:
            self.show_message("File error: File is not UTF-8 encoded.")
        except Exception as ex:
            self.show_message(f"Import error: {ex}")

    def remove_csv(self, e) -> None:
        try:
            files = self._list_quiz_files()
        except OSError as ex:
            self.show_message(f"Error reading the quiz folder: {ex}")
            return

        if not files:
            self.show_message("No quizzes available.")
            return

        dropdown = ft.Dropdown(
            label="Choose a file",
            options=[ft.dropdown.Option(file_name) for file_name in files],
        )

        def confirm_remove(_):
            selected_file = dropdown.value
            if not selected_file:
                self.show_message("Please select a file.")
                return

            try:
                os.remove(os.path.join(self.quiz_folder, selected_file))
                self._dismiss_dialog()
                self.show_message(f"Quiz '{selected_file}' deleted successfully.")
                self.show_startpage()
            except OSError as ex:
                self.show_message(f"Error deleting: {ex}")

        dialog = self._centered_dialog(
            "Delete quiz",
            dropdown,
            actions=[
                ft.Button(content="Delete", on_click=confirm_remove),
                ft.Button(content="Cancel", on_click=lambda _: self._dismiss_dialog()),
            ],
        )

        self.page.show_dialog(dialog)
        self.page.update()

    def _ask_start_quiz(self, filename: str, name: str) -> None:
        def start(_):
            self._dismiss_dialog()
            self.start_quiz(filename)

        dialog = self._centered_dialog(
            "Start quiz?",
            ft.Text(
                f"Do you want to start '{name}'?",
                text_align=ft.TextAlign.CENTER,
            ),
            actions=[
                ft.Button(content="Start", on_click=start),
                ft.Button(content="Cancel", on_click=lambda _: self._dismiss_dialog()),
            ],
        )
        self.page.show_dialog(dialog)
        self.page.update()

    def start_quiz(self, filename: str) -> None:
        quiz_key = os.path.basename(filename)
        progress = self._get_progress(quiz_key)
        if progress:
            self._ask_resume(filename, quiz_key, progress)
        else:
            self._begin_quiz(filename, quiz_key)

    def _begin_quiz(self, filename: str, quiz_key: str) -> None:
        self._clear_progress(quiz_key)
        self.load_questions(filename)
        if self.fragen:
            self.active_quiz_key = quiz_key
            self.show_question_page()

    def _resume_quiz(self, filename: str, quiz_key: str, progress: dict) -> None:
        self.fragen = [list(row) for row in progress.get("fragen", [])]
        if not self.fragen:
            self._begin_quiz(filename, quiz_key)
            return
        self.current_question = int(progress.get("current_question", 0))
        self.correct_count = int(progress.get("correct_count", 0))
        self.wrong_questions = [
            list(row) for row in progress.get("wrong_questions", [])
        ]
        self.selected_answer = None
        self.answer_locked = False
        if self.current_question >= len(self.fragen):
            self.current_question = 0
        self.active_quiz_key = quiz_key
        self.show_question_page()

    def _ask_resume(self, filename: str, quiz_key: str, progress: dict) -> None:
        total = len(progress.get("fragen", []))
        at = min(int(progress.get("current_question", 0)) + 1, total)

        def resume(_):
            self._dismiss_dialog()
            self._resume_quiz(filename, quiz_key, progress)

        def restart(_):
            self._dismiss_dialog()
            self._begin_quiz(filename, quiz_key)

        dialog = self._centered_dialog(
            "Resume quiz?",
            ft.Text(
                f"You stopped this quiz at question {at}/{total}. "
                "Do you want to continue or start over?",
                text_align=ft.TextAlign.CENTER,
            ),
            actions=[
                ft.Button(content="Continue", on_click=resume),
                ft.Button(content="Start over", on_click=restart),
            ],
        )
        self.page.show_dialog(dialog)
        self.page.update()

    def _ask_leave_quiz(self, e=None) -> None:
        def interrupt(_):
            self._dismiss_dialog()
            self._save_progress()
            self._go_home()

        def end(_):
            self._dismiss_dialog()
            self._clear_progress(self.active_quiz_key)
            self._go_home()

        dialog = self._centered_dialog(
            "Leave quiz",
            ft.Text(
                "End the quiz or just pause it? Paused quizzes can be resumed "
                "later. Ended quizzes don't count toward your statistics.",
                text_align=ft.TextAlign.CENTER,
            ),
            actions=[
                ft.Button(content="Pause", on_click=interrupt),
                ft.Button(content="End", on_click=end),
            ],
        )
        self.page.show_dialog(dialog)
        self.page.update()

    def _go_home(self) -> None:
        self.active_quiz_key = None
        self.fragen = []
        self.current_question = 0
        self.correct_count = 0
        self.wrong_questions = []
        self.selected_answer = None
        self.answer_locked = False
        self.show_startpage()

    def show_question_page(self) -> None:
        self._current_view = "question"
        self._refresh_layout_cache(force=True)
        side_padding = self._side_padding()

        if self.current_question >= len(self.fragen):
            self.show_result()
            return

        frage_data = self.fragen[self.current_question]

        if len(frage_data) != 6:
            self._set_root(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            self._logo(120),
                            ft.Text(
                                "FILE ERROR!",
                                size=self._get_text_size(40),
                                color=self.color_danger,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Button(
                                content="Back",
                                on_click=lambda e: self.show_startpage(),
                                style=self.make_button_style(
                                    self.color_info,
                                    text_size=self._get_text_size(30),
                                    padding=ft.Padding.all(15),
                                ),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=20,
                    alignment=ft.Alignment.CENTER,
                    expand=True,
                )
            )
            self.page.update()
            return

        # Autosave the pre-answer state so an interrupt or app kill can resume
        # exactly at this (still unanswered) question without double counting.
        self._save_progress()

        self.correct_answer = frage_data[5]
        self.correct_set = {c.strip() for c in frage_data[5].split("|") if c.strip()}
        self.is_multi = len(self.correct_set) > 1
        if not self.answer_locked:
            self.selected_set = set()
        self.action_button = None
        self.answer_buttons = []
        answer_containers: list[ft.Control] = []

        for i in range(1, 5):
            answer_text = frage_data[i]
            if answer_text:
                ans_text = ft.Text(
                    answer_text,
                    size=self._get_text_size(24),
                    weight=ft.FontWeight.W_400,
                    color=self.color_text,
                    text_align=ft.TextAlign.LEFT,
                )
                btn = ft.Button(
                    content=ft.Container(
                        content=ans_text,
                        alignment=ft.Alignment(-1, 0),
                        expand=True,
                    ),
                    data=answer_text,
                    expand=True,
                    on_click=lambda e, a=answer_text: self._on_answer_tap(a),
                    style=ft.ButtonStyle(
                        color=self.color_text,
                        bgcolor=self.color_answer,
                        padding=ft.Padding.symmetric(
                            horizontal=self._get_pad(18),
                            vertical=self._get_pad(16),
                        ),
                        # 14 sits between the input radius (10) and the card
                        # radius (18), so an answer reads softer than a field
                        # but still nested inside the question block.
                        shape=ft.RoundedRectangleBorder(radius=8),
                        # 1px, not 2: a list of options should stay quiet until
                        # one of them is picked.
                        side=ft.BorderSide(1, self.color_answer_border),
                    ),
                )
                self.answer_buttons.append(btn)
                ans_container = ft.Container(
                    content=ft.Row([btn]),
                    padding=ft.Padding.symmetric(
                        horizontal=self._get_pad(side_padding),
                        vertical=self._get_pad(6),
                    ),
                )
                answer_containers.append(ans_container)

        # One button for every question: it reads "Check" until the answer is
        # confirmed (revealing green/red), then becomes "Next" for the next
        # question. Disabled until at least one answer is selected.
        self.action_button = ft.Button(
            content="Next" if self.answer_locked else "Check",
            on_click=self._do_action,
            disabled=(not self.answer_locked) and (not self.selected_set),
            style=self._next_btn_style(),
        )

        # House icon replaces the "Home" label (Material icon rendered from the
        # bundled font — no network request, so DSGVO compliant). Framed with
        # rounded corners.
        home_button = ft.Button(
            content=ft.Icon(
                ft.Icons.HOME_ROUNDED,
                color=self.color_text,
                size=self._get_text_size(40),
            ),
            on_click=self._ask_leave_quiz,
            tooltip="Menu",
            style=self.make_button_style(
                self.color_surface,
                radius=8,
                color=self.color_text,
                side=ft.BorderSide(1, self.color_border_strong),
                padding=ft.Padding.all(self._get_pad(12)),
            ),
        )

        # The question carries the weight through boldness and the whitespace
        # under it, not through sheer size — see the styleguide, §12.
        question_text = ft.Text(
            frage_data[0],
            style=ft.TextStyle(
                size=self._get_text_size(32),
                weight=ft.FontWeight.W_700,
                color=self.color_text,
            ),
        )

        q_container = ft.Container(
            content=question_text,
            alignment=ft.Alignment.TOP_LEFT,
            padding=ft.Padding.only(
                left=self._get_pad(side_padding),
                right=self._get_pad(side_padding),
                top=self._get_pad(25),
                bottom=self._get_pad(26),
            ),
        )

        # The single Check/Next button sits under the last answer, on the right.
        next_container = ft.Container(
            content=self.action_button,
            padding=ft.Padding.only(
                top=self._get_pad(14),
                right=self._get_pad(side_padding),
                bottom=self._get_pad(6),
            ),
            alignment=ft.Alignment.CENTER_RIGHT,
        )

        # Question counter — larger and indented further from the edge.
        progress_text = ft.Text(
            f"{self.current_question + 1}/{len(self.fragen)}",
            style=ft.TextStyle(
                size=self._get_text_size(30),
                weight=ft.FontWeight.W_700,
                color=self.color_text,
            ),
        )

        bottom_container = ft.Container(
            content=ft.Row(
                controls=[
                    home_button,
                    ft.Container(expand=True),
                    progress_text,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.only(
                left=self._get_pad(side_padding + 14),
                right=self._get_pad(side_padding + 14),
                top=self._get_pad(6),
                bottom=self._get_pad(20),
            ),
        )

        content_controls: list[ft.Control] = [q_container]
        if self.is_multi:
            content_controls.append(
                ft.Container(
                    content=ft.Text(
                        "Select all correct answers.",
                        size=self._get_text_size(20),
                        color=self.color_muted,
                    ),
                    padding=ft.Padding.only(
                        left=self._get_pad(side_padding),
                        right=self._get_pad(side_padding),
                        bottom=self._get_pad(6),
                    ),
                )
            )
        content_controls += [*answer_containers, next_container]

        question_content = ft.Column(
            controls=content_controls,
            expand=True,
            spacing=0,
            scroll=ft.ScrollMode.ADAPTIVE,
        )

        self._set_root(question_content, bottom_container)

        # Restore the answered/selected state after a re-render (e.g. rotation).
        if self.answer_locked:
            self._apply_feedback()
            if self.action_button is not None:
                self.action_button.content = "Next"
        else:
            for button in self.answer_buttons:
                self._style_selected(button, button.data in self.selected_set)

        self.page.update()

    def load_questions(self, filename: str, show_errors: bool = True) -> None:
        self.fragen.clear()
        self.selected_answer = None
        self.answer_locked = False

        try:
            with open(filename, "r", encoding="utf-8") as data:
                reader = csv.reader(data, delimiter=";")
                self.fragen, errors = self._parse_quiz_rows(reader)
                if errors:
                    self.fragen.clear()
                    if show_errors:
                        self._show_validation_errors(errors)
        except FileNotFoundError:
            if show_errors:
                self.show_message(f"File '{filename}' not found!")
        except UnicodeDecodeError:
            if show_errors:
                self.show_message(
                    f"File '{filename}' has an invalid encoding (not UTF-8)."
                )
        except PermissionError:
            if show_errors:
                self.show_message(f"No read permission for '{filename}'.")
        except Exception as ex:
            if show_errors:
                self.show_message(f"Error loading file: {ex}")

        self.current_question = 0
        self.correct_count = 0
        self.wrong_questions = []

    def _on_answer_tap(self, answer: str) -> None:
        """Select answers (no feedback yet). Multiple choice toggles each tap;
        single choice keeps only the latest pick."""
        if self.answer_locked:
            return
        if self.is_multi:
            if answer in self.selected_set:
                self.selected_set.discard(answer)
            else:
                self.selected_set.add(answer)
        else:
            self.selected_set = {answer}
        for button in self.answer_buttons:
            self._style_selected(button, button.data in self.selected_set)
        if self.action_button is not None:
            self.action_button.disabled = not self.selected_set
        self.page.update()

    @staticmethod
    def _answer_label(button: ft.Button) -> ft.Text:
        """The Text inside an answer button (Button → Container → Text)."""
        return button.content.content

    def _style_selected(self, button: ft.Button, selected: bool) -> None:
        """Selection is shown by a tinted fill, not by a heavier border."""
        self._paint(
            button,
            self.color_primary_soft if selected else self.color_answer,
            border=self.color_primary if selected else self.color_answer_border,
            ink=self.color_primary_ink if selected else self.color_text,
            bold=selected,
        )

    def _paint(
        self,
        button: ft.Button,
        color: str,
        border: str | None = None,
        ink: str | None = None,
        bold: bool = True,
    ) -> None:
        button.style.bgcolor = color
        button.style.side = ft.BorderSide(1, border or color)
        label = self._answer_label(button)
        label.color = ink or self.color_text
        label.weight = ft.FontWeight.W_600 if bold else ft.FontWeight.W_400

    def _do_action(self, e=None) -> None:
        """One button: first press checks (reveals green/red), next press moves
        on to the following question."""
        if self.answer_locked:
            self.next_question()
            return
        if not self.selected_set:
            return
        self.answer_locked = True
        if self.selected_set == self.correct_set:
            self.correct_count += 1
        else:
            self.wrong_questions.append(self.fragen[self.current_question])
        self._apply_feedback()
        if self.action_button is not None:
            self.action_button.content = "Next"
        self.page.update()

    def _apply_feedback(self) -> None:
        for button in self.answer_buttons:
            answer = button.data
            is_correct = answer in self.correct_set
            was_selected = answer in self.selected_set
            if is_correct and was_selected:
                self._paint(
                    button,
                    self.color_success_soft,
                    border=self.color_success,
                    ink=self.color_success_ink,
                )
            elif is_correct and not was_selected:
                # A correct answer the user missed: much softer green for
                # multiple choice, the full green for single choice.
                if self.is_multi:
                    self._paint(
                        button,
                        self.color_success_faint,
                        border=self.color_success,
                        ink=self.color_success_ink,
                        bold=False,
                    )
                else:
                    self._paint(
                        button,
                        self.color_success_soft,
                        border=self.color_success,
                        ink=self.color_success_ink,
                    )
            elif was_selected and not is_correct:
                self._paint(
                    button,
                    self.color_danger_soft,
                    border=self.color_danger,
                    ink=self.color_danger_ink,
                )
            button.disabled = True

    def next_question(self, e=None) -> None:
        self.current_question += 1
        self.selected_set = set()
        self.selected_answer = None
        self.answer_locked = False
        self.show_question_page()

    def show_result(self) -> None:
        # Only a fully finished full quiz counts as completed. Record it once,
        # then clear the flag so a resize re-render can't double count.
        if self.active_quiz_key:
            self._record_completion(self.active_quiz_key)
            self._clear_progress(self.active_quiz_key)
            self.active_quiz_key = None

        self._current_view = "result"
        self._refresh_layout_cache(force=True)
        total = len(self.fragen)
        correct = self.correct_count
        wrong = total - correct
        score = round(correct / total * 100, 1) if total > 0 else 0.0
        side_padding = self._side_padding()

        # Percentage colour: green above 80 %, red below, orange at exactly 80 %.
        if score > 80:
            pct_color = self.color_success
        elif score < 80:
            pct_color = self.color_danger
        else:
            pct_color = self.color_warning

        title = ft.Container(
            content=ft.Text(
                "Result",
                size=self._get_text_size(44),
                weight=ft.FontWeight.BOLD,
                color=self.color_text,
                text_align=ft.TextAlign.CENTER,
            ),
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.only(
                top=self._get_pad(16), bottom=self._get_pad(2)
            ),
        )

        # Consistent, pleasant vertical gap reused between sections.
        gap = self._get_pad(30)
        page_w = int(self.page.width or 600)
        page_h = int(self.page.height or 800)
        landscape = page_w > page_h

        percent = ft.Text(
            f"{score} %",
            size=self._get_text_size(88),
            weight=ft.FontWeight.BOLD,
            color=pct_color,
            text_align=ft.TextAlign.CENTER,
        )

        # Large icon buttons — about twice the previous size. The score boxes
        # use the exact same square footprint and corner radius.
        big_icon, big_pad, big_radius = 100, 38, 28
        box_side = self._get_text_size(big_icon) + 2 * self._get_pad(big_pad)

        def score_card(label: str, value: int, color: str, ink: str) -> ft.Container:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            label,
                            size=self._get_text_size(22),
                            weight=ft.FontWeight.W_600,
                            color=ink,
                        ),
                        ft.Text(
                            str(value),
                            size=self._get_text_size(56),
                            weight=ft.FontWeight.W_800,
                            color=ink,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=self._get_pad(4),
                ),
                width=box_side,
                height=box_side,
                bgcolor=color,
                border_radius=big_radius,
                alignment=ft.Alignment.CENTER,
            )

        # Score boxes: same size/format as the Repeat button, centred.
        score_row = ft.Container(
            content=ft.Row(
                controls=[
                    score_card(
                        "Correct",
                        correct,
                        self.color_success_soft,
                        self.color_success_ink,
                    ),
                    score_card(
                        "Wrong", wrong, self.color_danger_soft, self.color_danger_ink
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=gap,
            ),
            padding=ft.Padding.symmetric(horizontal=self._get_pad(side_padding)),
        )

        repeat_block: ft.Control | None = None
        if wrong > 0:
            repeat_block = ft.Row(
                controls=[
                    self._icon_button(
                        ft.Icons.REPLAY_ROUNDED,
                        self.color_warning,
                        self.restart_wrong_questions,
                        size=big_icon,
                        pad=big_pad,
                        radius=big_radius,
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            )

        home_button = self._icon_button(
            ft.Icons.HOME_ROUNDED,
            self.color_info,
            lambda e: self._go_home(),
            size=big_icon,
            pad=big_pad,
            radius=big_radius,
        )

        if landscape:
            # Landscape: two columns side by side so everything fits on the
            # shorter screen — score on the left, action buttons on the right.
            right_controls: list[ft.Control] = []
            if repeat_block is not None:
                right_controls.append(repeat_block)
            right_controls.append(
                ft.Row([home_button], alignment=ft.MainAxisAlignment.CENTER)
            )

            body = ft.Row(
                controls=[
                    ft.Column(
                        controls=[ft.Container(percent, alignment=ft.Alignment.CENTER), score_row],
                        expand=True,
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=gap,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    ft.Column(
                        controls=right_controls,
                        expand=True,
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=gap,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                ],
                expand=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            self._set_root(title, body)
            self.page.update()
            return

        # Portrait: title pinned at the top, home button pinned at the bottom,
        # and the score/repeat block fills the space between — scrolling only if
        # it would not otherwise fit, so nothing ever overflows off-screen.
        middle_controls: list[ft.Control] = [
            ft.Container(
                content=percent,
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.only(top=self._get_pad(6), bottom=self._get_pad(16)),
            ),
            score_row,
        ]
        if repeat_block is not None:
            middle_controls.append(
                ft.Container(
                    content=repeat_block,
                    padding=ft.Padding.only(top=gap),
                    alignment=ft.Alignment.CENTER,
                )
            )

        middle = ft.Column(
            controls=middle_controls,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
        )

        home_bar = ft.Container(
            content=ft.Row(
                controls=[home_button],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            padding=ft.Padding.only(top=self._get_pad(10), bottom=self._get_pad(30)),
        )

        self._set_root(title, middle, home_bar)
        self.page.update()

    def restart_wrong_questions(self, e) -> None:
        self.fragen = self.wrong_questions.copy()
        self.wrong_questions = []
        self.current_question = 0
        self.correct_count = 0
        self.selected_answer = None
        self.answer_locked = False
        # A retry-only run is not the full quiz, so it must not be saved as
        # progress nor counted as a completion.
        self.active_quiz_key = None
        self.show_question_page()

    def _back_btn_style(self) -> ft.ButtonStyle:
        return ft.ButtonStyle(
            text_style=ft.TextStyle(
                size=self._get_text_size(22),
                weight=ft.FontWeight.W_800,
            ),
            color=self.color_on_primary,
            bgcolor=self.color_info,
            padding=ft.Padding.symmetric(
                horizontal=self._get_pad(18),
                vertical=self._get_pad(14),
            ),
            shape=ft.RoundedRectangleBorder(radius=8),
        )

    def _next_btn_style(self) -> ft.ButtonStyle:
        # Large by default; _get_text_size/_get_pad scale it down automatically
        # on smaller screens so it always fits.
        return ft.ButtonStyle(
            text_style=ft.TextStyle(
                size=self._get_text_size(34),
                weight=ft.FontWeight.W_700,
            ),
            # The one filled primary action on the screen.
            color=self.color_on_primary,
            bgcolor={
                ft.ControlState.DEFAULT: self.color_primary,
                ft.ControlState.PRESSED: self.color_primary_press,
                ft.ControlState.DISABLED: ft.Colors.with_opacity(
                    0.4, self.color_primary
                ),
            },
            padding=ft.Padding.symmetric(
                horizontal=self._get_pad(26),
                vertical=self._get_pad(18),
            ),
            shape=ft.RoundedRectangleBorder(radius=8),
        )

    def _on_resize(self, e) -> None:
        width = int(self.page.width or 600)
        height = int(self.page.height or 800)
        signature = (width // 16, height // 16, self._current_view)

        if signature == self._last_resize_signature:
            return

        self._last_resize_signature = signature
        self._render_current_view()

async def main(page: ft.Page):
    try:
        QuizApp(page)
    except Exception as ex:
        # Surface startup failures instead of leaving a black screen (e.g. on TestFlight).
        import traceback

        page.controls.clear()
        page.controls.append(
            ft.SafeArea(
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("Startup error", size=24, color="#DC2626"),
                            ft.Text(f"{type(ex).__name__}: {ex}", selectable=True),
                            ft.Text(traceback.format_exc(), size=10, selectable=True),
                        ],
                        scroll=ft.ScrollMode.ADAPTIVE,
                    ),
                    padding=20,
                    expand=True,
                ),
                expand=True,
            )
        )
        page.update()
        return

    if not page.web and page.platform is not None and not page.platform.is_mobile():
        try:
            await page.window.center()
            page.update()
        except Exception:
            pass


if __name__ == "__main__":
    ft.run(main)
