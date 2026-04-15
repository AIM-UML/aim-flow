#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "AIM Flow currently supports macOS only."
  exit 1
fi

if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "Python 3 is required. Install python3.12 with Homebrew and rerun this script."
  exit 1
fi

PYTHON_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$PYTHON_VERSION" != "3.12" && "$PYTHON_VERSION" != "3.11" ]]; then
  echo "Detected Python $PYTHON_VERSION. AIM Flow is most reliable on Python 3.11 or 3.12."
  echo "If the install fails, run: brew install python@3.12"
fi

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required for ffmpeg and portaudio."
  echo "Install Homebrew from https://brew.sh and rerun this script."
  exit 1
fi

echo "Installing macOS dependencies with Homebrew..."
brew install ffmpeg portaudio

echo "Creating virtual environment..."
"$PYTHON_BIN" -m venv .venv

echo "Installing Python dependencies..."
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/pip install -r requirements.txt

echo "Creating app icon..."
bash scripts/create_icns.sh

chmod +x run.sh scripts/build_app.sh scripts/create_icns.sh

cat <<'EOF'

AIM Flow is installed.

Next steps:
1. Run ./run.sh
2. When prompted, grant Accessibility and Microphone permissions
3. Press Option+Space to start and stop dictation

To build a standalone .app bundle:
  ./scripts/build_app.sh
EOF
