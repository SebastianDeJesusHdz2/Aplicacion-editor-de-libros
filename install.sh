#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_ROOT="$HOME/.local/share/pescritura"
INSTALL_DIR="$INSTALL_ROOT/app"
DATA_DIR="$INSTALL_ROOT/data"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
LAUNCHER="$BIN_DIR/pescritura"
DESKTOP_FILE="$DESKTOP_DIR/pescritura.desktop"
ICON_FILE="$ICON_DIR/pescritura.svg"

mkdir -p "$INSTALL_DIR" "$DATA_DIR/library" "$DATA_DIR/exports" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR"

if [ -d "$INSTALL_ROOT/library" ] && [ ! -e "$DATA_DIR/library/project.json" ]; then
  rsync -a --ignore-existing "$INSTALL_ROOT/library"/ "$DATA_DIR/library"/
fi

if [ -d "$INSTALL_ROOT/exports" ]; then
  rsync -a --ignore-existing "$INSTALL_ROOT/exports"/ "$DATA_DIR/exports"/
fi

rsync -a --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '.mypy_cache' \
  --exclude '.ruff_cache' \
  --exclude '.agents' \
  --exclude '.codex' \
  --exclude 'library' \
  --exclude 'exports' \
  --exclude 'backups' \
  --exclude '*.pescritura' \
  --exclude '*.csv' \
  --exclude '*.pdf' \
  "$SOURCE_DIR"/ "$INSTALL_DIR"/

install -m 644 "$SOURCE_DIR/pescritura_icon.svg" "$ICON_FILE"

if [ ! -d "$INSTALL_DIR/.venv" ]; then
  python3 -m venv "$INSTALL_DIR/.venv"
fi

"$INSTALL_DIR/.venv/bin/python" -m pip install --upgrade pip >/dev/null
"$INSTALL_DIR/.venv/bin/python" -m pip install -r "$INSTALL_DIR/requirements.txt"

cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$INSTALL_DIR"
export PESCRITURA_DATA_DIR="$DATA_DIR"
exec "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/main.py" "\$@"
EOF
chmod +x "$LAUNCHER"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Pescritura
Comment=Aplicacion para escribir novelas y exportar obras
Exec=$LAUNCHER
Icon=$ICON_FILE
Terminal=false
Categories=Office;WordProcessor;TextEditor;
StartupNotify=true
EOF

update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
xdg-desktop-menu forceupdate >/dev/null 2>&1 || true

echo "Instalado en: $INSTALL_DIR"
echo "Datos de usuario: $DATA_DIR"
echo "Lanzador: $LAUNCHER"
echo "Desktop file: $DESKTOP_FILE"
echo "Icono: $ICON_FILE"
