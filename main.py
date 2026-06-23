#!/usr/bin/env python3
"""
Geburtsdatum-Pflichtfeld-Scanner
=================================
Hauptprogramm — hier starten.

Verwendung:
  python main.py              # Dauerhafter Betrieb (alle 6h Scan)
  python main.py --once       # Einmaliger Scan
  python main.py --report     # Nur Report aus bestehenden Daten
  python main.py --test URL   # Einzelne URL testen
  python main.py --stats      # Statistiken anzeigen
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import schedule
import time
import threading

# Eigene Module
from crawler.config import SCAN_INTERVAL_H, LOGS_DIR
from crawler.database import init_db, get_all_findings
from crawler.scanner import run_full_scan, scan_single_url
from crawler.notifier import generate_html_report, generate_json_export


# ─── Logging einrichten ───────────────────────────────────────────────────────
log_file = LOGS_DIR / f"scanner_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("main")


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║   GEBURTSDATUM-PFLICHTFELD-SCANNER                          ║
║   AGG § 11 · DSGVO Art. 5 · BDSG § 26                      ║
║   Dokumentation von Verstößen in Bewerbungsformularen       ║
╚══════════════════════════════════════════════════════════════╝
""")


async def cmd_test(url: str):
    """Einzelne URL direkt testen."""
    from playwright.async_api import async_playwright
    from crawler.detector import detect

    logger.info(f"Test-Scan: {url}")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)  # Sichtbar für Test
        ctx     = await browser.new_context(locale="de-DE")
        page    = await ctx.new_page()
        await page.goto(url, wait_until="networkidle", timeout=30_000)
        await asyncio.sleep(2)

        finding = await detect(page, url)
        if finding:
            print(f"\n✅ TREFFER GEFUNDEN!")
            print(f"   Feld  : {finding.field_label}")
            print(f"   Layer : {finding.detection_method}")
            print(f"   Screenshot: {finding.screenshot_path}")
        else:
            print(f"\n⚪ Kein Pflichtfeld-Geburtsdatum gefunden.")

        await browser.close()


def cmd_stats():
    """Aktuelle Statistiken aus der Datenbank."""
    findings = get_all_findings()
    domains  = set(f["domain"] for f in findings)

    print(f"\n{'='*50}")
    print(f"  SCANNER-STATISTIKEN")
    print(f"{'='*50}")
    print(f"  Bestätigte Funde   : {len(findings)}")
    print(f"  Betroffene Domains : {len(domains)}")

    if findings:
        print(f"\n  Letzte Funde:")
        for f in findings[:10]:
            ts = f.get("timestamp", "")[:19]
            print(f"  [{ts}] {f['company_name']:<30} {f['field_label'][:50]}")
    print()


def cmd_report():
    """Report aus bestehenden Daten generieren."""
    findings = get_all_findings()
    if not findings:
        print("Keine Funde in der Datenbank.")
        return

    html_path = generate_html_report(findings)
    json_path = generate_json_export(findings)
    print(f"HTML-Report: {html_path}")
    print(f"JSON-Export: {json_path}")


def run_scheduled():
    """Scan im Scheduler ausführen (für den Daemon-Modus)."""
    logger.info(f"Geplanter Scan startet...")
    asyncio.run(run_full_scan())
    # Nach jedem Scan Report aktualisieren
    findings = get_all_findings()
    if findings:
        generate_html_report(findings)


def cmd_daemon():
    """
    Dauerhafter Betrieb: Scan alle N Stunden, läuft bis Ctrl+C.
    """
    logger.info(f"Daemon-Modus: Scan alle {SCAN_INTERVAL_H} Stunden")
    logger.info(f"Logs: {log_file}")
    logger.info("Zum Beenden: Ctrl+C")

    # Ersten Scan sofort starten
    run_scheduled()

    # Dann geplant alle N Stunden
    schedule.every(SCAN_INTERVAL_H).hours.do(run_scheduled)

    try:
        while True:
            schedule.run_pending()
            next_run = schedule.next_run()
            logger.info(f"Nächster Scan: {next_run.strftime('%d.%m.%Y %H:%M')}")
            time.sleep(300)  # Alle 5 Minuten prüfen
    except KeyboardInterrupt:
        logger.info("Scanner beendet.")


def main():
    print_banner()

    parser = argparse.ArgumentParser(
        description="Geburtsdatum-Pflichtfeld-Scanner"
    )
    parser.add_argument(
        "--once",   action="store_true",
        help="Einmaliger Scan und beenden"
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Report aus bestehenden Daten generieren"
    )
    parser.add_argument(
        "--test",   metavar="URL",
        help="Einzelne URL testen (Browser sichtbar)"
    )
    parser.add_argument(
        "--stats",  action="store_true",
        help="Statistiken anzeigen"
    )
    args = parser.parse_args()

    # Datenbank initialisieren
    init_db()
    logger.info("Datenbank initialisiert.")

    if args.test:
        asyncio.run(cmd_test(args.test))

    elif args.stats:
        cmd_stats()

    elif args.report:
        cmd_report()

    elif args.once:
        logger.info("Einmaliger Scan...")
        result = asyncio.run(run_full_scan())
        print(f"\nErgebnis: {result['scanned']} gescannt, {result['found']} Funde")
        cmd_report()

    else:
        # Standard: Dauerhafter Daemon-Betrieb
        cmd_daemon()


if __name__ == "__main__":
    main()
