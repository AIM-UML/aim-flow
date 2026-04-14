# AIM Flow

Free, open-source, fully local speech-to-text for macOS — no cloud, no API keys, no subscription.

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

- macOS 12 or later
- Python 3.11 or 3.12 (3.12 recommended)
- [Homebrew](https://brew.sh)

---

## Installation

### Step 1 — Clone and install

```bash
git clone https://github.com/jangel19/aim-flow.git
cd aim-flow
./install.sh
```

This installs `ffmpeg` and `portaudio` via Homebrew, creates a Python virtual environment, installs all dependencies, and generates the app icon.

### Step 2 — Build the app

```bash
./scripts/build_app.sh
```

This creates `dist/AIM Flow.app`.

### Step 3 — Move to Applications

```bash
cp -r "dist/AIM Flow.app" /Applications/
```

Or drag `dist/AIM Flow.app` to your `/Applications` folder in Finder.

### Step 4 — Launch AIM Flow

Open `/Applications/AIM Flow.app`. The AIMS "A" logo will appear in your menu bar.

### Step 5 — Grant permissions (one-time setup)

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

```bash
./run.sh
```

Grant Accessibility and Input Monitoring to **Terminal** (or whichever terminal app you use) instead of AIM Flow.

---

## Auto-start on login

**System Settings → General → Login Items → +** and add `/Applications/AIM Flow.app`.

---

## Tech stack

- [rumps](https://github.com/jaredks/rumps) — macOS menu bar framework
- [openai-whisper](https://github.com/openai/whisper) — local speech recognition
- [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) — microphone capture
- [pynput](https://github.com/moses-palmer/pynput) — global hotkey and paste
- [pyobjc](https://pyobjc.readthedocs.io) — AppKit image rendering
- [PyInstaller](https://pyinstaller.org) — .app bundle packaging

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

```bash
brew install ffmpeg
```

### Microphone access denied

**System Settings → Privacy & Security → Microphone** → enable AIM Flow.

### Whisper model download is slow

The first run downloads the `base` Whisper model (~140 MB). This only happens once. Subsequent launches are instant.

### Permissions were granted but still not working after reinstall

macOS ties permissions to the specific app binary. Every time you replace the `.app`, you need to re-grant Accessibility and Input Monitoring. Go to System Settings, remove the old AIM Flow entry if present, relaunch the app, and re-add it.

### Python version issues

Use Python 3.12:

```bash
brew install python@3.12
```

---

## Project layout

```
aim-flow/
├── launch_aim_flow.py       Convenience launcher
├── install.sh               One-command setup
├── run.sh                   Run from source
├── requirements.txt         Runtime dependencies
├── requirements-build.txt   PyInstaller (build only)
├── AIM Flow.spec            PyInstaller spec (icon + Info.plist)
├── status_logo.png          Menu bar icon source (18×18 PNG)
├── assets/
│   └── aim-flow.icns        Generated app bundle icon
├── scripts/
│   ├── build_app.sh         Build AIM Flow.app
│   └── create_icns.sh       Convert status_logo.png → .icns
└── src/aim_flow/
    ├── app.py               Menu bar app
    ├── audio.py             Microphone recording
    ├── automation.py        Clipboard + paste
    ├── config.py            Constants + resource path helper
    ├── hotkey.py            Global hotkey listener
    ├── permissions.py       Accessibility check + guidance dialog
    ├── transcription.py     Whisper engine
    └── visuals.py           Menu bar icon rendering
```

---

## License

MIT — see [LICENSE](LICENSE).

