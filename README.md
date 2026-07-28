# QuizMonkey

<p align="center">
  <img src="src/assets/icon.png" alt="QuizMonkey Logo" width="512" />
</p>

QuizMonkey is a quiz application with two front ends over one Supabase
backend:

| | Built with | Who it is for | What it does |
| --- | --- | --- | --- |
| **Mobile app** (this repo, `src/`) | Flet | Trainees, and anyone without an account | Play quizzes, see statistics, manage groups they belong to |
| **Web app** (`web/`, in progress) | FastAPI + HTMX | Trainers | Create quizzes, create and manage groups, invite trainees, release quizzes to groups |

The split is deliberate. Playing a quiz is a mobile job; administering groups
and quizzes is a forms-and-tables job that a real HTML front end does better
than a Flutter canvas. Row Level Security lives in the database, so both front
ends are bound by the same rules and neither can bypass the other.

You can run the same app on desktop, mobile or web, load your own quizzes from CSV,
play through questions, and review your results (including retrying only the
incorrect questions).

## What the app does

- Lists all available quiz files.
- Lets you upload and delete quiz CSV files directly in the app.
- Validates CSV data before a quiz starts.
- Runs one question at a time with immediate feedback.
- Shows result statistics (correct/wrong + score in percent).
- Supports "repeat incorrect questions" for focused practice.
- Saves an interrupted quiz so you can resume it later or start over.
- Has a statistics page showing how often each quiz was completed, with a
  reset button (behind a confirmation) to clear all counts.
- Optional accounts backed by Supabase, or use everything offline via
  "Continue without login".

The bottom actions differ by mode, on purpose:

- **Offline**: Import and Delete stay, because these CSV files are the user's
  own and there is nobody else to get quizzes from.
- **Signed in as a trainee**: only Statistic. Quizzes arrive from a trainer, so
  importing and deleting local files would just be confusing.

Sign-up in the mobile app always creates a **trainee**. Trainer accounts belong
to the web app, which is why there is no role picker here.

## Accounts and Supabase

The app starts on a login screen with a **Continue without login** button.
Offline use keeps the behaviour described above: local CSV files, local
statistics, nothing leaves the device.

Signing in is what later unlocks trainer/trainee features (groups, shared
quizzes). Setup:

1. Create a project at <https://supabase.com>.
2. Run [`supabase/migrations/0001_init.sql`](supabase/migrations/0001_init.sql)
   in the Supabase SQL editor. It creates the tables and the Row Level
   Security policies, and can be re-run safely.
3. Copy `.env.example` to `.env` and fill in `SUPABASE_URL` and
   `SUPABASE_ANON_KEY` (Project Settings -> API).

Without a `.env` the app skips the login screen entirely and goes straight to
offline mode, so the backend is genuinely optional.

### E-mail confirmation

This project runs with *Authentication -> Providers -> Email -> Confirm email*
switched **on**. Sign-up therefore does not sign the user in: Supabase returns
no session, the app says so and switches back to the sign-in form. The account
only works once the confirmation link has been opened.

Set *Authentication -> URL Configuration -> Site URL* to wherever the web
version is hosted, so the link in that mail leads somewhere useful. The
confirmation itself works regardless — the link hits Supabase first — but the
page the user lands on afterwards is that Site URL.

Only the **anon** key belongs in `.env` — it is safe for clients because Row
Level Security restricts what it can reach. The `service_role` key bypasses
those policies and must never ship in the app.

### Data model

| Table | Purpose |
| --- | --- |
| `profiles` | Name, e-mail, role (`trainer`/`trainee`), currently active view |
| `groups` | A trainer's group, with a name they choose |
| `group_members` | Membership and invitations (`invited` -> `accepted`) |
| `quizzes` | Quiz CSV uploaded by a trainer |
| `quiz_shares` | Which quiz is released to which group |
| `tests` | An exam: pass mark, attempts, mode, time limit |
| `test_sources` | For random tests: which quiz with what weight |
| `test_questions` | The frozen question set (manual or fixed random) |
| `test_pool` | Candidate questions for a per-trainee random draw |
| `test_shares` | Which test is released to which group |
| `test_attempts` | One row per attempt: snapshot, score, pass/fail |

A new sign-up automatically gets a `profiles` row via a database trigger, which
also links any invitation that was addressed to that e-mail beforehand.

## The web app (trainers)

What a trainer can do there:

- **Groups** — create groups, invite trainees by e-mail address, remove
  members. Invitees get a notification e-mail (see "Outgoing mail" below) and
  accept the invitation in the mobile app.
- **Quizzes** — build them in the browser (2–4 answers per question, one
  marked correct), import an existing CSV, export any quiz back to CSV.
- **Release** — publish a quiz to one or more groups; trainees then see it in
  the mobile app.

### Tests (exams)

A **test** is a formal exam built on top of quizzes, with a pass mark, a limited
number of attempts and no per-question feedback. A trainer can:

- **Build** a test from questions drawn at random across several quizzes with a
  percentage weighting (e.g. 50 % from quiz A, 30 % from B, 20 % from C), or by
  hand-picking individual questions. Set the pass mark, the number of attempts,
  an optional time limit, whether each trainee gets their own random draw or one
  fixed set, and whether a retry re-draws or repeats the same questions.
- **Release** it to groups, like a quiz.
- **See results** — for each trainee: passed or not, on which attempt, and their
  best score. A trainer can reset a trainee's attempts to let them retake.

A trainee takes the test in the browser or in the mobile app. There is no
feedback during the test — only the final percentage, shown green (passed) or
red (not passed).

**Tests are online-only, by design.** Unlike quizzes, the questions are drawn
and the answers are scored **on the server**, so the correct answers never reach
the trainee's device and cannot be read out of the network or database. The
mobile app talks to the same server over its JSON API (`/api/*`) using the
signed-in user's token. This needs `SUPABASE_SERVICE_ROLE_KEY` on the server
(see below); without it, tests can still be created and managed, but not taken.

Test results (pass/fail, score, attempts, time) are personal data — the privacy
policy has a section covering them (legal basis, retention).

### Languages

The web app is available in **German and English**, switchable in the footer
and in the settings. Texts live in [`web/i18n.py`](web/i18n.py) — one flat dict
per language, no gettext and no compile step. Without a language cookie the
browser's `Accept-Language` decides, defaulting to German.

The **mobile app is English only** by design, so its strings stay inline.

The language cookie stores nothing but `de` or `en`, carries no identifier and
is not used for tracking, so it needs no consent banner.

### Outgoing mail

Invitation notices are sent over plain SMTP, configured in `.env`
(`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`). Port 465
uses implicit TLS, anything else STARTTLS. Using your own mail server means no
third-party processor is involved — nothing to declare in the privacy policy
and no Art. 28 agreement needed.

Without SMTP configured, invitations still work; the confirmation message says
plainly that no mail was sent. Sending happens in a background task, so a slow
mail server never delays the trainer, and failures are logged rather than
swallowed.

## Running the web app

```bash
uv run uvicorn main:app --reload --app-dir web
```

Then open <http://127.0.0.1:8000>. It reads the same `.env` as the mobile app
and additionally needs `WEB_SESSION_SECRET` (generate one with
`python -c "import secrets; print(secrets.token_urlsafe(48))"`).

To enable **taking tests**, also set `SUPABASE_SERVICE_ROLE_KEY` (Project
Settings -> API -> `service_role`). It bypasses Row Level Security so the server
can draw questions and score attempts without exposing the answer key; it stays
only on the server and must never be compiled into the mobile app. Without it,
tests can be created and managed but not taken. The mobile app reaches this API
at `PUBLIC_BASE_URL` (override with `QM_API_BASE`).

Run the SQL migrations in `supabase/migrations/` in order in the Supabase SQL
editor; `0006`/`0007` add the tests tables.

Behind a real domain, also set `QUIZMONKEY_HTTPS=1` so the session cookie is
sent over TLS only.

### Privacy & licences (built in on purpose)

- **No third-party requests.** Fonts are the visitor's own system fonts, htmx
  is served from `web/static`. A Content Security Policy (`web/main.py`)
  blocks any external origin, so no visitor IP can leak to a CDN — no Google
  Fonts problem, no cookie banner needed for fonts.
- **One strictly necessary cookie** (`qm_session`), signed + HttpOnly +
  SameSite=Lax. No analytics, no tracking.
- **Legal pages** at `/privacy` and `/imprint`. Both contain `[PLACEHOLDER]`
  markers that must be filled in before going live (controller details,
  hosting provider, Supabase DPA, dates).
- **Open-source components** are all permissively licensed (MIT / BSD /
  Apache-2.0) and none require attribution on the site; they are listed in the
  imprint for transparency.

Before launch: fill the placeholders, conclude the Supabase DPA
(<https://supabase.com/legal/dpa>), and confirm your database region.

## Saved state

Completion counts, interrupted quiz runs and — when signed in — the Supabase
session tokens are stored in a `state.json` file next to the quiz folder
(`$FLET_APP_STORAGE_DATA/state.json` in packaged builds, `src/state.json`
during local development).

The tokens live in the app's sandboxed data directory, not in the iOS Keychain.
That is adequate here, but worth upgrading if accounts ever hold sensitive
data.

Quizzes finished via "repeat incorrect questions" and quizzes you end early do
not count toward the statistics.

## Tech stack

- Python `>=3.11`
- Flet `0.82.0`
- Project entry point: `src/main.py`

## Run locally

Install dependencies with `uv` and run:

```bash
uv run flet run
```

Run web mode:

```bash
uv run flet run --web
```

## Build targets

Use `flet build` for packaging:

```bash
flet build apk -v            # Android
flet build ipa -v            # iOS
flet build ios-simulator -v  # iOS Simulator (.app bundle)
flet build macos -v          # macOS
flet build linux -v          # Linux
flet build windows -v        # Windows
flet build web -v            # Web
```

To try the app in the iPhone Simulator:

```bash
xcrun simctl boot "iPhone 16 Pro"
open -a Simulator
flet build ios-simulator
xcrun simctl install booted build/ios-simulator/quizmonkey.app
xcrun simctl launch booted com.maxdev.monkeyquiz
```

Flet packaging docs: <https://docs.flet.dev/publish/>

## Quiz CSV format

Quiz files are loaded from:

- `src/quizzes/` during local development
- `$FLET_APP_STORAGE_DATA/quizzes/` in packaged app environments

Each row must follow exactly this schema:

```text
question;answer1;answer2;answer3;answer4;correctAnswer
```

Rules:

- Delimiter is `;` (semicolon), not comma.
- No header row.
- Exactly 6 fields per row.
- At least 2 non-empty answer options are required.
- Empty answer cells are allowed for shorter multiple choice sets.
- `correctAnswer` must exactly match one of `answer1..answer4`
  (case- and whitespace-sensitive).
- For a multiple-choice question with **several correct answers**, list them in
  the `correctAnswer` field separated by `|` (e.g. `Vienna|Graz`). Answer texts
  must then not contain `|`. A single correct answer needs no separator.
- File must be UTF-8 encoded.

Examples:

```text
What is the capital city of Austria?;Vienna;Salzburg;Innsbruck;Dresden;Vienna
Which of these are in Austria?;Vienna;Graz;Zurich;Munich;Vienna|Graz
```

## Repository structure

```text
src/
  main.py
  quizzes/
    myFirstQuiz.csv
  assets/
    icon.png
    splash_android.png
README.md
LICENSE
pyproject.toml
```

## License

This project is licensed under the MIT License.

See `LICENSE` for the full text.

## Third-party licenses

This repository's MIT license applies to this project's source code.

Dependencies (including Flet) are separate third-party software and keep their
own licenses.

## Community

- Contribution guide: `CONTRIBUTING.md`
- Security policy: `SECURITY.md`
