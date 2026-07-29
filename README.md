# LearnPlatform

<p align="center">
  <img src="src/assets/icon.png" alt="LearnPlatform Logo" width="512" />
</p>

LearnPlatform is a training and quiz management platform with two front ends over one Supabase backend:

| | Built with | Who it is for | What it does |
| --- | --- | --- | --- |
| **Mobile app** (`src/`) | Flet | Trainees, and anyone without an account | Play quizzes, see statistics, manage groups they belong to |
| **Web app** (`web/`) | FastAPI + HTMX | Trainers and trainees | Create quizzes and tests, manage groups and courses, invite trainees, track results |

The split is deliberate. Playing a quiz is a mobile job; administering groups,
quizzes, courses and tests is a forms-and-tables job that a real HTML front end
handles better than a Flutter canvas. Row Level Security lives in the database,
so both front ends are bound by the same rules and neither can bypass the other.

## What the platform does

### Mobile app (trainees)

- Lists available quiz files.
- Upload and delete quiz CSV files directly in the app.
- Validates CSV data before a quiz starts.
- Runs one question at a time with immediate feedback.
- Shows result statistics (correct/wrong + score in percent).
- Supports "repeat incorrect questions" for focused practice.
- Saves an interrupted quiz so you can resume or start over.
- Statistics page showing completion counts with a reset button.
- Optional accounts backed by Supabase, or offline via "Continue without login".

### Web app (trainers + trainees)

**Trainers** can:

- **Groups** -- create groups, invite trainees by e-mail, remove members. Drag-and-drop to reorder groups. Invitees get a notification mail and accept in the mobile app.
- **Courses** -- bundle groups and materials under a single course. Assign multiple groups to a course, upload files (PDF, images, Excel, Word, CSV, text, max 20 MB) that trainees can download.
- **Quizzes** -- build in the browser (2-4 answers per question), import CSV, export CSV, release to groups.
- **Tests** -- formal exams built from quizzes. Set pass mark, attempt limit, time limit, expiry date, random or hand-picked questions. Release to groups, view per-trainee results, reset attempts.
- **Dashboard** -- customisable overview: choose which widgets to show (stats, recent tests, quizzes, groups, open-test notifications).
- **Settings** -- edit first/last name, customise the dashboard, switch language and theme, change role, delete account.

**Trainees** can:

- Take released tests in the browser or mobile app.
- Browse courses and download course materials.
- See their own test results.

## Accounts and Supabase

The app starts on a login screen with a **Continue without login** button.
Offline use keeps all behaviour described above for the mobile side; nothing
leaves the device.

Setup:

1. Create a project at <https://supabase.com>.
2. Run the migrations in `supabase/migrations/` in order in the Supabase SQL editor. They create tables, RLS policies and triggers.
3. Copy `.env.example` to `.env` and fill in `SUPABASE_URL` and `SUPABASE_ANON_KEY` (Project Settings -> API).

Without `.env` the app skips the login screen and goes straight to offline mode.

### Database migrations

Run in order:

| Migration | Adds |
| --- | --- |
| `0001_init.sql` | Core tables: `profiles`, `groups`, `group_members`, `quizzes`, `quiz_shares` |
| `0002_...` through `0007_...` | Tests tables: `tests`, `test_sources`, `test_questions`, `test_pool`, `test_shares`, `test_attempts` |
| `0008_courses.sql` | `courses`, `course_groups`, `course_files` tables |
| `0009_groups_sort.sql` | `groups.sort_order` column for drag-and-drop ordering |
| `0010_tests_expires.sql` | `tests.expires_at` column for test expiry dates |

### Data model

| Table | Purpose |
| --- | --- |
| `profiles` | Name, e-mail, role (`trainer`/`trainee`), currently active view |
| `groups` | A trainer's group, with a name and drag-and-drop sort order |
| `group_members` | Membership and invitations (`invited` -> `accepted`) |
| `quizzes` | Quiz CSV uploaded by a trainer |
| `quiz_shares` | Which quiz is released to which group |
| `courses` | A course bundling groups and uploaded files |
| `course_groups` | Which groups belong to a course |
| `course_files` | Files uploaded to a course (stored as binary in Supabase) |
| `tests` | An exam: pass mark, attempts, mode, time limit, optional expiry date |
| `test_sources` | For random tests: which quiz with what weight |
| `test_questions` | The frozen question set (manual or fixed random) |
| `test_pool` | Candidate questions for a per-trainee random draw |
| `test_shares` | Which test is released to which group |
| `test_attempts` | One row per attempt: snapshot, score, pass/fail |

## Running the web app

```bash
uv run uvicorn main:app --reload --app-dir web
```

Then open <http://127.0.0.1:8000>. Reads the same `.env` as the mobile app
and additionally requires `WEB_SESSION_SECRET` (generate one with
`python -c "import secrets; print(secrets.token_urlsafe(48))"`).

To enable **taking tests**, also set `SUPABASE_SERVICE_ROLE_KEY` (Project
Settings -> API -> `service_role`). It bypasses RLS so the server can draw
questions and score attempts without exposing the answer key -- it stays only
on the server and must never be compiled into the mobile app.

Behind a real domain set `QUIZMONKEY_HTTPS=1` so the session cookie is
sent over TLS only.

## Running the mobile app

```bash
uv run flet run            # desktop
uv run flet run --web      # browser
```

## Build targets

```bash
flet build apk -v          # Android
flet build ipa -v          # iOS
flet build macos -v        # macOS
flet build linux -v        # Linux
flet build windows -v      # Windows
flet build web -v          # Web
```

## Web app: UI overview

### Navigation

- **Left sidebar** -- nav links (Dashboard, Groups, Courses, Quizzes, Tests), user name + role badge, Privacy + Imprint links
- **Top right gear icon** -- dropdown menu: Settings, Sign out

### Settings

- Edit first and last name
- Customise which dashboard widgets are visible
- Switch language (DE / EN) and theme (Light / Dark)
- Switch role (Trainer / Trainee)
- Delete account (requires typing your e-mail to confirm)

### Groups

- Vertical list, compact: group name + member count + Open/Delete buttons
- Drag-and-drop to reorder; order is persisted immediately

### Courses

- Create courses with a name and optional description
- Assign any of your groups to a course (trainees in those groups can see the course)
- Upload files (PDF, JPEG, PNG, GIF, WEBP, TXT, CSV, XLS, XLSX, DOC, DOCX, max 20 MB)
- Trainees browse courses and download files

### Tests

- Optional expiry date: after this date no new attempts can be started
- Open-attempt notifications on the dashboard: a warning banner lists tests where trainees have not yet submitted

### Dashboard

Widgets can be individually toggled in Settings:
- Statistics strip (group/trainee/quiz/test counts for trainers; released/open-test counts for trainees)
- Recent tests (with open-attempt badges for trainers)
- Recently changed quizzes
- Your groups
- Open-test notification banner

## Quiz CSV format

```text
question;answer1;answer2;answer3;answer4;correctAnswer
```

- Delimiter is `;` (semicolon), not comma.
- No header row.
- Exactly 6 fields per row.
- At least 2 non-empty answer options required.
- Empty answer cells are allowed for shorter questions.
- `correctAnswer` must exactly match one of `answer1..answer4` (case- and whitespace-sensitive).
- Multiple correct answers: separate with `|` in `correctAnswer` (e.g. `Vienna|Graz`).
- File must be UTF-8 encoded.

## Privacy and GDPR / DSGVO

- **No third-party requests.** Fonts are the visitor's own system fonts, htmx is served from `web/static`. A strict Content Security Policy enforces this -- no visitor IP leaks to any CDN.
- **Strictly necessary cookies only**: `qm_session` (signed, HttpOnly, SameSite=Lax), `qm_lang` (language preference, 2-char code), `qm_theme` (light/dark), `qm_dash` (dashboard widget prefs). No analytics, no tracking, no consent banner required.
- **Legal pages** at `/privacy` and `/imprint`. Both contain `[PLACEHOLDER]` markers to fill in before going live (controller details, hosting provider, Supabase DPA, dates).
- **Betroffenenrechte** (Art. 15-20 DSGVO): account deletion is available directly in Settings; users type their e-mail to confirm permanent deletion.
- Before launch: fill the placeholders, conclude the Supabase DPA (<https://supabase.com/legal/dpa>), confirm your database region.

## Tech stack

- Python `>=3.11`
- Flet `0.82.0` (mobile app)
- FastAPI + Jinja2 + HTMX (web app)
- Supabase (auth + database)

## Repository structure

```text
src/
  main.py          -- mobile app entry point
  auth_ui.py
  backend.py
  tests_ui.py
  quiz_csv.py
  quizzes/
  assets/
web/
  main.py          -- FastAPI application
  i18n.py          -- DE/EN translations
  auth.py
  email_out.py
  templates/       -- Jinja2 HTML templates
  static/          -- CSS, JS, htmx
supabase/
  migrations/
README.md
LICENSE
pyproject.toml
```

## License

MIT License -- see `LICENSE` for the full text.

Dependencies (including Flet) are separate third-party software and keep their own licenses.

## Community

- Contribution guide: `CONTRIBUTING.md`
- Security policy: `SECURITY.md`
