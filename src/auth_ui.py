"""Login and sign-up screens.

Kept out of main.py so the quiz UI stays readable. The view borrows the app's
sizing and styling helpers, so it scales with the window exactly like the rest
of the app.
"""

from __future__ import annotations

import flet as ft

from backend import BackendError


class AuthView:
    """Sign-in / sign-up screen with an offline escape hatch."""

    def __init__(self, app) -> None:
        self.app = app
        self.mode = "sign_in"  # or "sign_up"
        self.busy = False

        self.error_text: ft.Text | None = None

        # The input fields are created once and reused on every redraw:
        # switching between sign-in and sign-up re-renders the form, and
        # building fresh TextFields there would throw away what was typed.
        self.first_name_field = self._text_field("First name")
        self.last_name_field = self._text_field("Last name")
        self.email_field = self._text_field(
            "E-mail",
            keyboard=ft.KeyboardType.EMAIL,
            autofill=ft.AutofillHint.EMAIL,
        )
        self.password_field = self._text_field(
            "Password", password=True, can_reveal=True
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def show(self) -> None:
        app = self.app
        app._current_view = "auth"
        app._refresh_layout_cache(force=True)
        pad = app._get_pad(app._side_padding())

        # The fields outlive a redraw, so their font size has to be refreshed
        # here to keep up with a window resize.
        for field in (
            self.first_name_field,
            self.last_name_field,
            self.email_field,
            self.password_field,
        ):
            field.text_size = app._get_text_size(16)

        self.error_text = ft.Text(
            "",
            color=app.color_danger,
            size=app._get_text_size(14),
            text_align=ft.TextAlign.CENTER,
            visible=False,
        )

        controls: list[ft.Control] = [
            app._logo(base_size=96),
            ft.Container(
                content=ft.Text(
                    "QuizMonkey",
                    font_family="Fredoka",
                    size=app._get_text_size(40),
                    weight=ft.FontWeight.BOLD,
                    color=app.color_text,
                ),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.only(bottom=app._get_pad(4)),
            ),
            ft.Container(
                content=ft.Text(
                    "Sign in to see quizzes shared with you"
                    if self.mode == "sign_in"
                    # The mobile app is the trainee app; trainers manage
                    # groups and quizzes in the web version.
                    else "Create your trainee account",
                    size=app._get_text_size(15),
                    color=app.color_muted,
                    text_align=ft.TextAlign.CENTER,
                ),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.only(bottom=app._get_pad(14)),
            ),
        ]

        if self.mode == "sign_up":
            controls += [
                self.first_name_field,
                ft.Container(height=app._get_pad(8)),
                self.last_name_field,
                ft.Container(height=app._get_pad(8)),
            ]

        controls += [
            self.email_field,
            ft.Container(height=app._get_pad(8)),
            self.password_field,
        ]

        controls += [
            ft.Container(height=app._get_pad(16)),
            self.error_text,
            ft.Container(height=app._get_pad(6)),
            self._primary_button(),
            ft.Container(height=app._get_pad(10)),
            self._switch_mode_button(),
        ]

        if self.mode == "sign_in":
            controls.append(self._forgot_password_button())

        controls += [
            ft.Container(height=app._get_pad(18)),
            ft.Divider(color=app.color_border, height=1),
            ft.Container(height=app._get_pad(14)),
            self._offline_button(),
        ]

        if not self.app.backend.available:
            controls.append(self._backend_hint())

        form = ft.Column(
            controls=controls,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
        )

        # Cap the form width on wide windows, but never make it wider than the
        # space left between the side paddings — otherwise labels wrap on
        # phones.
        available = max(240.0, float(app.page.width or 600) - 2 * pad)

        app._set_root(
            ft.Container(
                content=ft.Container(
                    content=form,
                    width=min(available, 460.0),
                ),
                alignment=ft.Alignment.TOP_CENTER,
                padding=ft.Padding.symmetric(
                    horizontal=pad, vertical=app._get_pad(16)
                ),
                expand=True,
            )
        )
        app.page.update()

    # ------------------------------------------------------------------
    # Pieces
    # ------------------------------------------------------------------
    def _text_field(
        self,
        label: str,
        password: bool = False,
        can_reveal: bool = False,
        keyboard: ft.KeyboardType | None = None,
        autofill: ft.AutofillHint | None = None,
    ) -> ft.TextField:
        app = self.app

        def sync(e):
            # Registering a change handler is what makes Flet track the typed
            # text server-side. Without it, control.value stays empty and the
            # next page.update() pushes that emptiness back to the browser,
            # clearing the field under the user's fingers.
            #
            # Flet already assigns control.value before calling us; the
            # assignment below is only a fallback for the payload-carrying
            # variant, and must never overwrite a good value with nothing.
            if isinstance(e.data, str) and e.data:
                e.control.value = e.data

        return ft.TextField(
            label=label,
            # Must be None, not the "" default: Flet only carries the typed
            # text across a redraw when value is None (see TextField.
            # _migrate_state). With "" it treats the empty string as an
            # explicit setting and wipes what the user typed.
            value=None,
            on_change=sync,
            password=password,
            can_reveal_password=can_reveal,
            keyboard_type=keyboard or ft.KeyboardType.TEXT,
            autofill_hints=[autofill] if autofill else None,
            border_radius=10,
            filled=True,
            bgcolor=app.color_surface,
            border_color=app.color_border_strong,
            focused_border_color=app.color_primary,
            color=app.color_text,
            label_style=ft.TextStyle(color=app.color_muted),
            text_size=app._get_text_size(16),
            on_submit=lambda e: self._submit(),
        )

    def _primary_button(self) -> ft.Control:
        app = self.app
        label = "Sign in" if self.mode == "sign_in" else "Create account"
        return ft.Button(
            content=ft.Text(
                "Please wait..." if self.busy else label,
                size=app._get_text_size(18),
                weight=ft.FontWeight.BOLD,
                color=app.color_on_primary,
            ),
            on_click=lambda e: self._submit(),
            disabled=self.busy or not app.backend.available,
            height=app._get_pad(52),
            style=app.make_button_style(app.color_success, radius=12),
        )

    def _switch_mode_button(self) -> ft.Control:
        app = self.app
        label = (
            "No account yet? Create one"
            if self.mode == "sign_in"
            else "Already have an account? Sign in"
        )

        def toggle(e):
            self.mode = "sign_up" if self.mode == "sign_in" else "sign_in"
            self.show()

        return ft.TextButton(
            content=ft.Text(
                label,
                size=app._get_text_size(14),
                color=app.color_muted,
            ),
            on_click=toggle,
            disabled=not app.backend.available,
        )

    def _forgot_password_button(self) -> ft.Control:
        app = self.app
        return ft.TextButton(
            content=ft.Text(
                "Forgot your password?",
                size=app._get_text_size(13),
                color=app.color_muted,
            ),
            on_click=lambda e: self._reset_password(),
            disabled=self.busy or not app.backend.available,
        )

    def _offline_button(self) -> ft.Control:
        app = self.app
        return ft.Button(
            content=ft.Text(
                "Continue without login",
                size=app._get_text_size(16),
                weight=ft.FontWeight.BOLD,
                color=app.color_on_primary,
            ),
            on_click=lambda e: app.continue_offline(),
            height=app._get_pad(48),
            style=app.make_button_style(app.color_info, radius=12),
        )

    def _backend_hint(self) -> ft.Control:
        app = self.app
        return ft.Container(
            content=ft.Text(
                app.backend.config_error or "Backend unavailable.",
                size=app._get_text_size(12),
                color=app.color_warning,
                text_align=ft.TextAlign.CENTER,
            ),
            padding=ft.Padding.only(top=app._get_pad(12)),
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _values(self) -> tuple[str, str, str, str]:
        return (
            (self.email_field.value or "").strip(),
            self.password_field.value or "",
            (self.first_name_field.value or "").strip(),
            (self.last_name_field.value or "").strip(),
        )

    def _fail(self, message: str) -> None:
        if self.error_text is None:
            return
        self.error_text.value = message
        self.error_text.visible = True
        self.app.page.update()

    def _submit(self) -> None:
        if self.busy or not self.app.backend.available:
            return
        email, password, first, last = self._values()

        if not email or not password:
            self._fail("Please enter your e-mail and password.")
            return
        if self.mode == "sign_up" and (not first or not last):
            self._fail("Please enter your first and last name.")
            return

        self.busy = True
        self.show()
        try:
            if self.mode == "sign_in":
                profile = self.app.backend.sign_in(email, password)
                self.app.enter_signed_in(profile)
                return

            profile = self.app.backend.sign_up(
                email, password, first, last, "trainee"
            )
            if profile is None:
                # The project has e-mail confirmation switched on.
                self.busy = False
                self.mode = "sign_in"
                self.show()
                self.app.show_message(
                    f"Account created. Confirm the e-mail sent to {email}, "
                    "then sign in."
                )
                return
            self.app.enter_signed_in(profile)
        except BackendError as ex:
            self.busy = False
            self.show()
            self._fail(str(ex))
        except Exception as ex:  # network down, DNS, ...
            self.busy = False
            self.show()
            self._fail(f"Could not reach the server: {ex}")

    def _reset_password(self) -> None:
        email, _, _, _ = self._values()
        if not email:
            self._fail("Enter your e-mail address first, then tap again.")
            return
        try:
            self.app.backend.send_password_reset(email)
        except BackendError as ex:
            self._fail(str(ex))
            return
        self.app.show_message("Password reset e-mail sent.")
