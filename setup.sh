#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# GEBURTSDATUM-SCANNER — Installations-Script
# Führe aus mit: bash setup.sh
# ═══════════════════════════════════════════════════════════════

set -e

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   Geburtsdatum-Scanner — Setup                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Python-Version prüfen
python3 --version || { echo "❌ Python 3 nicht gefunden!"; exit 1; }

# Virtuelle Umgebung erstellen
echo "→ Erstelle virtuelle Python-Umgebung..."
python3 -m venv venv
source venv/bin/activate

# Abhängigkeiten installieren
echo "→ Installiere Python-Pakete..."
pip install --upgrade pip -q
pip install \
    playwright \
    requests \
    beautifulsoup4 \
    lxml \
    schedule \
    python-dotenv \
    -q

# Playwright-Browser installieren
echo "→ Installiere Chromium-Browser (Playwright)..."
playwright install chromium
playwright install-deps chromium 2>/dev/null || true

# Verzeichnisse anlegen
echo "→ Erstelle Verzeichnisstruktur..."
mkdir -p output/screenshots output/reports logs data

echo ""
echo "✅ Installation abgeschlossen!"
echo ""
echo "VERWENDUNG:"
echo "  source venv/bin/activate          # Umgebung aktivieren"
echo "  python main.py --stats            # Statistiken"
echo "  python main.py --test URL         # URL testen"
echo "  python main.py --once             # Einmaliger Scan"
echo "  python main.py                    # Dauerhafter Betrieb (alle 6h)"
echo ""
echo "E-Mail-Benachrichtigungen:"
echo "  → crawler/config.py öffnen und EMAIL_ENABLED = True setzen"
echo ""
