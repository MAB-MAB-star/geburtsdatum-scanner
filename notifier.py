"""
Benachrichtigungen & Berichte.
E-Mail bei Neufund + PDF/HTML-Report-Generator.
"""

import json
import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from .config import (
    EMAIL_ENABLED, EMAIL_FROM, EMAIL_TO,
    EMAIL_SMTP_HOST, EMAIL_SMTP_PORT,
    EMAIL_SMTP_USER, EMAIL_SMTP_PASS,
    REPORTS_DIR,
)

logger = logging.getLogger(__name__)


async def notify_new_finding(finding):
    """Bei einem neuen Fund: E-Mail + Log-Eintrag."""
    logger.info(
        f"\n{'='*60}\n"
        f"🔴 NEUER FUND\n"
        f"Unternehmen : {finding.company_name}\n"
        f"URL         : {finding.url}\n"
        f"Feld        : {finding.field_label}\n"
        f"Methode     : {finding.detection_method}\n"
        f"Screenshot  : {finding.screenshot_path}\n"
        f"Zeitstempel : {finding.timestamp}\n"
        f"DOM-Hash    : {finding.dom_hash[:16]}...\n"
        f"{'='*60}"
    )

    if EMAIL_ENABLED:
        _send_email(finding)


def _send_email(finding):
    """E-Mail-Benachrichtigung senden."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = (
            f"[Geburtsdatum-Scanner] Neuer Fund: {finding.company_name}"
        )
        msg["From"] = EMAIL_FROM
        msg["To"]   = EMAIL_TO

        text_body = f"""
Neuer Geburtsdatum-Pflichtfeld-Verstoß gefunden!

Unternehmen : {finding.company_name}
Domain      : {finding.domain}
URL         : {finding.url}
Stelle      : {finding.job_title}
Feld-Label  : {finding.field_label}
Erkannt via : {finding.detection_method}
Zeitstempel : {finding.timestamp}
DOM-Hash    : {finding.dom_hash}
Screenshot  : {finding.screenshot_path}

Rechtsgrundlagen:
- § 11 AGG: Altersdiskriminierung in Stellenausschreibungen verboten
- Art. 5 Abs. 1 lit. c DSGVO: Datenminimierung
- § 26 BDSG: Beschäftigtendatenschutz

Beschwerde einlegen bei:
- ADS: www.antidiskriminierungsstelle.de
- Datenschutzbehörde je nach Unternehmenssitz
"""

        html_body = f"""
<html><body style="font-family:sans-serif;max-width:600px;margin:auto">
<h2 style="color:#dc2626">🔴 Neuer Fund: {finding.company_name}</h2>
<table style="border-collapse:collapse;width:100%">
<tr><td style="padding:8px;background:#f3f4f6;font-weight:bold">Domain</td>
    <td style="padding:8px">{finding.domain}</td></tr>
<tr><td style="padding:8px;font-weight:bold">URL</td>
    <td style="padding:8px"><a href="{finding.url}">{finding.url}</a></td></tr>
<tr><td style="padding:8px;background:#f3f4f6;font-weight:bold">Stelle</td>
    <td style="padding:8px;background:#f3f4f6">{finding.job_title}</td></tr>
<tr><td style="padding:8px;font-weight:bold">Feld-Label</td>
    <td style="padding:8px"><strong>{finding.field_label}</strong></td></tr>
<tr><td style="padding:8px;background:#f3f4f6;font-weight:bold">Erkannt via</td>
    <td style="padding:8px;background:#f3f4f6">{finding.detection_method}</td></tr>
<tr><td style="padding:8px;font-weight:bold">Zeitstempel</td>
    <td style="padding:8px">{finding.timestamp}</td></tr>
<tr><td style="padding:8px;background:#f3f4f6;font-weight:bold">DOM-Hash</td>
    <td style="padding:8px;background:#f3f4f6;font-family:monospace;font-size:12px">{finding.dom_hash}</td></tr>
</table>
<hr>
<p style="color:#6b7280;font-size:12px">
§ 11 AGG · Art. 5 Abs. 1 lit. c DSGVO · § 26 BDSG
</p>
</body></html>
"""

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            if EMAIL_SMTP_USER:
                server.login(EMAIL_SMTP_USER, EMAIL_SMTP_PASS)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

        logger.info(f"E-Mail gesendet an {EMAIL_TO}")

    except Exception as e:
        logger.error(f"E-Mail fehlgeschlagen: {e}")


def generate_html_report(findings: list[dict]) -> Path:
    """Vollständigen HTML-Report aller Funde generieren."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"report_{ts}.html"

    rows = ""
    for f in findings:
        url = f.get("url", "")
        rows += f"""
        <tr>
          <td>{f.get('company_name','')}</td>
          <td><a href="{url}" target="_blank">{f.get('domain','')}</a></td>
          <td>{f.get('job_title','')[:80]}</td>
          <td><strong>{f.get('field_label','')[:100]}</strong></td>
          <td><code>{f.get('detection_method','')}</code></td>
          <td style="font-size:11px">{f.get('timestamp','')[:19]}</td>
          <td style="font-family:monospace;font-size:10px">{f.get('dom_hash','')[:12]}...</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Geburtsdatum-Pflichtfeld-Scanner — Bericht</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 1400px; margin: 2rem auto; padding: 0 1rem; }}
  h1 {{ color: #dc2626; }}
  .meta {{ color: #6b7280; font-size: 14px; margin-bottom: 2rem; }}
  .stats {{ display: flex; gap: 2rem; margin-bottom: 2rem; }}
  .stat {{ background: #f3f4f6; padding: 1rem 1.5rem; border-radius: 8px; }}
  .stat-n {{ font-size: 28px; font-weight: bold; color: #dc2626; }}
  .stat-l {{ font-size: 13px; color: #6b7280; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #1f2937; color: white; padding: 10px 8px; text-align: left; }}
  td {{ padding: 8px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }}
  tr:hover td {{ background: #fef2f2; }}
  .legal {{ margin-top: 3rem; padding: 1.5rem; background: #fef2f2;
            border: 1px solid #fecaca; border-radius: 8px; font-size: 13px; }}
  code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 11px; }}
</style>
</head>
<body>
<h1>🔴 Geburtsdatum-Pflichtfeld-Scanner — Ergebnisbericht</h1>
<p class="meta">
  Generiert: {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} UTC ·
  Zweck: Dokumentation von AGG- und DSGVO-Verstößen in Bewerbungsformularen
</p>

<div class="stats">
  <div class="stat">
    <div class="stat-n">{len(findings)}</div>
    <div class="stat-l">Bestätigte Funde</div>
  </div>
  <div class="stat">
    <div class="stat-n">{len(set(f.get('domain','') for f in findings))}</div>
    <div class="stat-l">Betroffene Domains</div>
  </div>
</div>

<table>
<thead>
<tr>
  <th>Unternehmen</th>
  <th>Domain</th>
  <th>Stelle</th>
  <th>Feld-Label</th>
  <th>Erkennungs-Layer</th>
  <th>Zeitstempel</th>
  <th>DOM-Hash</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>

<div class="legal">
<strong>Rechtsgrundlagen für Beschwerden:</strong><br>
§ 11 AGG — Stellenausschreibungen dürfen keine Altersdiskriminierung ermöglichen<br>
Art. 5 Abs. 1 lit. c DSGVO — Grundsatz der Datenminimierung<br>
§ 26 BDSG — Datenerhebung im Beschäftigungsverhältnis nur wenn erforderlich<br><br>
<strong>Beschwerdestellen:</strong>
Antidiskriminierungsstelle des Bundes (ADS) ·
BayLDA (Bayern) · LDI NRW · LfDI Baden-Württemberg
</div>

</body>
</html>
"""

    report_path.write_text(html, encoding="utf-8")
    logger.info(f"Report gespeichert: {report_path}")
    return report_path


def generate_json_export(findings: list[dict]) -> Path:
    """JSON-Export für Weiterverarbeitung."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = REPORTS_DIR / f"findings_{ts}.json"
    path.write_text(
        json.dumps(findings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
