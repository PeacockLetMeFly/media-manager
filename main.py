import config as cfg_module
from audio_monitor import AudioMonitor
from media_key import press_play_pause, media_is_playing, mic_is_active
from tray_app import TrayApp
from logger import log

# True only when WE triggered the pause — so we know to resume later.
_we_paused = [False]


def main():
    config = cfg_module.load()
    tray: list[TrayApp] = [None]

    def on_speaking_start():
        if _we_paused[0]:
            # Already paused by us — someone is speaking again, just stay paused
            log.info('Speaking again — resume cancelled, staying paused')
        else:
            playing = media_is_playing()
            log.debug(f'Speaking started — media_is_playing={playing}')
            if playing:
                _we_paused[0] = True
                log.info('Media was playing — pressing pause')
                press_play_pause()
            else:
                log.info('Media was already paused manually — not interfering')

        if tray[0]:
            tray[0].set_status('paused')

    def on_speaking_stop():
        if _we_paused[0]:
            _we_paused[0] = False
            log.info('Pressing play to resume media')
            press_play_pause()
        else:
            log.info('Resume skipped — we did not pause the media')

        if tray[0]:
            tray[0].set_status('listening')

    def can_resume() -> bool:
        """Delay resumption while the user is speaking into their mic."""
        threshold = config.get('threshold', 0.01)
        return not mic_is_active(threshold)

    def on_discord_found():
        if tray[0]:
            tray[0].set_status('listening')

    def on_discord_lost():
        _we_paused[0] = False
        if tray[0]:
            tray[0].set_status('disconnected')

    monitor = AudioMonitor(
        on_speaking_start=on_speaking_start,
        on_speaking_stop=on_speaking_stop,
        on_discord_found=on_discord_found,
        on_discord_lost=on_discord_lost,
        config=config,
        can_resume=can_resume,
    )

    tray[0] = TrayApp(config=config, save_config=cfg_module.save, monitor=monitor)

    log.info('=== Media Manager started ===')
    monitor.start()
    tray[0].run()
    log.info('=== Media Manager stopped ===')


if __name__ == '__main__':
    main()
