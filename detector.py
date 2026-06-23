"""
Detektor — Schicht 4 der Pipeline.
Analysiert gerenderte DOM-Strukturen auf Geburtsdatum-Pflichtfelder.
5 unabhängige Erkennungs-Layer für maximale Treffsicherheit.
"""

import re
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from .config import (
    BIRTH_LABEL_PATTERNS, REQUIRED_INDICATORS,
    FORM_CONTEXT_PATTERNS, FILIALLEITER_PATTERNS,
    SCREENSHOTS_DIR,
)
from .database import Finding

logger = logging.getLogger(__name__)

# Kompilierte Regex-Objekte (einmalig beim Import)
BIRTH_RE    = re.compile("|".join(BIRTH_LABEL_PATTERNS), re.I)
REQUIRED_RE = re.compile("|".join(REQUIRED_INDICATORS), re.I)
CONTEXT_RE  = re.compile("|".join(FORM_CONTEXT_PATTERNS), re.I)
JOB_RE      = re.compile("|".join(FILIALLEITER_PATTERNS), re.I)


def extract_domain(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")


def make_screenshot_path(domain: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", domain)
    return SCREENSHOTS_DIR / f"{safe}_{ts}.png"


async def detect(page, url: str) -> Optional[Finding]:
    """
    Haupt-Erkennungsfunktion.
    Gibt Finding zurück wenn Verstoß gefunden, sonst None.
    """
    try:
        full_text = await page.inner_text("body")
    except Exception:
        full_text = ""

    # Kontext-Check: Ist das überhaupt ein Bewerbungsformular mit Filialleiter-Kontext?
    has_job_context  = bool(JOB_RE.search(full_text))
    has_form_context = bool(CONTEXT_RE.search(full_text))

    if not (has_job_context or has_form_context):
        return None

    domain     = extract_domain(url)
    job_title  = _extract_job_title(full_text)
    company    = _extract_company(page, url)

    # ── Layer A: Label-Text mit Stern-Markierung ──────────────────────────────
    result = await _layer_a_label_stern(page, url, domain, company, job_title)
    if result:
        return result

    # ── Layer B: HTML-Attribut required + Datums-Feldname ────────────────────
    result = await _layer_b_html_required(page, url, domain, company, job_title)
    if result:
        return result

    # ── Layer C: ARIA-required + birth-bezogene aria-label ───────────────────
    result = await _layer_c_aria(page, url, domain, company, job_title)
    if result:
        return result

    # ── Layer D: Placeholder-Text ─────────────────────────────────────────────
    result = await _layer_d_placeholder(page, url, domain, company, job_title)
    if result:
        return result

    # ── Layer E: JavaScript-Validierungstest (Form ohne Wert absenden) ────────
    result = await _layer_e_submit_test(page, url, domain, company, job_title)
    if result:
        return result

    return None


async def _make_finding(page, url, domain, company, job_title, label, method) -> Finding:
    """Screenshot + Hash erstellen und Finding bauen."""
    ss_path = make_screenshot_path(domain)
    try:
        await page.screenshot(path=str(ss_path), full_page=True)
    except Exception as e:
        logger.warning(f"Screenshot fehlgeschlagen: {e}")
        ss_path = Path("kein_screenshot")

    html     = await page.content()
    dom_hash = hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()
    ts       = datetime.now(timezone.utc).isoformat()

    logger.info(f"✓ TREFFER [{method}] {domain} — '{label}'")

    return Finding(
        url=url,
        domain=domain,
        company_name=company,
        job_title=job_title,
        field_label=label,
        detection_method=method,
        screenshot_path=str(ss_path),
        dom_hash=dom_hash,
        timestamp=ts,
    )


async def _layer_a_label_stern(page, url, domain, company, job_title):
    """Label-Text enthält Geburtsdatum-Begriff UND Stern (*)."""
    try:
        labels = await page.query_selector_all("label, .label, [class*='label']")
        for label_el in labels:
            text = await label_el.inner_text()
            if BIRTH_RE.search(text) and "*" in text:
                # Zusatz-Check: Ist das Feld auch wirklich required?
                for_attr = await label_el.get_attribute("for") or ""
                if for_attr:
                    input_el = await page.query_selector(f"#{for_attr}")
                    if input_el:
                        return await _make_finding(
                            page, url, domain, company, job_title,
                            text.strip()[:200], "A-Label-Stern"
                        )
                # Auch ohne for-Attribut: Stern im Label ist Pflichtfeld-Indikator
                return await _make_finding(
                    page, url, domain, company, job_title,
                    text.strip()[:200], "A-Label-Stern"
                )
    except Exception as e:
        logger.debug(f"Layer A Fehler: {e}")
    return None


async def _layer_b_html_required(page, url, domain, company, job_title):
    """Input-Feld mit required-Attribut und Geburts-bezogenem Name/ID."""
    selectors = [
        'input[required][type="date"]',
        'input[required][name*="birth"]',
        'input[required][name*="geburts"]',
        'input[required][id*="geburts"]',
        'input[required][name*="dob"]',
        'input[required][id*="dob"]',
        'input[required][name*="birthday"]',
        'input[required][id*="birthday"]',
    ]
    try:
        for sel in selectors:
            el = await page.query_selector(sel)
            if el:
                label_text = await _get_label_text(page, el)
                if not label_text:
                    label_text = await el.get_attribute("name") or sel
                return await _make_finding(
                    page, url, domain, company, job_title,
                    label_text[:200], "B-HTML-required"
                )
    except Exception as e:
        logger.debug(f"Layer B Fehler: {e}")
    return None


async def _layer_c_aria(page, url, domain, company, job_title):
    """aria-required=true + aria-label enthält Geburtsdatum-Begriff."""
    try:
        aria_els = await page.query_selector_all('[aria-required="true"]')
        for el in aria_els:
            aria_label = await el.get_attribute("aria-label") or ""
            aria_desc  = await el.get_attribute("aria-describedby") or ""
            label_text = aria_label or aria_desc
            if BIRTH_RE.search(label_text):
                return await _make_finding(
                    page, url, domain, company, job_title,
                    label_text[:200], "C-ARIA-required"
                )
    except Exception as e:
        logger.debug(f"Layer C Fehler: {e}")
    return None


async def _layer_d_placeholder(page, url, domain, company, job_title):
    """Placeholder-Text enthält TT.MM.JJJJ oder ähnliches."""
    placeholder_patterns = [
        r"tt\.mm\.jjjj",
        r"dd\.mm\.yyyy",
        r"geburtsdatum",
        r"\d{2}\.\d{2}\.\d{4}",   # Datumsformat-Hinweis
    ]
    combined = re.compile("|".join(placeholder_patterns), re.I)
    try:
        inputs = await page.query_selector_all("input[placeholder]")
        for inp in inputs:
            placeholder = await inp.get_attribute("placeholder") or ""
            if combined.search(placeholder):
                # Prüfen ob Feld required ist
                is_required = await inp.get_attribute("required")
                if is_required is not None:
                    label_text = await _get_label_text(page, inp) or placeholder
                    return await _make_finding(
                        page, url, domain, company, job_title,
                        label_text[:200], "D-Placeholder"
                    )
    except Exception as e:
        logger.debug(f"Layer D Fehler: {e}")
    return None


async def _layer_e_submit_test(page, url, domain, company, job_title):
    """
    Stärkster Beweis: Formular ohne Geburtsdatum-Wert absenden
    und Validierungsfehler-Meldung analysieren.
    Vorsicht: Formular wird NICHT wirklich abgesendet (kein Submit-Button-Klick).
    """
    birth_error_patterns = [
        r"geburtsdatum.*?(pflicht|required|eingeben|angeben)",
        r"bitte.*?geburtsdatum",
        r"gültiges.*?geburtsdatum",
        r"birth.*?(required|invalid|enter)",
    ]
    error_re = re.compile("|".join(birth_error_patterns), re.I)

    try:
        # HTML5-Validierung triggern ohne tatsächlichen Submit
        result = await page.evaluate("""
            () => {
                const forms = document.querySelectorAll('form');
                const errors = [];
                for (const form of forms) {
                    const inputs = form.querySelectorAll(
                        'input[required], select[required]'
                    );
                    for (const inp of inputs) {
                        if (!inp.validity.valid) {
                            const label = document.querySelector(
                                'label[for="' + inp.id + '"]'
                            );
                            const labelText = label ? label.innerText : (inp.name || inp.id);
                            errors.push({
                                name: inp.name || '',
                                id: inp.id || '',
                                label: labelText,
                                type: inp.type || '',
                                validationMsg: inp.validationMessage || ''
                            });
                        }
                    }
                }
                return errors;
            }
        """)

        if result:
            for field in result:
                label_text = field.get("label", "")
                name       = field.get("name", "")
                if BIRTH_RE.search(label_text) or BIRTH_RE.search(name):
                    return await _make_finding(
                        page, url, domain, company, job_title,
                        f"{label_text} (name={name})"[:200],
                        "E-HTML5-Validierung"
                    )
    except Exception as e:
        logger.debug(f"Layer E Fehler: {e}")
    return None


async def _get_label_text(page, input_el) -> str:
    """Zugehöriges Label-Element für ein Input-Feld finden."""
    try:
        input_id = await input_el.get_attribute("id")
        if input_id:
            label = await page.query_selector(f'label[for="{input_id}"]')
            if label:
                return (await label.inner_text()).strip()
        # Fallback: übergeordnetes label-Element
        return await input_el.evaluate("""
            el => {
                const label = el.closest('label');
                return label ? label.innerText.trim() : '';
            }
        """)
    except Exception:
        return ""


def _extract_job_title(text: str) -> str:
    """Versucht den Stellentitel aus dem Seitentext zu extrahieren."""
    match = JOB_RE.search(text)
    if match:
        start = max(0, match.start() - 20)
        end   = min(len(text), match.end() + 60)
        snippet = text[start:end].strip().split("\n")[0]
        return snippet[:150]
    return "Unbekannte Stelle"


def _extract_company(page, url: str) -> str:
    """Domain als Firmenname-Fallback."""
    domain = extract_domain(url)
    # Erste Teile der Domain als Firmenname
    parts = domain.split(".")
    return parts[0].replace("-", " ").title() if parts else domain
