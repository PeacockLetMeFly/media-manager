import sys
import os
import winreg

_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "MediaManager"


def _exe_path() -> str:
    if getattr(sys, 'frozen', False):
        return sys.executable
    return os.path.abspath(os.path.join(os.path.dirname(__file__), 'main.py'))


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY) as key:
            winreg.QueryValueEx(key, _APP_NAME)
            return True
    except FileNotFoundError:
        return False


def enable():
    path = _exe_path()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, access=winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, f'"{path}"')


def disable():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, access=winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, _APP_NAME)
    except FileNotFoundError:
        pass
