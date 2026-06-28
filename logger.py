import logging
import os
import sys
from logging.handlers import RotatingFileHandler

def _log_path():
    base = os.path.dirname(sys.executable if getattr(sys, 'frozen', False)
                           else os.path.abspath(__file__))
    return os.path.join(base, 'media_manager.log')

def setup():
    log = logging.getLogger('mm')
    log.setLevel(logging.DEBUG)

    fmt = logging.Formatter('%(asctime)s  %(levelname)-7s  %(message)s',
                            datefmt='%H:%M:%S')

    # Rotating file — max 1 MB, keep 2 backups
    fh = RotatingFileHandler(_log_path(), maxBytes=1_000_000, backupCount=2,
                             encoding='utf-8')
    fh.setFormatter(fmt)
    log.addHandler(fh)

    # Also print to terminal when running as a script
    if not getattr(sys, 'frozen', False):
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        log.addHandler(ch)

    return log

log = setup()
