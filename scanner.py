"""
Scanner — Hauptmodul.
Orchestriert: Seed Discovery → Playwright-Rendering → Detektor → Datenbank.
Läuft als dauerhafter Hintergrundprozess.
"""

import asyncio
import logging
import urllib.robotparser
from urllib.parse import urlparse
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext

from .config import (
    HEADLESS, PAGE_TIMEOUT_MS, MAX_WORKERS, USER_AGENT,
    REQUEST_DELAY_MIN, REQUEST_DELAY_MAX,
)
from .detector import detect
from .database import (
    init_db, save_finding, url_already_scanned, mark_url_scanned,
    finding_exists_for_domain, start_scan_run, finish_scan_run,
)
from .seed_discovery import generate_seed_urls
from .notifier import notify_new_finding

logger = logging.getLogger(__name__)

# Robots.txt Cache (pro Domain)
_robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}


def _check_robots(url: str) -> bool:
    """
    robots.txt prüfen. Gibt True zurück wenn crawlen erlaubt.
    Im Zweifel: erlauben (öffentliche Jobseiten sind fast immer offen).
    """
    try:
        parsed  = urlparse(url)
        base    = f"{parsed.scheme}://{parsed.netloc}"
        domain  = parsed.netloc

        if domain not in _robots_cache:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"{base}/robots.txt")
            rp.read()
            _robots_cache[domain] = rp

        return _robots_cache[domain].can_fetch(USER_AGENT, url)
    except Exception:
        return True  # Bei Fehler: crawlen erlaubt


async def scan_single_url(
    url: str,
    context: BrowserContext,
) -> bool:
    """
    Eine URL scannen. Gibt True zurück wenn Treffer gefunden.
    """
    parsed_domain = urlparse(url).netloc.replace("www.", "")

    # Skip wenn bereits gescannt
    if url_already_scanned(url):
        logger.debug(f"Skip (bereits gescannt): {url}")
        return False

    # Skip wenn Domain bereits einen Fund hat (Effizienz)
    if finding_exists_for_domain(parsed_domain):
        logger.debug(f"Skip (Domain bereits mit Fund): {parsed_domain}")
        mark_url_scanned(url, parsed_domain, "existing_finding")
        return False

    # robots.txt prüfen
    if not _check_robots(url):
        logger.debug(f"robots.txt: gesperrt für {url}")
        mark_url_scanned(url, parsed_domain, "robots_blocked")
        return False

    page = await context.new_page()
    found = False

    try:
        await page.set_extra_http_headers({"User-Agent": USER_AGENT})

        logger.info(f"Scanne: {url}")
        response = await page.goto(
            url,
            wait_until="networkidle",
            timeout=PAGE_TIMEOUT_MS,
        )

        if response and response.status >= 400:
            mark_url_scanned(url, parsed_domain, f"http_{response.status}")
            return False

        # Kurz warten damit dynamische Inhalte laden können
        await asyncio.sleep(1.5)

        # Detektor aufrufen
        finding = await detect(page, url)

        if finding:
            finding_id = save_finding(finding)
            logger.info(
                f"🔴 FUND #{finding_id}: {finding.company_name} "
                f"({finding.domain}) — {finding.field_label[:60]}"
            )
            await notify_new_finding(finding)
            found = True

        mark_url_scanned(url, parsed_domain, "scanned")

    except Exception as e:
        logger.warning(f"Fehler bei {url}: {type(e).__name__}: {e}")
        mark_url_scanned(url, parsed_domain, f"error")

    finally:
        await page.close()

    return found


async def run_scan_batch(urls: list[str]) -> tuple[int, int]:
    """
    Batch von URLs parallel scannen (MAX_WORKERS parallele Browser).
    Gibt (gescannt, gefunden) zurück.
    """
    scanned = 0
    found   = 0

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(
            headless=HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        # Mehrere Kontexte = mehrere parallele Browser-Identitäten
        contexts = [
            await browser.new_context(
                viewport={"width": 1280, "height": 800},
                locale="de-DE",
                timezone_id="Europe/Berlin",
            )
            for _ in range(MAX_WORKERS)
        ]

        semaphore = asyncio.Semaphore(MAX_WORKERS)

        async def bounded_scan(url: str, ctx: BrowserContext) -> bool:
            async with semaphore:
                return await scan_single_url(url, ctx)

        # URLs auf Kontexte verteilen
        tasks = [
            bounded_scan(url, contexts[i % MAX_WORKERS])
            for i, url in enumerate(urls)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            scanned += 1
            if r is True:
                found += 1

        for ctx in contexts:
            await ctx.close()
        await browser.close()

    return scanned, found


async def run_full_scan() -> dict:
    """
    Vollständiger Scan-Zyklus:
    1. Seed URLs sammeln
    2. In Batches scannen
    3. Statistiken zurückgeben
    """
    logger.info("=" * 60)
    logger.info("SCAN-ZYKLUS GESTARTET")
    logger.info("=" * 60)

    run_id     = start_scan_run()
    all_urls   = []
    total_found = 0
    total_scanned = 0

    # URLs sammeln (Generator läuft durch alle Quellen)
    logger.info("Sammle Seed-URLs...")
    for url in generate_seed_urls():
        all_urls.append(url)
        # Alle 50 URLs sofort in einem Batch scannen
        if len(all_urls) >= 50:
            scanned, found = await run_scan_batch(all_urls)
            total_scanned += scanned
            total_found   += found
            all_urls = []
            logger.info(
                f"Zwischenstand: {total_scanned} gescannt, "
                f"{total_found} Funde"
            )

    # Restliche URLs scannen
    if all_urls:
        scanned, found = await run_scan_batch(all_urls)
        total_scanned += scanned
        total_found   += found

    finish_scan_run(run_id, total_scanned, total_found)

    summary = {
        "run_id": run_id,
        "scanned": total_scanned,
        "found": total_found,
    }

    logger.info(f"SCAN ABGESCHLOSSEN: {summary}")
    return summary
