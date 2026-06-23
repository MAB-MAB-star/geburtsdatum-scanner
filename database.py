"""
Datenbank-Modul — SQLite (kein Server nötig, läuft lokal)
Alle Funde werden dauerhaft gespeichert.
"""

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

from .config import DB_PATH


@dataclass
class Finding:
    """Ein bestätigter Verstoß."""
    url: str
    domain: str
    company_name: str
    job_title: str
    field_label: str
    detection_method: str      # A=Label-Stern, B=HTML-required, C=ARIA, D=Submit-Test, E=Placeholder
    screenshot_path: str
    dom_hash: str
    timestamp: str
    robots_checked: bool = True
    confirmed: bool = True
    notes: str = ""

    def to_dict(self):
        return asdict(self)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Tabellen erstellen falls nicht vorhanden."""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS findings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            url             TEXT NOT NULL,
            domain          TEXT NOT NULL,
            company_name    TEXT NOT NULL,
            job_title       TEXT,
            field_label     TEXT NOT NULL,
            detection_method TEXT NOT NULL,
            screenshot_path TEXT,
            dom_hash        TEXT NOT NULL,
            timestamp       TEXT NOT NULL,
            robots_checked  INTEGER DEFAULT 1,
            confirmed       INTEGER DEFAULT 1,
            notes           TEXT DEFAULT '',
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS scanned_urls (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT UNIQUE NOT NULL,
            domain      TEXT NOT NULL,
            status      TEXT DEFAULT 'ok',
            scanned_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS scan_runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at  TEXT NOT NULL,
            finished_at TEXT,
            urls_scanned INTEGER DEFAULT 0,
            findings_count INTEGER DEFAULT 0
        )
    """)

    c.execute("CREATE INDEX IF NOT EXISTS idx_domain ON findings(domain)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_scanned ON scanned_urls(url)")

    conn.commit()
    conn.close()


def save_finding(f: Finding) -> int:
    """Fund speichern. Gibt die ID zurück."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO findings
        (url, domain, company_name, job_title, field_label,
         detection_method, screenshot_path, dom_hash, timestamp,
         robots_checked, confirmed, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        f.url, f.domain, f.company_name, f.job_title, f.field_label,
        f.detection_method, f.screenshot_path, f.dom_hash, f.timestamp,
        int(f.robots_checked), int(f.confirmed), f.notes
    ))
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id


def url_already_scanned(url: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM scanned_urls WHERE url=?", (url,))
    result = c.fetchone() is not None
    conn.close()
    return result


def mark_url_scanned(url: str, domain: str, status: str = "ok"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO scanned_urls (url, domain, status)
        VALUES (?,?,?)
    """, (url, domain, status))
    conn.commit()
    conn.close()


def get_all_findings() -> list[dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM findings ORDER BY created_at DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def finding_exists_for_domain(domain: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM findings WHERE domain=? AND confirmed=1", (domain,))
    result = c.fetchone() is not None
    conn.close()
    return result


def start_scan_run() -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO scan_runs (started_at) VALUES (?)",
              (datetime.now(timezone.utc).isoformat(),))
    run_id = c.lastrowid
    conn.commit()
    conn.close()
    return run_id


def finish_scan_run(run_id: int, urls_scanned: int, findings_count: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE scan_runs
        SET finished_at=?, urls_scanned=?, findings_count=?
        WHERE id=?
    """, (datetime.now(timezone.utc).isoformat(), urls_scanned, findings_count, run_id))
    conn.commit()
    conn.close()
