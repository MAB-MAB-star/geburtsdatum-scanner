"""
Seed Discovery — Schicht 1 & 2 der Pipeline.
Sucht Karriereseiten-URLs über öffentliche Jobbörsen und Google.
"""

import re
import time
import random
import logging
import urllib.parse
from typing import Iterator

import requests
from bs4 import BeautifulSoup

from .config import (
    JOB_SEARCH_TERMS, CAREER_URL_PATTERNS,
    EXCLUDED_DOMAINS, USER_AGENT, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX,
)

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _sleep():
    time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))


def _is_excluded(url: str) -> bool:
    for domain in EXCLUDED_DOMAINS:
        if domain in url:
            return True
    return False


def _extract_domain(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def _looks_like_career_url(url: str) -> bool:
    url_lower = url.lower()
    return any(pat in url_lower for pat in CAREER_URL_PATTERNS)


def discover_from_google(term: str, max_results: int = 30) -> list[str]:
    """
    Google-Suche nach Karriereseiten.
    Sucht: '{term} Bewerbungsformular online bewerben site:de'
    """
    urls = []
    query = f'"{term}" Bewerbungsformular "online bewerben" site:.de'
    encoded = urllib.parse.quote_plus(query)
    search_url = f"https://www.google.de/search?q={encoded}&num={max_results}&hl=de"

    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"Google: HTTP {resp.status_code}")
            return urls

        soup = BeautifulSoup(resp.text, "lxml")

        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Google-Weiterleitungs-URLs entpacken
            if href.startswith("/url?q="):
                href = urllib.parse.unquote(href[7:].split("&")[0])
            if href.startswith("http") and not _is_excluded(href):
                urls.append(href)

    except Exception as e:
        logger.warning(f"Google-Suche fehlgeschlagen: {e}")

    _sleep()
    return list(dict.fromkeys(urls))  # Deduplizieren


def discover_from_indeed(term: str, pages: int = 3) -> list[str]:
    """
    Indeed.de nach Firmen-Domains durchsuchen.
    Extrahiert die Original-Unternehmens-URLs aus Stellenanzeigen.
    """
    urls = []
    for page in range(pages):
        start = page * 15
        search_url = (
            f"https://de.indeed.com/jobs?q={urllib.parse.quote_plus(term)}"
            f"&l=Deutschland&start={start}&lang=de"
        )
        try:
            resp = requests.get(search_url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")

            # Unternehmens-Webseiten aus Stellendetails extrahieren
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "/rc/clk" in href or "/company/" in href:
                    continue
                if href.startswith("http") and not _is_excluded(href):
                    # Nur Unternehmens-Domains, nicht Indeed-interne Links
                    if "indeed.com" not in href:
                        urls.append(href)

        except Exception as e:
            logger.debug(f"Indeed Seite {page}: {e}")
        _sleep()

    return list(dict.fromkeys(urls))


def discover_from_arbeitsagentur(term: str, max_results: int = 50) -> list[str]:
    """
    Bundesagentur für Arbeit — offizielle Job-API.
    Gibt strukturierte Daten zurück, sehr zuverlässig.
    """
    urls = []
    api_url = (
        f"https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
        f"?was={urllib.parse.quote(term)}&wo=Deutschland&size={max_results}"
    )
    api_headers = {
        **HEADERS,
        "X-API-Key": "jobboerse-jobsuche",
    }
    try:
        resp = requests.get(api_url, headers=api_headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for job in data.get("stellenangebote", []):
                ext_url = job.get("externeUrl", "")
                if ext_url and not _is_excluded(ext_url):
                    urls.append(ext_url)
                arbgeber_url = job.get("arbeitgeber", {}).get("url", "")
                if arbgeber_url and not _is_excluded(arbgeber_url):
                    urls.append(arbgeber_url)
    except Exception as e:
        logger.debug(f"Arbeitsagentur API: {e}")

    _sleep()
    return list(dict.fromkeys(urls))


def discover_career_links_from_domain(domain_url: str) -> list[str]:
    """
    Startet bei einer Unternehmens-Domain und sucht Karriereseiten-Links.
    Crawlt bis Tiefe 2.
    """
    found = []
    try:
        base_url = domain_url.rstrip("/")
        resp = requests.get(base_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("http"):
                href = urllib.parse.urljoin(base_url, href)

            if _is_excluded(href):
                continue
            if _looks_like_career_url(href):
                found.append(href)

    except Exception as e:
        logger.debug(f"Domain-Crawl {domain_url}: {e}")

    _sleep()
    return list(dict.fromkeys(found))


def find_application_forms(career_url: str) -> list[str]:
    """
    Auf der Karriereseite: Links zu konkreten Bewerbungsformularen suchen.
    """
    forms = []
    form_patterns = [
        r"bewerb", r"apply", r"online.bewerbung",
        r"jetzt.bewerben", r"bewerbungsformular",
    ]
    form_re = re.compile("|".join(form_patterns), re.I)

    try:
        resp = requests.get(career_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")

        # Direkte Formulare auf der Seite
        if soup.find("form"):
            forms.append(career_url)

        # Links zu Bewerbungsformularen
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"]
            if not href.startswith("http"):
                href = urllib.parse.urljoin(career_url, href)
            if form_re.search(text) or form_re.search(href):
                if not _is_excluded(href):
                    forms.append(href)

        # Einzelne Stellenanzeigen mit Bewerbungsbutton
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("http"):
                href = urllib.parse.urljoin(career_url, href)
            if any(kw in href.lower() for kw in [
                "filialleiter", "marktleiter", "storemanager",
                "store-manager", "filialleitung"
            ]):
                if not _is_excluded(href):
                    forms.append(href)

    except Exception as e:
        logger.debug(f"Form-Suche {career_url}: {e}")

    _sleep()
    return list(dict.fromkeys(forms))


def generate_seed_urls() -> Iterator[str]:
    """
    Haupt-Generator: Liefert kontinuierlich URLs zum Scannen.
    Kombiniert alle Quellen.
    """
    seen_domains = set()

    for term in JOB_SEARCH_TERMS:
        logger.info(f"Suche Suchbegriff: '{term}'")

        # Quelle 1: Bundesagentur für Arbeit
        for url in discover_from_arbeitsagentur(term):
            domain = _extract_domain(url)
            if domain and domain not in seen_domains:
                seen_domains.add(domain)
                career_links = discover_career_links_from_domain(url)
                for link in career_links:
                    form_links = find_application_forms(link)
                    for fl in form_links:
                        yield fl
                    if not form_links:
                        yield link

        # Quelle 2: Google
        for url in discover_from_google(term):
            domain = _extract_domain(url)
            if domain and domain not in seen_domains:
                seen_domains.add(domain)
                form_links = find_application_forms(url)
                for fl in form_links:
                    yield fl
                if not form_links:
                    yield url

        # Quelle 3: Indeed
        for url in discover_from_indeed(term, pages=2):
            domain = _extract_domain(url)
            if domain and domain not in seen_domains:
                seen_domains.add(domain)
                career_links = discover_career_links_from_domain(url)
                for link in career_links:
                    yield link

        _sleep()
