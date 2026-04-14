# AIM Flow

Free, open-source, fully local speech-to-text for macOS and Linux — no cloud, no API keys, no subscription.

AIM Flow lives in your menu bar. Press a hotkey, speak, and the transcribed text is automatically pasted into whatever field you were typing in.

Created by Jordi Lopez for the [Artificial Intelligence Multidisciplinary Society (AIMS)](https://github.com/jangel19).

---

## How it works

1. The AIMS "A" logo sits in your menu bar.
2. Press `Ctrl+Shift+Space` to start recording — the logo shows a live waveform.
3. Press `Ctrl+Shift+Space` again to stop.
4. Whisper transcribes your audio locally on your machine.
5. The text is automatically pasted into the active field.

---

## Requirements

### macOS
- macOS 12 or later
- Python 3.11 or 3.12 (3.12 recommended)
- [Homebrew](https://brew.sh)

### Linux (Ubuntu / Debian)
- Ubuntu 20.04+ or any Debian-based distro
- Python 3.11 or 3.12
- A system tray (GNOME with AppIndicator extension, KDE, XFCE, etc.)

---

## Installation

### macOS

#### Step 1 — Clone and install

```bash
git clone https://github.com/jangel19/aim-flow.git
cd aim-flow
./install.sh
```

This installs `ffmpeg` and `portaudio` via Homebrew, creates a Python virtual environment, installs all dependencies, and generates the app icon.

#### Step 2 — Build the app

```bash
./scripts/build_app.sh
```

This creates `dist/AIM Flow.app`.

#### Step 3 — Move to Applications

```bash
cp -r "dist/AIM Flow.app" /Applications/
```

Or drag `dist/AIM Flow.app` to your `/Applications` folder in Finder.

#### Step 4 — Launch AIM Flow

Open `/Applications/AIM Flow.app`. The AIMS "A" logo will appear in your menu bar.

#### Step 5 — Grant permissions (one-time setup)

This is the most important step. Without these, the hotkey and paste will not work.

Open **System Settings → Privacy & Security** and enable the following for **AIM Flow**:

| Permission | Where to find it | Why it's needed |
|---|---|---|
| **Accessibility** | Privacy & Security → Accessibility | Lets AIM Flow detect the global hotkey and paste text |
| **Input Monitoring** | Privacy & Security → Input Monitoring | Lets AIM Flow listen for `Ctrl+Shift+Space` system-wide |
| **Microphone** | Privacy & Security → Microphone | Lets AIM Flow record your voice (macOS will prompt automatically) |

**After enabling both Accessibility and Input Monitoring, quit and relaunch AIM Flow.** macOS does not apply permission changes to a running process.

> Tip: If AIM Flow does not appear in the Accessibility or Input Monitoring list, try using the hotkey or the "Toggle Recording" menu item once — macOS will add it to the list automatically.

---

### Linux

#### Step 1 — Clone and switch to the Linux branch

```bash
git clone https://github.com/jangel19/aim-flow.git
cd aim-flow
git checkout linux
cd aim-flow-linux
```

#### Step 2 — Install and run

```bash
bash install_linux.sh
./run_linux.sh
```

`install_linux.sh` uses `apt-get` to install `ffmpeg`, `portaudio19-dev`, `libdbus-1-dev`, `xclip`, and `libnotify-bin`, then creates a Python virtual environment and installs all Python dependencies.

The AIMS "A" logo will appear in your system tray.

> **GNOME users:** The system tray is hidden by default. Install the [AppIndicator and KStatusNotifierItem Support](https://extensions.gnome.org/extension/615/appindicator-support/) extension to make it visible.

> **Wayland users:** Clipboard and paste work via `wl-clipboard`. For keystroke injection without XWayland, install `ydotool` and ensure its daemon (`ydotoold`) is running.

---

## Usage

| Action | How |
|---|---|
| Start recording | `Ctrl+Shift+Space` |
| Stop recording and paste | `Ctrl+Shift+Space` again |
| Toggle via menu | Click the A logo → Toggle Recording |
| Quit | Click the A logo → Quit |

The Whisper model (`base`) is downloaded automatically on first use (~140 MB). Subsequent runs load it from cache.

---

## Run from source (no build required)

**macOS**
```bash
./run.sh
```
Grant Accessibility and Input Monitoring to **Terminal** (or whichever terminal app you use) instead of AIM Flow.

**Linux**
```bash
cd aim-flow-linux
./run_linux.sh
```

---

## Auto-start on login

**macOS** — **System Settings → General → Login Items → +** and add `/Applications/AIM Flow.app`.

**Linux** — Create a `.desktop` entry in `~/.config/autostart/`:

```ini
[Desktop Entry]
Type=Application
Name=AIM Flow
Exec=/path/to/aim-flow-linux/run_linux.sh
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
```

---

## Tech stack

- [openai-whisper](https://github.com/openai/whisper) — local speech recognition
- [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) — microphone capture
- [pynput](https://github.com/moses-palmer/pynput) — global hotkey and paste

**macOS only**
- [rumps](https://github.com/jaredks/rumps) — menu bar framework
- [pyobjc](https://pyobjc.readthedocs.io) — AppKit image rendering
- [PyInstaller](https://pyinstaller.org) — .app bundle packaging

**Linux only**
- [pystray](https://github.com/moses-palmer/pystray) — system tray icon
- [Pillow](https://python-pillow.org) — tray icon rendering

---

## Troubleshooting

### Hotkey does nothing

1. Go to **System Settings → Privacy & Security → Accessibility** and confirm AIM Flow is toggled ON.
2. Go to **System Settings → Privacy & Security → Input Monitoring** and confirm AIM Flow is toggled ON.
3. Quit and relaunch AIM Flow after changing permissions.
4. If you just reinstalled the app, macOS revokes permissions on replacement — re-grant them.

### Text is transcribed but not pasted

Same fix as above — Accessibility permission is required for the paste keystroke. Make sure it is enabled and that you restarted AIM Flow after enabling it.

### Multiple A icons appear in the menu bar

Only one instance of AIM Flow can run at a time. If you see duplicates, quit all of them (click each → Quit) and relaunch once. This is prevented automatically in newer versions.

### "ffmpeg not found" error

**macOS**
```bash
brew install ffmpeg
```

**Linux**
```bash
sudo apt-get install ffmpeg
```

### Microphone access denied

**System Settings → Privacy & Security → Microphone** → enable AIM Flow.

### Whisper model download is slow

The first run downloads the `base` Whisper model (~140 MB). This only happens once. Subsequent launches are instant.

### Permissions were granted but still not working after reinstall

macOS ties permissions to the specific app binary. Every time you replace the `.app`, you need to re-grant Accessibility and Input Monitoring. Go to System Settings, remove the old AIM Flow entry if present, relaunch the app, and re-add it.

### Python version issues

**macOS** — Use Python 3.12:
```bash
brew install python@3.12
```

**Linux** — Use Python 3.12:
```bash
sudo apt-get install python3.12 python3.12-venv python3.12-dev
```

---

## Project layout

```
aim-flow/                         macOS application
├── launch_aim_flow.py            Convenience launcher
├── install.sh                    One-command setup (Homebrew)
├── run.sh                        Run from source
├── requirements.txt              Runtime dependencies
├── requirements-build.txt        PyInstaller (build only)
├── AIM Flow.spec                 PyInstaller spec (icon + Info.plist)
├── status_logo.png               Menu bar icon source (18×18 PNG)
├── assets/
│   └── aim-flow.icns             Generated app bundle icon
├── scripts/
│   ├── build_app.sh              Build AIM Flow.app
│   └── create_icns.sh            Convert status_logo.png → .icns
└── src/aim_flow/
    ├── app.py                    Menu bar app (macOS)
    ├── audio.py                  Microphone recording
    ├── automation.py             Clipboard + paste
    ├── config.py                 Constants + resource path helper
    ├── hotkey.py                 Global hotkey listener
    ├── permissions.py            Accessibility check + guidance dialog
    ├── transcription.py          Whisper engine
    └── visuals.py                Menu bar icon rendering (macOS/AppKit)

aim-flow-linux/                   Linux application (linux branch)
├── launch_aim_flow_linux.py      Convenience launcher
├── install_linux.sh              One-command setup (apt-get)
├── run_linux.sh                  Run from source
├── requirements_linux.txt        Runtime dependencies
└── src/aim_flow/
    ├── app_linux.py              System tray app (pystray)
    ├── audio.py                  Microphone recording (shared)
    ├── automation.py             Clipboard + paste (X11/Wayland)
    ├── config.py                 Constants + resource path helper
    ├── hotkey.py                 Global hotkey listener (shared)
    ├── transcription.py          Whisper engine (shared)
    └── visuals_linux.py          Tray icon rendering (Pillow)
```

---

## License

MIT — see [LICENSE](LICENSE).

