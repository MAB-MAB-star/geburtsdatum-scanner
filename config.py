"""
Geburtsdatum-Scanner — Konfiguration
Alle Einstellungen zentral anpassen.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

# ─── Pfade ────────────────────────────────────────────────────────────────────
SCREENSHOTS_DIR = BASE_DIR / "output" / "screenshots"
REPORTS_DIR     = BASE_DIR / "output" / "reports"
LOGS_DIR        = BASE_DIR / "logs"
DATA_DIR        = BASE_DIR / "data"
DB_PATH         = DATA_DIR / "findings.sqlite"

for d in [SCREENSHOTS_DIR, REPORTS_DIR, LOGS_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Crawler-Verhalten ────────────────────────────────────────────────────────
HEADLESS          = True        # False = Browser sichtbar (Debugging)
REQUEST_DELAY_MIN = 2.0         # Mindest-Pause zwischen Requests (Sekunden)
REQUEST_DELAY_MAX = 5.0         # Max-Pause
PAGE_TIMEOUT_MS   = 30_000      # 30 Sekunden Timeout pro Seite
MAX_WORKERS       = 3           # Parallele Browser-Instanzen
SCAN_INTERVAL_H   = 6           # Scan-Zyklus alle N Stunden
CRAWL_DEPTH       = 2           # Wie tief von der Domain aus crawlen

# ─── User-Agent (offen als Research-Bot) ─────────────────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (compatible; AGG-Research-Bot/1.0; "
    "+https://github.com/yourname/geburtsdatum-scanner; "
    "Zweck: Dokumentation von AGG-Verstaessen in Bewerbungsformularen)"
)

# ─── Suchbegriffe für Jobbörsen ───────────────────────────────────────────────
JOB_SEARCH_TERMS = [
    "Filialleiter",
    "Marktleiter",
    "Store Manager Einzelhandel",
    "Filialleiterin",
    "Storemanager",
    "Niederlassungsleiter Einzelhandel",
]

# ─── URL-Pattern für Karriereseiten ──────────────────────────────────────────
CAREER_URL_PATTERNS = [
    "/karriere", "/jobs", "/bewerben", "/bewerbung",
    "/stellenangebote", "/stellenanzeige", "/apply",
    "/online-bewerbung", "/jetzt-bewerben", "/jobangebote",
    "/work-with-us", "/arbeiten-bei", "/offene-stellen",
]

# ─── Domains die AUSGESCHLOSSEN werden (Jobbörsen selbst) ────────────────────
EXCLUDED_DOMAINS = {
    "stepstone.de", "indeed.com", "indeed.de", "xing.com",
    "linkedin.com", "monster.de", "jobware.de", "kimeta.de",
    "jooble.org", "stellenanzeigen.de", "jobboerse.arbeitsagentur.de",
    "glassdoor.de", "heyjobs.co", "arbeitsagentur.de",
    "google.com", "google.de", "bing.com",
}

# ─── Geburtsdatum-Erkennungs-Muster ──────────────────────────────────────────
BIRTH_LABEL_PATTERNS = [
    r"geburtsdatum",
    r"geburtstag",
    r"geburtsjahr",
    r"geb\.\s*datum",
    r"geb\.-datum",
    r"date\s+of\s+birth",
    r"\bdob\b",
    r"tt\.mm\.jjjj",
    r"birthdate",
    r"birthday",
    r"born\s+on",
    r"nato\s+il",           # Italienisch (für Südtirol)
    r"data\s+di\s+nascita",
]

REQUIRED_INDICATORS = [
    r"\*",               # Stern-Markierung
    r"pflichtfeld",
    r"pflicht",
    r"required",
    r"obligatorisch",
    r"muss\s+ausgef",
]

# ─── Bewerbungsformular-Kontext-Erkennung ─────────────────────────────────────
FORM_CONTEXT_PATTERNS = [
    r"bewerbung", r"bewerben", r"apply", r"application",
    r"lebenslauf", r"anschreiben", r"cv\b", r"resume",
    r"jetzt bewerben", r"stelle bewerben", r"initiativbewerbung",
]

FILIALLEITER_PATTERNS = [
    r"filialleiter", r"filialleiterin", r"marktleiter",
    r"store.?manager", r"storemanager", r"niederlassungsleiter",
    r"filialleitung", r"marktleitung", r"shop.?manager",
]

# ─── E-Mail Benachrichtigung (optional) ──────────────────────────────────────
EMAIL_ENABLED    = False    # True = E-Mail bei Neufund
EMAIL_FROM       = "scanner@example.de"
EMAIL_TO         = "deine@email.de"
EMAIL_SMTP_HOST  = "smtp.example.de"
EMAIL_SMTP_PORT  = 587
EMAIL_SMTP_USER  = ""
EMAIL_SMTP_PASS  = ""
