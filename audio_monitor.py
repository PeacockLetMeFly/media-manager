import threading
import time
import psutil
import numpy as np
import sounddevice as sd
from logger import log

POLL_INTERVAL = 0.15          # seconds between audio level checks
DISCORD_CHECK_INTERVAL = 3    # seconds between voice app process checks
SILENCE_CONFIRM = 1.5         # quiet for this long before starting the resume countdown
MIC_RELEASE_HOLD = 1.0        # mic must drop below threshold for this long before considered quiet

# Supported voice apps — key is display name, value is lowercase process name substring
VOICE_APPS = {
    'Discord':     'discord',
    'TeamSpeak 3': 'ts3client',
    'Mumble':      'mumble',
}

# ── microphone level monitor ───────────────────────────────────────────────────

_device_levels = {}
_device_levels_lock = threading.Lock()
_mic_streams = {}
_active_device_id = None
_streams_lock = threading.Lock()   # guards open/close operations


def get_input_devices():
    """Return list of (index, name) for all available input devices."""
    devices = []
    for i, d in enumerate(sd.query_devices()):
        if d['max_input_channels'] > 0:
            devices.append((i, d['name']))
    return devices


def _open_stream(device_id: int):
    def _cb(indata, frames, time_info, status, did=device_id):
        with _device_levels_lock:
            _device_levels[did] = float(np.abs(indata).max())
    try:
        stream = sd.InputStream(device=device_id, channels=1, samplerate=16000,
                                blocksize=512, dtype='float32', callback=_cb)
        stream.start()
        return stream
    except Exception:
        return None


def _close_all_streams():
    global _active_device_id
    with _streams_lock:
        for stream in list(_mic_streams.values()):
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        _mic_streams.clear()
        with _device_levels_lock:
            _device_levels.clear()
        _active_device_id = None


def set_mic_device(device_id: int | None):
    """Switch to a specific input device (or None to return to auto-detect)."""
    global _active_device_id
    _close_all_streams()
    with _streams_lock:
        if device_id is not None:
            stream = _open_stream(device_id)
            if stream:
                _mic_streams[device_id] = stream
                _active_device_id = device_id
                name = sd.query_devices(device_id)['name']
                log.info(f'Mic switched to [{device_id}] {name}')
            else:
                log.warning(f'Could not open mic device [{device_id}], falling back to auto-detect')
                _start_mic_streams()
        else:
            _start_mic_streams()


def _start_mic_streams(device_id: int | None = None):
    """Open stream(s). If device_id given, open only that device; else open all."""
    global _active_device_id
    if device_id is not None:
        stream = _open_stream(device_id)
        if stream:
            _mic_streams[device_id] = stream
            _active_device_id = device_id
            name = sd.query_devices(device_id)['name']
            log.info(f'Mic locked to configured device [{device_id}] {name}')
        else:
            log.warning(f'Configured mic device [{device_id}] unavailable — falling back to auto-detect')
            _start_mic_streams(None)
        return

    for i, device in enumerate(sd.query_devices()):
        if device['max_input_channels'] < 1:
            continue
        stream = _open_stream(i)
        if stream:
            _mic_streams[i] = stream
            log.debug(f'Mic stream open: [{i}] {device["name"]}')

    log.info(f'Mic monitoring started across {len(_mic_streams)} input device(s)')


def _mic_peak():
    """Return peak from the active device, or auto-lock to the loudest device."""
    global _active_device_id

    with _device_levels_lock:
        if not _device_levels:
            return 0.0
        if _active_device_id is not None:
            return _device_levels.get(_active_device_id, 0.0)
        peak_by_device = dict(_device_levels)

    best_id = max(peak_by_device, key=peak_by_device.get)
    if peak_by_device[best_id] > 0.05:
        _active_device_id = best_id
        name = sd.query_devices(best_id)['name']
        log.info(f'Mic auto-locked to device [{best_id}] {name}')
        with _streams_lock:
            for dev_id, stream in list(_mic_streams.items()):
                if dev_id != best_id:
                    try:
                        stream.stop()
                        stream.close()
                    except Exception:
                        pass
                    del _mic_streams[dev_id]

    return peak_by_device.get(best_id, 0.0)


# ── audio helpers ──────────────────────────────────────────────────────────────

def _voice_app_running(process_match: str) -> bool:
    try:
        return any(process_match in p.name().lower() for p in psutil.process_iter(['name']))
    except Exception:
        return False


_sessions_logged = False

def _voice_app_peak(process_match: str) -> float:
    global _sessions_logged
    try:
        from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
        sessions = list(AudioUtilities.GetAllSessions())
        if not _sessions_logged:
            names = [s.Process.name() if s.Process else '<system>' for s in sessions]
            log.info(f'Audio sessions: {names}')
            _sessions_logged = True
        peak = 0.0
        for session in sessions:
            if session.Process and process_match in session.Process.name().lower():
                meter = session._ctl.QueryInterface(IAudioMeterInformation)
                peak = max(peak, meter.GetPeakValue())
        if peak > 0:
            return peak
    except Exception as e:
        log.debug(f'_voice_app_peak error: {e}')
    return 0.0


class AudioMonitor:
    """
    Four-phase state machine:

        idle       – nobody speaking, media plays freely
        speaking   – at least one source active; on_speaking_start() has been called
        confirming – all quiet; 1.5s silence-confirm timer running
        counting   – silence confirmed; N-second countdown running

    ALL mic/audio checks happen inside _tick(), which runs in the single poll thread.
    Timer callbacks only set a flag and return — they never call audio APIs, so there
    is no COM threading issue.
    """

    def __init__(self, on_speaking_start, on_speaking_stop,
                 on_discord_found, on_discord_lost, config, can_resume=None):
        self.on_speaking_start = on_speaking_start
        self.on_speaking_stop = on_speaking_stop
        self.on_discord_found = on_discord_found
        self.on_discord_lost = on_discord_lost
        self.config = config
        self.can_resume = can_resume   # kept for API compat; mic checked inline now

        self._lock = threading.Lock()
        self._running = False
        self._thread = None

        self._discord_present = False
        self._last_discord_check = 0

        # Per-source speaking flags
        self._discord_active = False   # Discord output above threshold
        self._user_active = False      # mic recently active (within MIC_RELEASE_HOLD)
        self._mic_last_active = None   # last time mic was above threshold

        # State
        self._phase = 'idle'           # 'idle' | 'speaking' | 'confirming' | 'counting'
        self._timer = None
        self._ready_to_resume = False  # set by countdown timer; cleared by _tick

    # ── lifecycle ──────────────────────────────────────────────────────────────

    def start(self):
        _start_mic_streams(self.config.get('mic_device_id'))
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        with self._lock:
            self._cancel_timer()

    # ── poll loop ──────────────────────────────────────────────────────────────

    def _loop(self):
        while self._running:
            now = time.monotonic()

            if now - self._last_discord_check >= DISCORD_CHECK_INTERVAL:
                self._last_discord_check = now
                app_name = self.config.get('voice_app', 'Discord')
                process_match = VOICE_APPS.get(app_name, 'discord')
                running = _voice_app_running(process_match)
                if running != self._discord_present:
                    self._discord_present = running
                    if running:
                        log.info(f'{app_name} detected — monitoring started')
                        self.on_discord_found()
                    else:
                        log.warning(f'{app_name} lost — resetting state')
                        with self._lock:
                            self._hard_reset()
                        self.on_discord_lost()

            if self.config.get('enabled', True) and self._discord_present:
                threshold = self.config.get('threshold', 0.01)
                app_name = self.config.get('voice_app', 'Discord')
                process_match = VOICE_APPS.get(app_name, 'discord')
                self._tick(threshold, process_match)

            time.sleep(POLL_INTERVAL)

    # ── tick: read audio, drive state machine ──────────────────────────────────

    def _tick(self, threshold, process_match: str = 'discord'):
        # _voice_app_peak() uses GetAllSessions() which initialises COM for this thread.
        # _mic_peak() must be called after, in the same thread — COM is then ready.
        discord_peak = _voice_app_peak(process_match)
        mic_peak = _mic_peak()
        mic_threshold = self.config.get('mic_threshold', 0.05)
        mic_active = mic_peak > mic_threshold

        with self._lock:
            # ── Discord output source ──────────────────────────────────────────
            discord_was = self._discord_active
            self._discord_active = discord_peak > threshold
            if self._discord_active and not discord_was:
                log.info(f'Others speaking  (peak={discord_peak:.4f})')

            # ── Mic source ────────────────────────────────────────────────────────
            # "recently active" = above threshold within the last MIC_RELEASE_HOLD seconds.
            # The hold bridges natural word gaps so brief dips don't break detection.
            now = time.monotonic()
            if mic_active:
                self._mic_last_active = now

            mic_recently_active = (
                self._mic_last_active is not None
                and (now - self._mic_last_active) < MIC_RELEASE_HOLD
            )

            user_was = self._user_active
            if mic_recently_active != self._user_active:
                self._user_active = mic_recently_active
                if mic_recently_active:
                    log.info(f'User mic active  (peak={mic_peak:.4f})')
                else:
                    log.debug('User mic went quiet')

            # "anyone speaking" — user mic only triggers pause if pause_on_self is enabled
            pause_on_self = self.config.get('pause_on_self', False)
            anyone = self._discord_active or (pause_on_self and self._user_active)

            # ── state machine ──────────────────────────────────────────────────

            if self._phase == 'idle':
                if anyone:
                    self._enter_speaking()

            elif self._phase == 'speaking':
                if not anyone:
                    self._enter_confirming()

            elif self._phase == 'confirming':
                if anyone:
                    log.debug('Speaking resumed during silence confirm — staying in speaking')
                    self._cancel_timer()
                    self._phase = 'speaking'
                    threading.Thread(target=self.on_speaking_start, daemon=True).start()

            elif self._phase == 'counting':
                if self._discord_active:
                    # Others started talking during countdown — cancel and go back
                    log.info('Others speaking during countdown — cancelling resume')
                    self._cancel_timer()
                    self._ready_to_resume = False
                    self._phase = 'speaking'
                    threading.Thread(target=self.on_speaking_start, daemon=True).start()
                elif self._ready_to_resume:
                    # Countdown elapsed. Resume only if user's mic has also been quiet.
                    if mic_recently_active:
                        log.debug(f'Resume held — user mic active (peak={mic_peak:.4f})')
                    else:
                        log.info('Resuming media')
                        self._ready_to_resume = False
                        self._phase = 'idle'
                        threading.Thread(target=self.on_speaking_stop, daemon=True).start()

    # ── phase helpers (called under self._lock) ────────────────────────────────

    def _enter_speaking(self):
        self._cancel_timer()
        self._ready_to_resume = False
        self._phase = 'speaking'
        threading.Thread(target=self.on_speaking_start, daemon=True).start()

    def _enter_confirming(self):
        self._phase = 'confirming'
        log.debug(f'All quiet — starting silence confirm ({SILENCE_CONFIRM}s)')
        self._timer = threading.Timer(SILENCE_CONFIRM, self._on_silence_confirmed)
        self._timer.daemon = True
        self._timer.start()

    def _on_silence_confirmed(self):
        """Timer callback — only sets phase and starts next timer, no audio calls."""
        delay = self.config.get('resume_delay', 10)
        with self._lock:
            if self._phase != 'confirming':
                return
            log.info(f'Silence confirmed — starting resume countdown ({delay}s)')
            self._phase = 'counting'
            self._timer = threading.Timer(delay, self._on_countdown_elapsed)
            self._timer.daemon = True
            self._timer.start()

    def _on_countdown_elapsed(self):
        """Timer callback — only sets the ready flag; _tick does the actual resume."""
        with self._lock:
            if self._phase != 'counting':
                return
            log.debug('Countdown elapsed — checking mic before resume')
            self._timer = None
            self._ready_to_resume = True

    def _cancel_timer(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _hard_reset(self):
        self._cancel_timer()
        self._phase = 'idle'
        self._discord_active = False
        self._user_active = False
        self._mic_last_active = None
        self._ready_to_resume = False
