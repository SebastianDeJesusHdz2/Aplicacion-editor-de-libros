#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="$HOME/.local/share/pescritura"
INSTALL_DIR="$INSTALL_ROOT/app"
DATA_DIR="$INSTALL_ROOT/data"
BIN_DIR="$HOME/.local/bin"
DESKTOP_FILE="$HOME/.local/share/applications/pescritura.desktop"
ICON_FILE="$HOME/.local/share/icons/hicolor/scalable/apps/pescritura.svg"
LAUNCHER="$BIN_DIR/pescritura"

rm -f "$LAUNCHER" "$DESKTOP_FILE"
rm -f "$ICON_FILE"
rm -rf "$INSTALL_DIR"
rmdir "$INSTALL_ROOT" >/dev/null 2>&1 || true

update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
xdg-desktop-menu forceupdate >/dev/null 2>&1 || true

echo "Desinstalado."
echo "Datos conservados en: $DATA_DIR"
