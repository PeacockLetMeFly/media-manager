import json
import os
import sys

DEFAULTS = {
    'resume_delay': 10,
    'enabled': True,
    'threshold': 0.01,
    'mic_threshold': 0.05,
    'pause_on_self': True,
    'mic_device_id': None,
    'voice_app': 'Discord',
}

def _path():
    base = os.path.dirname(sys.executable if getattr(sys, 'frozen', False)
                           else os.path.abspath(__file__))
    return os.path.join(base, 'config.json')

def load():
    try:
        with open(_path()) as f:
            return {**DEFAULTS, **json.load(f)}
    except Exception:
        return dict(DEFAULTS)

def save(cfg):
    try:
        with open(_path(), 'w') as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass
