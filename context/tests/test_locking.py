import multiprocessing
from pathlib import Path

import pytest

from ai_context_kit.locking import WorkspaceLockTimeout, workspace_write_lock


def _hold_lock(root: str, ready, release) -> None:
    with workspace_write_lock(Path(root), timeout=1):
        ready.put(True)
        release.get(timeout=5)


def test_second_writer_times_out_while_workspace_lock_is_held(tmp_path: Path) -> None:
    with workspace_write_lock(tmp_path, timeout=0.1):
        with pytest.raises(WorkspaceLockTimeout, match="another aictx writer"):
            with workspace_write_lock(tmp_path, timeout=0.05):
                pytest.fail("a second writer entered the critical section")

    with workspace_write_lock(tmp_path, timeout=0.05):
        pass


def test_lock_coordinates_separate_processes(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    ready = context.Queue()
    release = context.Queue()
    process = context.Process(target=_hold_lock, args=(str(tmp_path), ready, release))
    process.start()
    try:
        assert ready.get(timeout=5) is True
        with pytest.raises(WorkspaceLockTimeout):
            with workspace_write_lock(tmp_path, timeout=0.05):
                pytest.fail("parent entered while child held the lock")
    finally:
        release.put(True)
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
    assert process.exitcode == 0
