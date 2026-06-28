# Media Manager

Automatically pauses your media (audiobook, music, YouTube) when someone speaks in your voice chat, then resumes it after they go quiet.

![Status: Windows only](https://img.shields.io/badge/platform-Windows-blue)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)

## Features

- Pauses media when others speak in Discord, TeamSpeak 3, or Mumble
- Optionally pauses when **you** speak too
- Resumes automatically after configurable silence (1–30 seconds)
- Targets the correct media session — won't interfere if you have YouTube open alongside your audiobook
- Mic device selector — choose your headset instead of relying on auto-detect
- Runs quietly in the system tray

## Download

Grab the latest `.exe` from the [Releases](../../releases) page — no Python required.

## Running from source

**Requirements:** Python 3.11+, Windows

```bash
pip install -r requirements.txt
python main.py
```

> **Note:** `winrt` packages are installed separately if needed:
> ```bash
> pip install winrt-Windows.Media.Control winrt-Windows.Foundation.Collections
> ```

## Settings

Open the tray icon → **Settings**

| Setting | Description |
|---|---|
| Resume after silence | How long to wait after everyone goes quiet before resuming (1–30s) |
| Trigger sensitivity | How loud others need to be to trigger a pause |
| Mic sensitivity | How loud you need to be to trigger a pause (if "Pause when I speak" is on) |
| Voice app | Which app to monitor — Discord, TeamSpeak 3, or Mumble |
| Microphone | Choose your mic instead of relying on auto-detect |
| Active | Enable or disable the app without closing it |
| Pause when I speak | Also pause when your own mic is active |

## Building the .exe

```bash
build.bat
```

Output is in `dist/MediaManager.exe`.

## Platform support

Windows only. The app relies on Windows-specific APIs (WASAPI via pycaw, Windows Media Transport Controls via winrt) for audio session detection and media control.

Browser-based voice calls (Google Meet, Teams, Zoom) are not supported — their audio is indistinguishable from other browser tabs.

## License

MIT
