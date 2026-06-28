import threading
import pystray
from icon_gen import make_icon
from settings_window import SettingsWindow


class TrayApp:
    def __init__(self, config: dict, save_config, monitor):
        self.config      = config
        self.save_config = save_config
        self.monitor     = monitor
        self._status     = 'disconnected'
        self._settings: SettingsWindow | None = None
        self._icon: pystray.Icon | None       = None

    # ── status ────────────────────────────────────────────────────────────────

    def set_status(self, status: str):
        self._status = status
        if self._icon:
            self._icon.icon  = make_icon(status)
            self._icon.title = f"Media Manager  •  {status.capitalize()}"
        if self._settings:
            self._settings.set_status(status)

    # ── menu actions ─────────────────────────────────────────────────────────

    def _open_settings(self, icon=None, item=None):
        if self._settings and self._settings.root:
            try:
                self._settings.root.after(0, lambda: (
                    self._settings.root.lift(),
                    self._settings.root.focus_force(),
                ))
                return
            except Exception:
                pass

        def _run():
            self._settings = SettingsWindow(self.config, self.save_config, self._status)
            self._settings.open()

        threading.Thread(target=_run, daemon=True).start()

    def _toggle_enabled(self, icon, item):
        self.config['enabled'] = not self.config.get('enabled', True)
        self.save_config(self.config)

    def _quit(self, icon, item):
        self.monitor.stop()
        icon.stop()

    # ── run ───────────────────────────────────────────────────────────────────

    def run(self):
        self._icon = pystray.Icon(
            name='media_manager',
            icon=make_icon('disconnected'),
            title='Media Manager',
            menu=pystray.Menu(
                pystray.MenuItem('Settings', self._open_settings, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    'Enabled',
                    self._toggle_enabled,
                    checked=lambda item: self.config.get('enabled', True),
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('Quit', self._quit),
            ),
        )
        self._icon.run()
