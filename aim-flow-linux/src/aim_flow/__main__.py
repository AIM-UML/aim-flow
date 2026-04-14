"""CLI entry point for AIM Flow (Linux).

Enforces a single-instance lock using fcntl (POSIX), configures logging,
then delegates to AIMFlowLinuxApp.
"""

from __future__ import annotations

import fcntl
import logging
import os
import sys
import tempfile

from .app_linux import AIMFlowLinuxApp

_LOCK_FILE = os.path.join(tempfile.gettempdir(), "aim-flow-linux.lock")
_lock_handle = None  # kept alive so the lock is held for the process lifetime


def _acquire_single_instance_lock() -> bool:
    """Return True if this is the only running instance, False otherwise."""
    global _lock_handle
    try:
        _lock_handle = open(_LOCK_FILE, "w")
        fcntl.flock(_lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        if _lock_handle:
            _lock_handle.close()
            _lock_handle = None
        return False


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logging.getLogger("whisper").setLevel(logging.WARNING)
    logging.getLogger("numba").setLevel(logging.WARNING)
    logging.getLogger("filelock").setLevel(logging.WARNING)


def main() -> int:
    if not _acquire_single_instance_lock():
        # Silently exit — another instance is already running in the tray.
        return 0

    _configure_logging()
    app = AIMFlowLinuxApp()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
