"""One writer at a time for cabinet mutations."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from . import paths


@contextmanager
def writer_lock(lock_file: Path | None = None):
    lock_file = lock_file or paths.lock_path()
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_file, "a+")
    try:
        if os.name == "nt":
            yield fh
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield fh
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    finally:
        fh.close()
