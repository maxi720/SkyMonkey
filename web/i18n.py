"""German / English texts for the web app.

One flat dict per language rather than gettext .po files: it is a few hundred
strings, it stays readable in a diff, and it needs no compile step or extra
dependency.

The chosen language lives in a cookie (`qm_lang`). It is strictly necessary for
the interface to work as the user asked, carries no identifier and is not used
for tracking, so it needs no consent banner. When no cookie is set, the
browser's Accept-Language header decides, defaulting to German.
"""

from __future__ import annotations

LANG_COOKIE = "qm_lang"
LANGUAGES = ("de", "en")
DEFAULT_LANG = "de"

TEXTS: dict[str, dict[str, str]] = {
    # -- chrome ------------------------------------------------------------
    "nav.dashboard": {"de": "Übersicht", "en": "Dashboard"},
    "nav.groups": {"de": "Gruppen", "en": "Groups"},
    "nav.quizzes": {"de": "Quizze", "en": "Quizzes"},
    "nav.tests": {"de": "Tests", "en": "Tests"},
    "nav.take": {"de": "Tests", "en": "Tests"},
    "nav.settings": {"de": "Einstellungen", "en": "Settings"},
    "nav.signin": {"de": "Anmelden", "en": "Sign in"},
    "nav.signout": {"de": "Abmelden", "en": "Sign out"},
    "nav.register": {"de": "Konto erstellen", "en": "Create account"},
    "nav.skip": {"de": "Zum Inhalt springen", "en": "Skip to content"},
    "nav.section_manage": {"de": "Verwalten", "en": "Manage"},
    "nav.section_learn": {"de": "Lernen", "en": "Learn"},
    "nav.section_account": {"de": "Konto", "en": "Account"},
    "nav.courses": {"de": "Kurse", "en": "Courses"},
    "footer.privacy": {"de": "Datenschutz", "en": "Privacy"},
    "footer.imprint": {"de": "Impressum", "en": "Imprint"},
    "lang.label": {"de": "Sprache", "en": "Language"},

    # -- login / register --------------------------------------------------
    "login.title": {"de": "Anmelden", "en": "Sign in"},
    "login.lead": {
        "de": "Verwalte deine Gruppen und Quizze.",
        "en": "Manage your groups and quizzes.",
    },
    "login.email": {"de": "E-Mail", "en": "E-mail"},
    "login.password": {"de": "Passwort", "en": "Password"},
    "login.submit": {"de": "Anmelden", "en": "Sign in"},
    "login.no_account": {"de": "Noch kein Konto?", "en": "No account yet?"},
    "login.create_one": {"de": "Jetzt erstellen", "en": "Create one"},
    "login.mobile_hint": {
        "de": "Quizze gespielt werden in der App — hier werden sie erstellt "
              "und verwaltet.",
        "en": "Playing quizzes happens in the mobile app — this site is for "
              "creating and managing them.",
    },
    "login.not_configured": {
        "de": "Dem Server fehlt seine Konfiguration. Siehe README: In der "
              "<code>.env</code> braucht es <code>SUPABASE_URL</code>, "
              "<code>SUPABASE_ANON_KEY</code> und <code>WEB_SESSION_SECRET</code>.",
        "en": "The server is missing its configuration. See the README: "
              "<code>.env</code> needs <code>SUPABASE_URL</code>, "
              "<code>SUPABASE_ANON_KEY</code> and <code>WEB_SESSION_SECRET</code>.",
    },
    "register.title": {"de": "Konto erstellen", "en": "Create account"},
    "register.lead": {
        "de": "Jedes Konto startet als Trainee. In den Einstellungen kannst "
              "du dich selbst zum Trainer machen — solange QuizMonkey in der "
              "frühen Phase ist, kostenlos.",
        "en": "Every account starts as a trainee. You can switch yourself to "
              "trainer in the settings afterwards — free while QuizMonkey is "
              "in early access.",
    },
    "register.first_name": {"de": "Vorname", "en": "First name"},
    "register.last_name": {"de": "Nachname", "en": "Last name"},
    "register.privacy_consent": {
        "de": "Ich habe die %s gelesen und bin einverstanden, dass mein Name "
              "und meine E-Mail-Adresse zum Betrieb meines Kontos verarbeitet "
              "werden.",
        "en": "I have read the %s and agree to my name and e-mail address "
              "being processed to run my account.",
    },
    "register.privacy_link": {
        "de": "Datenschutzerklärung", "en": "privacy policy",
    },
    "register.submit": {"de": "Konto erstellen", "en": "Create account"},
    "register.have_account": {
        "de": "Du hast schon ein Konto?", "en": "Already have an account?",
    },

    # -- dashboard ---------------------------------------------------------
    "dash.hello": {"de": "Hallo, %s", "en": "Hello, %s"},
    "dash.signed_in_as": {"de": "Du bist angemeldet als", "en": "You are signed in as"},
    "dash.groups_title": {"de": "Gruppen", "en": "Groups"},
    "dash.groups_text": {
        "de": "Lege Gruppen an und lade Trainees per E-Mail-Adresse ein.",
        "en": "Create groups and invite trainees by e-mail address.",
    },
    "dash.groups_cta": {"de": "Gruppen verwalten", "en": "Manage groups"},
    "dash.quizzes_title": {"de": "Quizze", "en": "Quizzes"},
    "dash.quizzes_text": {
        "de": "Erstelle Quizze hier oder importiere eine CSV-Datei und gib "
              "sie einer Gruppe frei.",
        "en": "Write quizzes here or upload a CSV, then release them to a group.",
    },
    "dash.quizzes_cta": {"de": "Quizze verwalten", "en": "Manage quizzes"},
    "dash.tests_title": {"de": "Tests", "en": "Tests"},
    "dash.tests_text": {
        "de": "Erstelle Prüfungen aus deinen Quizzen und gib sie Gruppen frei.",
        "en": "Build exams from your quizzes and release them to groups.",
    },
    "dash.tests_cta": {"de": "Tests verwalten", "en": "Manage tests"},
    "dash.take_title": {"de": "Tests machen", "en": "Take a test"},
    "dash.take_text": {
        "de": "Prüfungen, die dir ein Trainer freigegeben hat. Tests brauchen "
              "eine Internetverbindung.",
        "en": "Exams a trainer has released to you. Tests need an internet "
              "connection.",
    },
    "dash.take_cta": {"de": "Zu meinen Tests", "en": "Go to my tests"},
    "dash.trainee_title": {"de": "Du bist Trainee", "en": "You are a trainee"},
    "dash.trainee_text": {
        "de": "Trainees spielen Quizze in der QuizMonkey-App. Quizze "
              "erscheinen dort, sobald ein Trainer sie einer deiner Gruppen "
              "freigibt.",
        "en": "Trainees play quizzes in the QuizMonkey mobile app. Quizzes "
              "appear there as soon as a trainer releases them to a group you "
              "are in.",
    },
    "dash.trainee_switch": {
        "de": "Du willst selbst Quizze und Gruppen anlegen? Ändere deine "
              "Rolle in den Einstellungen.",
        "en": "Want to create quizzes and groups yourself? Switch your role "
              "in the settings.",
    },
    "dash.to_settings": {"de": "Zu den Einstellungen", "en": "Go to settings"},
    "dash.subtitle": {
        "de": "Deine Übersicht auf einen Blick.",
        "en": "Your overview at a glance.",
    },
    "dash.new_test": {"de": "Neuer Test", "en": "New test"},
    "dash.new_quiz": {"de": "Neues Quiz", "en": "New quiz"},
    "dash.stat_groups": {"de": "Gruppen", "en": "Groups"},
    "dash.stat_trainees": {"de": "Trainees", "en": "Trainees"},
    "dash.stat_quizzes": {"de": "Quizze", "en": "Quizzes"},
    "dash.stat_tests": {"de": "Tests", "en": "Tests"},
    "dash.stat_released": {"de": "Freigegebene Tests", "en": "Released tests"},
    "dash.stat_open": {"de": "Noch offen", "en": "Still open"},
    "dash.recent_tests": {"de": "Zuletzt erstellte Tests", "en": "Latest tests"},
    "dash.recent_quizzes": {"de": "Zuletzt geänderte Quizze", "en": "Recently changed quizzes"},
    "dash.your_groups": {"de": "Deine Gruppen", "en": "Your groups"},
    "dash.your_tests": {"de": "Deine Tests", "en": "Your tests"},
    "dash.view_all": {"de": "Alle ansehen", "en": "View all"},
    "dash.results": {"de": "Ergebnisse", "en": "Results"},
    "dash.open": {"de": "Öffnen", "en": "Open"},
    "dash.open_tests_notice": {
        "de": "%s Test(s) mit offenen Abgaben — bitte prüfen:",
        "en": "%s test(s) with open attempts — please review:",
    },
    "dash.open_attempts": {
        "de": "%s offene Abgabe(n)", "en": "%s open attempt(s)",
    },
    "dash.open_attempts_badge": {"de": "offen", "en": "open"},
    "dash.expires": {"de": "Läuft ab", "en": "Expires"},
    "dash.no_quizzes": {"de": "Noch kein Quiz erstellt.", "en": "No quiz created yet."},
    "dash.no_groups": {"de": "Noch keine Gruppe angelegt.", "en": "No group yet."},

    # -- settings ----------------------------------------------------------
    "settings.title": {"de": "Einstellungen", "en": "Settings"},
    "settings.account": {"de": "Konto", "en": "Account"},
    "settings.name": {"de": "Name", "en": "Name"},
    "settings.email": {"de": "E-Mail", "en": "E-mail"},
    "settings.role": {"de": "Rolle", "en": "Role"},
    "role.trainer": {"de": "Trainer", "en": "trainer"},
    "role.trainee": {"de": "Trainee", "en": "trainee"},
    "settings.language": {"de": "Sprache", "en": "Language"},
    "settings.language_text": {
        "de": "Gilt für diese Website. Die mobile App ist auf Englisch.",
        "en": "Applies to this website. The mobile app is English only.",
    },
    "settings.appearance": {"de": "Darstellung", "en": "Appearance"},
    "settings.appearance_text": {
        "de": "Gilt für diese Website. Die mobile App ist immer hell.",
        "en": "Applies to this website. The mobile app is always light.",
    },
    "settings.theme_light": {"de": "Hell", "en": "Light"},
    "settings.theme_dark": {"de": "Dunkel", "en": "Dark"},
    "settings.position": {"de": "Deine Position", "en": "Your position"},
    "settings.is_trainer": {
        "de": "Du bist <strong>Trainer</strong>: Du kannst Gruppen anlegen, "
              "Trainees einladen und Quizze freigeben.",
        "en": "You are a <strong>trainer</strong>: you can create groups, "
              "invite trainees and release quizzes.",
    },
    "settings.trainer_note": {
        "de": "Zurück zu Trainee blendet diese Werkzeuge aus. Deine Gruppen "
              "und Quizze bleiben erhalten, du kannst jederzeit zurück "
              "wechseln.",
        "en": "Switching back to trainee hides those tools. Your groups and "
              "quizzes are kept, so you can switch back at any time.",
    },
    "settings.become_trainee": {"de": "Trainee werden", "en": "Become a trainee"},
    "settings.is_trainee": {
        "de": "Du bist <strong>Trainee</strong>: Du spielst Quizze, die "
              "Trainer deinen Gruppen freigeben.",
        "en": "You are a <strong>trainee</strong>: you play quizzes that "
              "trainers release to your groups.",
    },
    "settings.trainee_note": {
        "de": "Als Trainer bekommst du zusätzlich Gruppen, Einladungen und "
              "eigene Quizze. In der frühen Phase kostenlos.",
        "en": "As a trainer you additionally get groups, invitations and your "
              "own quizzes. This is free while QuizMonkey is in early access.",
    },
    "settings.become_trainer": {"de": "Trainer werden", "en": "Become a trainer"},
    "settings.your_data": {"de": "Deine Daten", "en": "Your data"},
    "settings.rights": {
        "de": "Du hast das Recht auf Auskunft, Berichtigung, Löschung und "
              "Datenübertragbarkeit (Art. 15–20 DSGVO). Passwortänderung und "
              "Kontolöschung kommen auf diese Seite; bis dahin schreib an die "
              "Adresse im %s.",
        "en": "You have the right to access, rectification, erasure and data "
              "portability (Art. 15–20 GDPR). Password changes and account "
              "deletion are coming to this page; until then, write to the "
              "address in the %s.",
    },
    "settings.rights_short": {
        "de": "Du hast das Recht auf Auskunft, Berichtigung, Löschung und "
              "Datenübertragbarkeit (Art. 15–20 DSGVO).",
        "en": "You have the right to access, rectification, erasure and data "
              "portability (Art. 15–20 GDPR).",
    },
    "settings.save_profile": {"de": "Profil speichern", "en": "Save profile"},
    "settings.email_note": {
        "de": "E-Mail-Adresse kann hier nicht geändert werden.",
        "en": "E-mail address cannot be changed here.",
    },
    "settings.dashboard": {"de": "Dashboard anpassen", "en": "Customise dashboard"},
    "settings.dashboard_text": {
        "de": "Wähle, welche Bereiche auf deiner Übersicht angezeigt werden. "
              "Die Begrüßung mit deinem Namen bleibt immer sichtbar.",
        "en": "Choose which sections appear on your dashboard. "
              "The greeting with your name always stays visible.",
    },
    "settings.save_dashboard": {"de": "Speichern", "en": "Save"},
    "settings.dash_stats": {"de": "Statistiken (Zähler)", "en": "Statistics (counters)"},
    "settings.dash_tests": {"de": "Tests", "en": "Tests"},
    "settings.dash_quizzes": {"de": "Quizze", "en": "Quizzes"},
    "settings.dash_groups": {"de": "Gruppen", "en": "Groups"},
    "settings.dash_notifications": {
        "de": "Benachrichtigungen (offene Tests)",
        "en": "Notifications (open tests)",
    },
    "settings.delete_account": {"de": "Konto löschen", "en": "Delete account"},
    "settings.delete_account_text": {
        "de": "Das Löschen deines Kontos ist endgültig. Alle deine Daten, "
              "Gruppen, Quizze und Tests werden unwiderruflich entfernt.",
        "en": "Deleting your account is permanent. All your data, groups, "
              "quizzes and tests will be irreversibly removed.",
    },
    "settings.delete_account_show": {
        "de": "Konto löschen …", "en": "Delete account …",
    },
    "settings.delete_confirm_hint": {
        "de": "Gib zur Bestätigung deine E-Mail-Adresse ein: %s",
        "en": "Type your e-mail address to confirm: %s",
    },
    "settings.delete_type_email": {
        "de": "E-Mail-Adresse zur Bestätigung", "en": "E-mail address to confirm",
    },
    "settings.delete_final_confirm": {
        "de": "Konto wirklich endgültig löschen?",
        "en": "Really delete your account permanently?",
    },
    "settings.delete_account_btn": {
        "de": "Konto endgültig löschen", "en": "Permanently delete account",
    },
    "msg.profile_saved": {"de": "Profil gespeichert.", "en": "Profile saved."},
    "msg.dashboard_saved": {
        "de": "Dashboard-Einstellungen gespeichert.",
        "en": "Dashboard settings saved.",
    },
    "msg.account_deleted": {
        "de": "Konto wurde gelöscht.", "en": "Account has been deleted.",
    },
    "err.delete_email_mismatch": {
        "de": "Die eingegebene E-Mail-Adresse stimmt nicht überein.",
        "en": "The e-mail address entered does not match.",
    },

    # -- groups ------------------------------------------------------------
    "groups.title": {"de": "Gruppen", "en": "Groups"},
    "groups.lead": {
        "de": "Eine Gruppe bündelt Trainees, denen du Quizze freigibst.",
        "en": "A group bundles the trainees you release quizzes to.",
    },
    "groups.new": {"de": "Neue Gruppe", "en": "New group"},
    "groups.name": {"de": "Gruppenname", "en": "Group name"},
    "groups.create": {"de": "Anlegen", "en": "Create"},
    "groups.members": {"de": "Mitglieder", "en": "Members"},
    "groups.none": {
        "de": "Noch keine Gruppen. Lege oben deine erste an.",
        "en": "No groups yet. Create your first one above.",
    },
    "groups.drag_hint": {
        "de": "Ziehe die Gruppen, um sie neu zu sortieren.",
        "en": "Drag groups to reorder them.",
    },
    "groups.drag": {"de": "Verschieben", "en": "Drag to reorder"},
    "groups.members_short": {"de": "Mitgl.", "en": "members"},
    "groups.new_lead": {
        "de": "Erstelle eine neue Gruppe und lade Trainees per E-Mail ein.",
        "en": "Create a new group and invite trainees by e-mail.",
    },
    "groups.name_placeholder": {
        "de": "z. B. Kurs 2026 Gruppe A", "en": "e.g. Course 2026 Group A",
    },
    "groups.open": {"de": "Öffnen", "en": "Open"},
    "groups.delete": {"de": "Löschen", "en": "Delete"},
    "groups.delete_confirm": {
        "de": "Diese Gruppe löschen? Mitgliedschaften und Freigaben gehen "
              "verloren.",
        "en": "Delete this group? Memberships and releases will be lost.",
    },
    "group.invite_title": {"de": "Trainee einladen", "en": "Invite a trainee"},
    "group.invite_text": {
        "de": "Die Person bekommt eine E-Mail. Hat sie noch kein Konto, wird "
              "sie gebeten, sich mit genau dieser Adresse zu registrieren — "
              "die Einladung erscheint dann automatisch in ihrer App.",
        "en": "They receive an e-mail. If they have no account yet, they are "
              "asked to register with exactly this address — the invitation "
              "then appears in their app automatically.",
    },
    "group.invite_submit": {"de": "Einladen", "en": "Invite"},
    "group.status": {"de": "Status", "en": "Status"},
    "group.status_invited": {"de": "eingeladen", "en": "invited"},
    "group.status_accepted": {"de": "angenommen", "en": "accepted"},
    "group.remove": {"de": "Entfernen", "en": "Remove"},
    "group.no_members": {
        "de": "Noch niemand eingeladen.", "en": "Nobody invited yet.",
    },
    "group.back": {"de": "Zurück zu den Gruppen", "en": "Back to groups"},

    # -- quizzes -----------------------------------------------------------
    "quizzes.title": {"de": "Quizze", "en": "Quizzes"},
    "quizzes.lead": {
        "de": "Erstelle ein Quiz hier oder importiere eines als CSV.",
        "en": "Build a quiz here, or import one you already have as CSV.",
    },
    "quizzes.new": {"de": "Neues Quiz", "en": "New quiz"},
    "quizzes.import_title": {"de": "CSV importieren", "en": "Import CSV"},
    "quizzes.import_text": {
        "de": "Eine Frage pro Zeile: "
              "<code>Frage;Antwort1;Antwort2;Antwort3;Antwort4;RichtigeAntwort</code> "
              "— Strichpunkte, keine Kopfzeile. Antwort 3 und 4 dürfen leer "
              "bleiben. Die richtige Antwort muss exakt einer der Antworten "
              "entsprechen.",
        "en": "One question per line: "
              "<code>question;answer1;answer2;answer3;answer4;correctAnswer</code> "
              "— semicolons, no header row. Leave answers 3 and 4 empty for "
              "shorter questions. The correct answer must match one of the "
              "answers exactly.",
    },
    "quizzes.file": {"de": "CSV-Datei", "en": "CSV file"},
    "quizzes.name_optional": {"de": "Name (optional)", "en": "Name (optional)"},
    "quizzes.name_placeholder": {
        "de": "Standard: Dateiname", "en": "Defaults to the file name",
    },
    "quizzes.import": {"de": "Importieren", "en": "Import"},
    "quizzes.yours": {"de": "Deine Quizze", "en": "Your quizzes"},
    "quizzes.name": {"de": "Name", "en": "Name"},
    "quizzes.questions": {"de": "Fragen", "en": "Questions"},
    "quizzes.edit": {"de": "Bearbeiten", "en": "Edit"},
    "quizzes.export": {"de": "Exportieren", "en": "Export"},
    "quizzes.delete": {"de": "Löschen", "en": "Delete"},
    "quizzes.delete_confirm": {
        "de": "Dieses Quiz löschen? Trainees verlieren den Zugriff darauf.",
        "en": "Delete this quiz? Trainees will lose access to it.",
    },
    "quizzes.none": {
        "de": "Noch keine Quizze. Lege oben eines an oder importiere eine CSV.",
        "en": "No quizzes yet. Create one above, or import a CSV.",
    },
    "quiz.edit_title": {"de": "Quiz bearbeiten", "en": "Edit quiz"},
    "quiz.new_title": {"de": "Neues Quiz", "en": "New quiz"},
    "quiz.lead": {
        "de": "Jede Frage braucht zwei bis vier Antworten, eine davon als "
              "richtig markiert.",
        "en": "Each question needs two to four answers, one of them marked "
              "correct.",
    },
    "quiz.name": {"de": "Name des Quiz", "en": "Quiz name"},
    "quiz.notes": {"de": "Notizen (optional)", "en": "Notes (optional)"},
    "quiz.notes_placeholder": {
        "de": "z. B. Quelle der Fragen oder Schwerpunkte",
        "en": "e.g. where the questions come from, or what to focus on",
    },
    "quiz.notes_hint": {
        "de": "Nur für dich sichtbar. Trainees sehen die Notizen nicht.",
        "en": "Visible to you only. Trainees do not see these notes.",
    },
    "quiz.note_empty": {
        "de": "Noch keine Notiz. Über „Bearbeiten“ kannst du eine hinzufügen.",
        "en": "No note yet. Add one under “Edit”.",
    },
    "quiz.released_to": {"de": "Freigegeben für", "en": "Released to"},
    "quiz.released_none": {
        "de": "Für keine Gruppe freigegeben.",
        "en": "Not released to any group.",
    },
    "quiz.created": {"de": "Erstellt", "en": "Created"},
    "quiz.updated": {"de": "Zuletzt geändert", "en": "Last changed"},
    "quiz.search": {"de": "Fragen durchsuchen", "en": "Search questions"},
    "quiz.search_placeholder": {
        "de": "Fragen filtern …", "en": "Filter questions …",
    },
    "quiz.search_none": {
        "de": "Keine Frage passt zur Suche.",
        "en": "No question matches your search.",
    },
    "quiz.question": {"de": "Frage", "en": "Question"},
    "quiz.question_text": {"de": "Fragetext", "en": "Question text"},
    "quiz.answers_hint": {
        "de": "Trage zwei bis vier Antworten ein und hake die richtige(n) an. "
              "Mehrere dürfen richtig sein.",
        "en": "Fill in two to four answers and tick the correct one(s). More "
              "than one may be correct.",
    },
    "quiz.answer": {"de": "Antwort", "en": "Answer"},
    "quiz.optional": {"de": "optional", "en": "optional"},
    "quiz.answer_correct": {
        "de": "Antwort %s ist richtig", "en": "Answer %s is correct",
    },
    "quiz.remove_question": {"de": "Frage entfernen", "en": "Remove question"},
    "quiz.remove_confirm": {
        "de": "Diese Frage entfernen? Der eingegebene Inhalt geht verloren.",
        "en": "Remove this question? The text you entered will be lost.",
    },
    "quiz.withdraw_confirm": {
        "de": "Freigabe für diese Gruppe zurückziehen? Die Trainees verlieren "
              "den Zugriff auf das Quiz.",
        "en": "Withdraw this quiz from the group? The trainees will lose "
              "access to it.",
    },
    "quiz.add_question": {"de": "+ Frage hinzufügen", "en": "+ Add question"},
    "quiz.save": {"de": "Quiz speichern", "en": "Save quiz"},
    "quiz.release_title": {"de": "An Gruppen freigeben", "en": "Release to groups"},
    "quiz.release_hint": {
        "de": "Bestimme auf einer eigenen Seite, welche Gruppen dieses Quiz "
              "üben dürfen.",
        "en": "Choose which groups may practise this quiz on a dedicated page.",
    },
    "quiz.release_manage": {
        "de": "Freigaben verwalten", "en": "Manage releases",
    },
    "quiz.release_text": {
        "de": "Trainees sehen ein Quiz in der App, sobald es einer ihrer "
              "Gruppen freigegeben ist.",
        "en": "Trainees see a quiz in the mobile app as soon as it is "
              "released to a group they belong to.",
    },
    "quiz.release": {"de": "Freigeben", "en": "Release"},
    "quiz.withdraw": {"de": "Zurückziehen", "en": "Withdraw"},
    "quiz.released": {"de": "freigegeben", "en": "released"},
    "quiz.no_groups": {
        "de": "Du hast noch keine Gruppen. %s, um dieses Quiz freizugeben.",
        "en": "You have no groups yet. %s to release this quiz.",
    },
    "quiz.create_group_link": {"de": "Lege eine an", "en": "Create one"},
    "quiz.export_title": {"de": "Export", "en": "Export"},
    "quiz.export_text": {
        "de": "Lädt das Quiz im CSV-Format der App herunter "
              "(<code>Frage;Antwort1;…;RichtigeAntwort</code>).",
        "en": "Downloads the quiz in the CSV format the app uses "
              "(<code>question;answer1;…;correctAnswer</code>).",
    },
    "quiz.download": {"de": "CSV herunterladen", "en": "Download CSV"},
    "quiz.back": {"de": "Zurück zu den Quizzen", "en": "Back to quizzes"},

    # -- tests -------------------------------------------------------------
    "tests.title": {"de": "Tests", "en": "Tests"},
    "tests.lead": {
        "de": "Ein Test ist eine Prüfung aus deinen Quizzen — mit "
              "Bestehensgrenze, begrenzten Versuchen und ohne Feedback während "
              "des Tests.",
        "en": "A test is an exam built from your quizzes — with a pass mark, "
              "limited attempts and no feedback during the test.",
    },
    "tests.new": {"de": "Neuer Test", "en": "New test"},
    "tests.yours": {"de": "Deine Tests", "en": "Your tests"},
    "tests.none": {
        "de": "Noch keine Tests. Lege oben deinen ersten an.",
        "en": "No tests yet. Create your first one above.",
    },
    "tests.delete_confirm": {
        "de": "Diesen Test löschen? Ergebnisse der Trainees gehen verloren.",
        "en": "Delete this test? Trainees' results will be lost.",
    },
    "test.new_title": {"de": "Neuer Test", "en": "New test"},
    "test.lead": {
        "de": "Stelle die Fragen zufällig aus mehreren Quizzen zusammen und "
              "lege die Regeln fest.",
        "en": "Compose the questions at random from several quizzes and set "
              "the rules.",
    },
    "test.no_quizzes": {
        "de": "Du brauchst zuerst mindestens ein Quiz. %s anlegen.",
        "en": "You need at least one quiz first. Create one under %s.",
    },
    "test.name": {"de": "Name des Tests", "en": "Test name"},
    "test.pass_percent": {"de": "Bestehen ab (%)", "en": "Pass mark (%)"},
    "test.attempts": {"de": "Erlaubte Versuche", "en": "Allowed attempts"},
    "test.questions": {"de": "Fragen", "en": "Questions"},
    "test.time_limit": {"de": "Zeitlimit", "en": "Time limit"},
    "test.time_limit_min": {
        "de": "Zeitlimit (Minuten)", "en": "Time limit (minutes)",
    },
    "test.time_limit_hint": {
        "de": "Leer lassen für kein Limit. Ist ein Limit gesetzt, sieht der "
              "Trainee während des Tests die verbleibende Zeit.",
        "en": "Leave empty for no limit. With a limit, the trainee sees the "
              "remaining time during the test.",
    },
    "test.no_limit": {"de": "kein Limit", "en": "no limit"},
    "test.minutes": {"de": "Min.", "en": "min"},
    "test.mode": {"de": "Fragen auswählen", "en": "Choose questions"},
    "test.mode_random": {
        "de": "Zufällig aus Quizzen ziehen",
        "en": "Draw at random from quizzes",
    },
    "test.mode_manual": {
        "de": "Fragen selbst auswählen",
        "en": "Pick questions myself",
    },
    "test.manual_title": {"de": "Fragen auswählen", "en": "Pick questions"},
    "test.manual_hint": {
        "de": "Hake die Fragen an, die im Test vorkommen sollen — auch quer "
              "über mehrere Quizze.",
        "en": "Tick the questions the test should contain — across as many "
              "quizzes as you like.",
    },
    "test.manual_empty": {
        "de": "Dieses Quiz hat keine Fragen.",
        "en": "This quiz has no questions.",
    },
    "test.sources_title": {"de": "Fragen-Quellen", "en": "Question sources"},
    "test.sources_hint": {
        "de": "Gib an, wie viele Fragen der Test hat, und verteile sie "
              "prozentual auf deine Quizze (Summe 100 %).",
        "en": "Set how many questions the test has and split them across your "
              "quizzes by percentage (must total 100%).",
    },
    "test.question_count": {"de": "Anzahl Fragen", "en": "Number of questions"},
    "test.weight": {"de": "Anteil %", "en": "Share %"},
    "test.weight_hint": {
        "de": "0 % = dieses Quiz nicht verwenden. Die Prozente werden fair auf "
              "ganze Fragen gerundet.",
        "en": "0% = don't use that quiz. Percentages are rounded fairly to "
              "whole questions.",
    },
    "test.random_title": {"de": "Zufalls-Regeln", "en": "Random rules"},
    "test.draw_scope": {
        "de": "Wer bekommt welche Fragen?", "en": "Who gets which questions?",
    },
    "test.scope_per_trainee": {
        "de": "Jeder Trainee bekommt eine eigene Zufallsauswahl.",
        "en": "Each trainee gets their own random selection.",
    },
    "test.scope_fixed": {
        "de": "Ein festes Set — alle Trainees bekommen dieselben Fragen.",
        "en": "One fixed set — every trainee gets the same questions.",
    },
    "test.retry_mode": {
        "de": "Bei einem weiteren Versuch", "en": "On another attempt",
    },
    "test.retry_new": {
        "de": "Neue Zufallsfragen ziehen.", "en": "Draw new random questions.",
    },
    "test.retry_same": {
        "de": "Wieder dieselben Fragen.", "en": "The same questions again.",
    },
    "test.retry_hint": {
        "de": "Gilt nur bei eigener Auswahl pro Trainee. Bei einem festen Set "
              "sind es immer dieselben Fragen.",
        "en": "Only applies to a per-trainee selection. A fixed set is always "
              "the same questions.",
    },
    "test.expires_at": {"de": "Ablaufdatum", "en": "Expiry date"},
    "test.expires_hint": {
        "de": "Optional. Nach diesem Datum können keine neuen Versuche mehr "
              "gestartet werden. Leer lassen für kein Ablaufdatum.",
        "en": "Optional. After this date no new attempts can be started. "
              "Leave empty for no expiry.",
    },
    "test.edit_title": {"de": "Test bearbeiten", "en": "Edit test"},
    "test.create": {"de": "Test erstellen", "en": "Create test"},
    "test.save": {"de": "Test speichern", "en": "Save test"},
    "test.cancel": {"de": "Abbrechen", "en": "Cancel"},
    "test.back": {"de": "Zurück zu den Tests", "en": "Back to tests"},
    "test.release_text": {
        "de": "Trainees sehen einen Test, sobald er einer ihrer Gruppen "
              "freigegeben ist.",
        "en": "Trainees see a test as soon as it is released to a group they "
              "belong to.",
    },
    "test.withdraw_confirm": {
        "de": "Freigabe für diese Gruppe zurückziehen?",
        "en": "Withdraw this test from the group?",
    },
    "msg.test_created": {"de": "Test erstellt.", "en": "Test created."},
    "msg.test_saved": {"de": "Test gespeichert.", "en": "Test saved."},
    "msg.test_deleted": {"de": "Test gelöscht.", "en": "Test deleted."},
    "msg.test_released": {
        "de": "Test der Gruppe freigegeben.", "en": "Test released to the group.",
    },
    "msg.test_withdrawn": {
        "de": "Test von der Gruppe zurückgezogen.",
        "en": "Test withdrawn from the group.",
    },
    "err.test_not_found": {"de": "Test nicht gefunden.", "en": "Test not found."},

    # -- taking a test -----------------------------------------------------
    "take.title": {"de": "Meine Tests", "en": "My tests"},
    "take.lead": {
        "de": "Prüfungen, die dir freigegeben wurden. Während eines Tests gibt "
              "es kein Feedback — nur am Ende das Ergebnis.",
        "en": "Exams released to you. There is no feedback during a test — only "
              "the result at the end.",
    },
    "take.none": {
        "de": "Dir wurde noch kein Test freigegeben.",
        "en": "No test has been released to you yet.",
    },
    "take.open": {"de": "Öffnen", "en": "Open"},
    "take.back": {"de": "Zurück zu den Tests", "en": "Back to tests"},
    "take.passed": {"de": "Bestanden", "en": "Passed"},
    "take.failed": {"de": "Nicht bestanden", "en": "Not passed"},
    "take.locked": {"de": "Gesperrt", "en": "Locked"},
    "take.in_progress": {"de": "Läuft", "en": "In progress"},
    "take.attempts_used": {
        "de": "%s von %s Versuchen", "en": "%s of %s attempts",
    },
    "take.attempts_left_label": {"de": "Versuche übrig", "en": "Attempts left"},
    "take.required": {
        "de": "Zum Bestehen brauchst du mindestens %s %%.",
        "en": "You need at least %s%% to pass.",
    },
    "take.rules_hint": {
        "de": "Der Test lässt sich nicht pausieren, und du bekommst erst am "
              "Ende dein Ergebnis.",
        "en": "The test cannot be paused, and you only get your result at the "
              "end.",
    },
    "take.start": {"de": "Test starten", "en": "Start test"},
    "take.start_confirm": {
        "de": "Test jetzt starten? Er lässt sich nicht pausieren und zählt als "
              "Versuch.",
        "en": "Start the test now? It cannot be paused and counts as an attempt.",
    },
    "take.resume": {"de": "Test fortsetzen", "en": "Resume test"},
    "take.you_passed": {
        "de": "Bestanden — beim %s. Versuch.", "en": "Passed — on attempt %s.",
    },
    "take.you_locked": {
        "de": "Alle Versuche aufgebraucht, nicht bestanden.",
        "en": "All attempts used, not passed.",
    },
    "take.best": {"de": "Bestes Ergebnis: %s %%", "en": "Best score: %s%%"},
    "take.time_left": {"de": "Verbleibende Zeit", "en": "Time left"},
    "take.multi_hint": {
        "de": "Mehrere Antworten können richtig sein.",
        "en": "More than one answer can be correct.",
    },
    "take.no_feedback_hint": {
        "de": "Wähle je Frage eine Antwort. Das Ergebnis siehst du nach dem "
              "Absenden.",
        "en": "Pick one answer per question. You'll see the result after you "
              "submit.",
    },
    "take.submit": {"de": "Test abgeben", "en": "Submit test"},
    "take.submit_confirm": {
        "de": "Test abgeben? Danach kannst du nichts mehr ändern.",
        "en": "Submit the test? You cannot change anything afterwards.",
    },
    "take.result": {"de": "Ergebnis", "en": "Result"},
    "take.attempt_no": {"de": "Versuch %s", "en": "Attempt %s"},
    "take.another": {"de": "Noch ein Versuch", "en": "Another attempt"},

    # -- results (trainer) -------------------------------------------------
    "results.title": {"de": "Ergebnisse", "en": "Results"},
    "results.trainee": {"de": "Trainee", "en": "Trainee"},
    "results.attempts": {"de": "Versuche / Bestanden bei", "en": "Attempts / passed on"},
    "results.best": {"de": "Bestes", "en": "Best"},
    "results.passed": {"de": "bestanden", "en": "passed"},
    "results.locked": {"de": "gesperrt", "en": "locked"},
    "results.ongoing": {"de": "offen", "en": "ongoing"},
    "results.at_attempt": {"de": "beim %s. Versuch", "en": "on attempt %s"},
    "results.reset": {"de": "Zurücksetzen", "en": "Reset"},
    "results.reset_confirm": {
        "de": "Versuche dieses Trainees zurücksetzen? Er kann den Test dann "
              "neu machen.",
        "en": "Reset this trainee's attempts? They can then take the test again.",
    },
    "results.none": {
        "de": "Noch hat niemand diesen Test gemacht.",
        "en": "Nobody has taken this test yet.",
    },

    "err.tests_not_configured": {
        "de": "Tests sind auf dem Server noch nicht eingerichtet "
              "(SUPABASE_SERVICE_ROLE_KEY fehlt).",
        "en": "Tests are not set up on the server yet "
              "(SUPABASE_SERVICE_ROLE_KEY is missing).",
    },
    "err.test_passed": {
        "de": "Du hast diesen Test bereits bestanden.",
        "en": "You have already passed this test.",
    },
    "err.test_locked": {
        "de": "Keine Versuche mehr übrig.", "en": "No attempts left.",
    },
    "err.test_empty": {
        "de": "Dieser Test enthält keine Fragen.",
        "en": "This test contains no questions.",
    },
    "err.attempt_not_found": {
        "de": "Versuch nicht gefunden.", "en": "Attempt not found.",
    },
    "err.attempt_done": {
        "de": "Dieser Versuch ist bereits abgeschlossen.",
        "en": "This attempt is already finished.",
    },

    # -- courses -----------------------------------------------------------
    "courses.lead": {
        "de": "Kurse bündeln Gruppen und Materialien. Erstelle einen Kurs, "
              "weise Gruppen zu und lade Dateien hoch.",
        "en": "Courses bundle groups and materials. Create a course, assign "
              "groups and upload files.",
    },
    "courses.new": {"de": "Neuer Kurs", "en": "New course"},
    "courses.new_lead": {
        "de": "Lege einen neuen Kurs an. Du kannst danach Gruppen hinzufügen "
              "und Dateien hochladen.",
        "en": "Create a new course. You can then add groups and upload files.",
    },
    "courses.name": {"de": "Kursname", "en": "Course name"},
    "courses.name_placeholder": {
        "de": "z. B. Mathematik Grundkurs 2026",
        "en": "e.g. Mathematics Foundation 2026",
    },
    "courses.description": {"de": "Beschreibung (optional)", "en": "Description (optional)"},
    "courses.description_placeholder": {
        "de": "Kurze Beschreibung des Kursinhalts",
        "en": "Brief description of the course content",
    },
    "courses.create": {"de": "Kurs erstellen", "en": "Create course"},
    "courses.save": {"de": "Kurs speichern", "en": "Save course"},
    "courses.edit": {"de": "Kurs bearbeiten", "en": "Edit course"},
    "courses.manage": {"de": "Verwalten", "en": "Manage"},
    "courses.back": {"de": "Zurück zu den Kursen", "en": "Back to courses"},
    "courses.delete": {"de": "Löschen", "en": "Delete"},
    "courses.delete_confirm": {
        "de": "Diesen Kurs löschen? Alle Dateien und Gruppen-Zuweisungen gehen verloren.",
        "en": "Delete this course? All files and group assignments will be lost.",
    },
    "courses.none": {
        "de": "Noch keine Kurse. Erstelle deinen ersten Kurs.",
        "en": "No courses yet. Create your first course.",
    },
    "courses.groups_count": {"de": "Gruppen", "en": "groups"},
    "courses.files_count": {"de": "Dateien", "en": "files"},
    "courses.assigned_groups": {"de": "Zugewiesene Gruppen", "en": "Assigned groups"},
    "courses.assign_groups": {"de": "Gruppen zuweisen", "en": "Assign groups"},
    "courses.assign_groups_text": {
        "de": "Wähle, welche Gruppen diesen Kurs sehen sollen.",
        "en": "Choose which groups should see this course.",
    },
    "courses.include": {"de": "Einschließen", "en": "Include"},
    "courses.save_groups": {"de": "Gruppen speichern", "en": "Save groups"},
    "courses.no_groups_hint": {
        "de": "Du hast noch keine Gruppen. Lege erst eine Gruppe an.",
        "en": "You have no groups yet. Create a group first.",
    },
    "courses.no_groups_yet": {
        "de": "Noch keine Gruppe zugewiesen.",
        "en": "No group assigned yet.",
    },
    "courses.files": {"de": "Dateien", "en": "Files"},
    "courses.files_hint": {
        "de": "Lade Dateien hoch, die die Trainees dieses Kurses sehen können "
              "(PDF, Bilder, Excel, Word, Text, CSV — max. 20 MB).",
        "en": "Upload files that trainees of this course can see "
              "(PDF, images, Excel, Word, text, CSV — max. 20 MB).",
    },
    "courses.upload_file": {"de": "Datei auswählen", "en": "Choose file"},
    "courses.file_label": {"de": "Anzeigename", "en": "Display name"},
    "courses.file_label_placeholder": {
        "de": "z. B. Skript Kapitel 1", "en": "e.g. Script Chapter 1",
    },
    "courses.optional": {"de": "optional", "en": "optional"},
    "courses.upload": {"de": "Hochladen", "en": "Upload"},
    "courses.download": {"de": "Herunterladen", "en": "Download"},
    "courses.no_files": {"de": "Noch keine Dateien hochgeladen.", "en": "No files uploaded yet."},
    "courses.file_delete_confirm": {
        "de": "Diese Datei löschen?", "en": "Delete this file?",
    },
    "msg.course_created": {"de": "Kurs erstellt.", "en": "Course created."},
    "msg.course_saved": {"de": "Kurs gespeichert.", "en": "Course saved."},
    "msg.course_deleted": {"de": "Kurs gelöscht.", "en": "Course deleted."},
    "msg.course_groups_saved": {
        "de": "Gruppen-Zuweisung gespeichert.", "en": "Group assignment saved.",
    },
    "msg.course_file_uploaded": {"de": "Datei hochgeladen.", "en": "File uploaded."},
    "msg.course_file_deleted": {"de": "Datei gelöscht.", "en": "File deleted."},
    "err.course_not_found": {"de": "Kurs nicht gefunden.", "en": "Course not found."},
    "err.file_too_large": {
        "de": "Die Datei ist zu groß (max. 20 MB).",
        "en": "The file is too large (max. 20 MB).",
    },
    "err.file_type_not_allowed": {
        "de": "Dieser Dateityp ist nicht erlaubt.",
        "en": "This file type is not allowed.",
    },

    # -- flash messages (referenced by key in redirects) -------------------
    "msg.attempts_reset": {
        "de": "Versuche zurückgesetzt.", "en": "Attempts reset.",
    },
    "msg.group_created": {"de": "Gruppe angelegt.", "en": "Group created."},
    "msg.group_deleted": {"de": "Gruppe gelöscht.", "en": "Group deleted."},
    "msg.member_removed": {"de": "Mitglied entfernt.", "en": "Member removed."},
    "msg.quiz_saved": {"de": "Quiz gespeichert.", "en": "Quiz saved."},
    "msg.quiz_deleted": {"de": "Quiz gelöscht.", "en": "Quiz deleted."},
    "msg.quiz_released": {
        "de": "Quiz der Gruppe freigegeben.", "en": "Quiz released to the group.",
    },
    "msg.quiz_withdrawn": {
        "de": "Quiz von der Gruppe zurückgezogen.",
        "en": "Quiz withdrawn from the group.",
    },
    "msg.role_trainer": {"de": "Du bist jetzt Trainer.", "en": "You are now a trainer."},
    "msg.role_trainee": {"de": "Du bist jetzt Trainee.", "en": "You are now a trainee."},
    "msg.registered": {
        "de": "Konto erstellt. Bestätige die E-Mail und melde dich dann an.",
        "en": "Account created. Please confirm your e-mail, then sign in.",
    },
    "msg.invited": {"de": "Einladung an %s gesendet.", "en": "Invitation sent to %s."},
    "msg.invited_no_mail": {
        "de": "%s wurde eingeladen, aber es wurde keine E-Mail gesendet "
              "(SMTP ist nicht konfiguriert).",
        "en": "%s was invited, but no e-mail was sent (SMTP is not configured).",
    },
    "err.invalid_email": {
        "de": "Bitte eine gültige E-Mail-Adresse eingeben.",
        "en": "Please enter a valid e-mail address.",
    },
    "err.already_invited": {
        "de": "Diese E-Mail-Adresse ist bereits eingeladen.",
        "en": "That e-mail address is already invited.",
    },
    "err.need_trainer": {
        "de": "Wechsle zu Trainer, um Gruppen und Quizze zu verwalten.",
        "en": "Switch to trainer to manage groups and quizzes.",
    },
    "err.privacy_required": {
        "de": "Bitte akzeptiere die Datenschutzerklärung.",
        "en": "Please accept the privacy policy.",
    },
    "err.quiz_not_found": {"de": "Quiz nicht gefunden.", "en": "Quiz not found."},
    "err.group_name_required": {
        "de": "Bitte einen Gruppennamen eingeben.",
        "en": "Please enter a group name.",
    },
    "err.quiz_name_required": {
        "de": "Gib dem Quiz einen Namen.", "en": "Give the quiz a name.",
    },
    "err.quiz_no_questions": {
        "de": "Füge mindestens eine Frage hinzu.",
        "en": "Add at least one question.",
    },
    "err.encoding": {
        "de": "Die Zeichenkodierung der Datei konnte nicht gelesen werden.",
        "en": "Could not read the file encoding.",
    },
    "err.backend": {
        "de": "Das Backend ist nicht konfiguriert.",
        "en": "Backend is not configured.",
    },
    "err.signin_failed": {
        "de": "Anmeldung fehlgeschlagen.", "en": "Sign-in failed.",
    },
    "err.group_not_found": {
        "de": "Gruppe nicht gefunden.", "en": "Group not found.",
    },
    "msg.imported": {
        "de": "Quiz importiert.", "en": "Quiz imported.",
    },
    "err.unknown_role": {"de": "Unbekannte Rolle.", "en": "Unknown role."},
    "err.first_name_required": {
        "de": "Bitte einen Vornamen eingeben.", "en": "Please enter a first name.",
    },
    "err.course_name_required": {
        "de": "Bitte einen Kursnamen eingeben.", "en": "Please enter a course name.",
    },
    "err.file_not_found": {"de": "Datei nicht gefunden.", "en": "File not found."},
}


def pick_language(cookie_value: str | None, accept_language: str | None) -> str:
    """Cookie wins; otherwise the browser's preference; otherwise German."""
    if cookie_value in LANGUAGES:
        return cookie_value
    for part in (accept_language or "").split(","):
        code = part.split(";")[0].strip().lower()[:2]
        if code in LANGUAGES:
            return code
    return DEFAULT_LANG


def translate(key: str, lang: str, *args) -> str:
    """Look up `key`; fall back to the other language, then to the key itself
    so a missing string is visible rather than silently blank."""
    entry = TEXTS.get(key)
    if entry is None:
        return key
    text = entry.get(lang) or entry.get(DEFAULT_LANG) or key
    if args:
        try:
            return text % args
        except TypeError:
            return text
    return text
