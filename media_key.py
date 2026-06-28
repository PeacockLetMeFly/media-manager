import asyncio
import threading
from pynput.keyboard import Key, Controller

_kb = Controller()

# ── SMTC helpers ──────────────────────────────────────────────────────────────

def _run_async(coro):
    """Run an async coroutine synchronously (creates a new event loop on a thread)."""
    result = [None]
    exc = [None]
    def _worker():
        loop = asyncio.new_event_loop()
        try:
            result[0] = loop.run_until_complete(coro)
        except Exception as e:
            exc[0] = e
        finally:
            loop.close()
    t = threading.Thread(target=_worker)
    t.start()
    t.join(timeout=3)
    if exc[0]:
        raise exc[0]
    return result[0]


def _get_sessions():
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as Mgr,
    )
    async def _inner():
        mgr = await Mgr.request_async()
        return mgr.get_sessions()
    return _run_async(_inner())


def _is_discord(source_id: str) -> bool:
    return 'discord' in source_id.lower()


# ── public API ────────────────────────────────────────────────────────────────

def press_play_pause():
    """Toggle play/pause on the non-Discord session that is currently Playing.
    Falls back to the OS media key if SMTC is unavailable or no session found."""
    try:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status,
        )
        sessions = _get_sessions()
        for s in sessions:
            if _is_discord(s.source_app_user_model_id):
                continue
            info = s.get_playback_info()
            if info and info.playback_status == Status.PLAYING:
                async def _toggle(session=s):
                    await session.try_toggle_play_pause_async()
                _run_async(_toggle())
                return
        # No Playing session found — try toggling any non-Discord session
        for s in sessions:
            if not _is_discord(s.source_app_user_model_id):
                async def _toggle(session=s):
                    await session.try_toggle_play_pause_async()
                _run_async(_toggle())
                return
    except Exception:
        pass
    # Final fallback: OS media key
    _kb.press(Key.media_play_pause)
    _kb.release(Key.media_play_pause)


def media_is_playing() -> bool:
    """True if any non-Discord media session reports PlaybackStatus == PLAYING."""
    try:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status,
        )
        sessions = _get_sessions()
        for s in sessions:
            if _is_discord(s.source_app_user_model_id):
                continue
            info = s.get_playback_info()
            if info and info.playback_status == Status.PLAYING:
                return True
        return False
    except Exception:
        pass
    # Fallback: pycaw audio peak
    try:
        from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
        for session in AudioUtilities.GetAllSessions():
            if not session.Process:
                continue
            if 'discord' in session.Process.name().lower():
                continue
            meter = session._ctl.QueryInterface(IAudioMeterInformation)
            if meter.GetPeakValue() > 0.001:
                return True
    except Exception:
        pass
    return False


def mic_is_active(threshold: float = 0.01) -> bool:
    """True if the default microphone is picking up audio (user is speaking)."""
    try:
        from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
        from comtypes import CLSCTX_ALL
        enumerator = AudioUtilities.GetDeviceEnumerator()
        device = enumerator.GetDefaultAudioEndpoint(1, 1)  # eCapture, eMultimedia
        meter = device.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
        peak = meter.QueryInterface(IAudioMeterInformation).GetPeakValue()
        return peak > threshold
    except Exception:
        return False
