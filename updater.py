import threading
import urllib.request
import json
from version import __version__
from logger import log

RELEASES_URL = "https://api.github.com/repos/PeacockLetMeFly/media-manager/releases/latest"


def _parse_version(tag: str) -> tuple:
    return tuple(int(x) for x in tag.lstrip('v').split('.') if x.isdigit())


def check_for_update(on_update_available):
    """Check GitHub for a newer release in a background thread.
    Calls on_update_available(version, url) if one is found."""
    def _check():
        try:
            req = urllib.request.Request(RELEASES_URL,
                                         headers={'User-Agent': 'media-manager-updater'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            latest_tag = data.get('tag_name', '')
            latest_url = data.get('html_url', '')
            if not latest_tag:
                return
            if _parse_version(latest_tag) > _parse_version(__version__):
                log.info(f'Update available: {latest_tag}')
                on_update_available(latest_tag, latest_url)
            else:
                log.info(f'App is up to date ({__version__})')
        except Exception as e:
            log.debug(f'Update check failed: {e}')

    threading.Thread(target=_check, daemon=True).start()
