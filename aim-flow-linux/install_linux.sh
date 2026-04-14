#!/usr/bin/env bash
# AIM Flow — Linux installer (Ubuntu / Debian)
# Usage:  bash install_linux.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# ---------------------------------------------------------------------------
# Guard: Linux only
# ---------------------------------------------------------------------------
if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This installer targets Linux (Ubuntu/Debian)."
  echo "For macOS, run the ../aim-flow/install.sh script instead."
  exit 1
fi

# ---------------------------------------------------------------------------
# Detect package manager (apt-get required)
# ---------------------------------------------------------------------------
if ! command -v apt-get >/dev/null 2>&1; then
  echo "apt-get not found.  This installer supports Ubuntu/Debian only."
  echo "On other distros install manually:"
  echo "  ffmpeg, portaudio-devel (or equivalent), libdbus-1-dev,"
  echo "  python3-dev, python3-venv, xclip (or xsel / wl-clipboard),"
  echo "  libnotify-bin"
  exit 1
fi

# ---------------------------------------------------------------------------
# Python version check (3.11 or 3.12 preferred)
# ---------------------------------------------------------------------------
if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
elif command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="python3.11"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "Python 3 is required.  Install with:"
  echo "  sudo apt-get install python3.12 python3.12-venv python3.12-dev"
  exit 1
fi

PYTHON_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "Using Python $PYTHON_VERSION  ($PYTHON_BIN)"

if [[ "$PYTHON_VERSION" != "3.12" && "$PYTHON_VERSION" != "3.11" ]]; then
  echo "WARNING: AIM Flow is most reliable on Python 3.11 or 3.12."
  echo "         If the install fails, run:"
  echo "           sudo apt-get install python3.12 python3.12-venv python3.12-dev"
fi

# ---------------------------------------------------------------------------
# System dependencies
# ---------------------------------------------------------------------------
echo ""
echo "Installing system dependencies via apt-get..."
sudo apt-get update -qq
sudo apt-get install -y \
  ffmpeg \
  portaudio19-dev \
  libdbus-1-dev \
  python3-dev \
  python3-venv \
  libnotify-bin \
  xclip

# Optional: xsel as a fallback clipboard tool.
sudo apt-get install -y xsel || true

# Optional: wl-clipboard for Wayland sessions.
sudo apt-get install -y wl-clipboard || true

# Optional: ydotool for Wayland keystroke injection (requires a running daemon).
# Uncomment if you run a pure Wayland session without XWayland:
# sudo apt-get install -y ydotool || true

echo "System dependencies installed."

# ---------------------------------------------------------------------------
# Python virtual environment
# ---------------------------------------------------------------------------
echo ""
echo "Creating virtual environment (.venv)..."
"$PYTHON_BIN" -m venv .venv

echo "Upgrading pip / setuptools / wheel..."
.venv/bin/python -m pip install --upgrade pip setuptools wheel

echo "Installing Python dependencies..."
.venv/bin/pip install -r requirements_linux.txt

# ---------------------------------------------------------------------------
# Copy shared assets from the macOS project if not already present
# ---------------------------------------------------------------------------
if [[ ! -f "status_logo.png" ]]; then
  if [[ -f "../aim-flow/status_logo.png" ]]; then
    echo "Copying status_logo.png from ../aim-flow/..."
    cp "../aim-flow/status_logo.png" .
  elif [[ -f "../status_logo.png" ]]; then
    cp "../status_logo.png" .
  else
    echo "WARNING: status_logo.png not found.  The tray icon will use a blank image."
    echo "         Copy the PNG to $ROOT_DIR/status_logo.png to fix this."
  fi
fi

# ---------------------------------------------------------------------------
# Make scripts executable
# ---------------------------------------------------------------------------
chmod +x run_linux.sh

cat <<'EOF'

AIM Flow (Linux) is installed.

Next steps:
1. Run ./run_linux.sh
2. AIM Flow will appear in your system tray.
3. Press Ctrl+Shift+Space to start and stop dictation.

Notes:
  • On X11   — clipboard via xclip; paste via pynput (Ctrl+V).
  • On Wayland — clipboard via wl-copy; paste via ydotool (if installed)
                 or pynput/XWayland fallback.
  • Notifications require libnotify / notify-send (installed above).
  • If the tray icon is invisible, install a tray/appindicator extension for
    your desktop (e.g. TopIcons Plus on GNOME, or use KDE/XFCE).

EOF
