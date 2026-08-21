#!/bin/bash
# build_and_sign.sh — build local + semnare ad-hoc, pentru distribuție
# internă (colegi) fara cont Apple Developer Program platit ($99/an) si
# fara niciun pas manual de configurare (nu e nevoie sa creezi vreun
# certificat in Keychain). Elimina eroarea grava "App is damaged and
# can't be opened" (aplicatie nesemnata deloc) — nu poate elimina
# complet avertismentul "Developer cannot be verified" la prima
# deschidere directa a .app-ului fara wrapper (asta cere notarizare
# reala Apple), dar impreuna cu Lanseaza_GDCVideoRepair.command
# rezolva tot fluxul.
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="GDCVideoRepair"

echo "==> Compilez $APP_NAME.app (PyInstaller)..."
python3 -m pip install --upgrade pip --quiet
pip install pyinstaller --quiet
pyinstaller build/build-mac.spec --noconfirm

APP_PATH="dist/$APP_NAME.app"
if [ ! -d "$APP_PATH" ]; then
    echo "EROARE: $APP_PATH nu a fost generat." >&2
    exit 1
fi

echo "==> Curat atributele extinse (xattr -cr)..."
xattr -cr "$APP_PATH"

echo "==> Semnez ad-hoc (fara cont Apple Developer)..."
codesign --force --deep --sign - "$APP_PATH"

echo "==> Verific semnatura..."
codesign --verify --verbose "$APP_PATH"

echo ""
echo "==> Gata: $APP_PATH"
echo "    Pune-l intr-un folder impreuna cu Lanseaza_GDCVideoRepair.command"
echo "    inainte sa il trimiti colegilor (arhiveaza cu 'ditto', nu cu"
echo "    Finder/'Compress', ca sa pastrezi permisiunile Mac corect)."
