"""Cross-process serialization for workspace mutations."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import time
from typing import Iterator, TextIO

from .config import ConfigError


class WorkspaceLockTimeout(ConfigError):
    """Raised when another process keeps the workspace write lock."""


def _try_lock(stream: TextIO) -> bool:
    if os.name == "nt":
        import msvcrt

        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    import fcntl

    try:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


def _unlock(stream: TextIO) -> None:
    if os.name == "nt":
        import msvcrt

        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def workspace_write_lock(
    root: Path,
    *,
    timeout: float = 10.0,
    poll_interval: float = 0.05,
) -> Iterator[None]:
    """Allow only one mutating aictx process in a workspace at a time."""

    lock_path = root.resolve() / ".ai" / "write.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as stream:
        if stream.tell() == 0:
            stream.write("0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while not _try_lock(stream):
            if time.monotonic() >= deadline:
                raise WorkspaceLockTimeout(
                    f"another aictx writer holds {lock_path}; retry after it finishes"
                )
            time.sleep(poll_interval)
        try:
            yield
        finally:
            _unlock(stream)

