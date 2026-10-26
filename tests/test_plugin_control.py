"""Plugin controls must work from an extracted archive without backend imports."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugin/hooks/runtime_control.py"


def load_control():
    spec = importlib.util.spec_from_file_location("plugin_control", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def control(tmp_path, monkeypatch):
    monkeypatch.setenv("EVOLVETRACE_CONTROL_DIR", str(tmp_path / "settings"))
    return load_control()


@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            value = {"schema_version": "activity-status/v1", "process_id": 123,
                     "started_at": "2026-01-01T00:00:00+00:00", "received_event_count": 0}
            body = json.dumps(value).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    instance = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{instance.server_port}"
    instance.shutdown()
    instance.server_close()
    thread.join()


def test_pause_persists_across_processes_and_resume_keeps_runtime(control, tmp_path, server):
    runtime = tmp_path / "runtime with spaces"
    runtime.mkdir()
    control.configure(runtime, server)
    control.set_enabled(False)
    env = {**os.environ}
    result = subprocess.run([sys.executable, str(SCRIPT), "status"], env=env,
                            text=True, capture_output=True, check=True)
    assert json.loads(result.stdout)["collection"] == "paused"
    control.set_enabled(True)
    assert control.status()["collection"] == "enabled"
    assert control.status()["service"] == "ready"
    assert control.read_settings()["runtime_root"] == str(runtime.resolve())


@pytest.mark.parametrize("url", ["https://127.0.0.1:8001", "http://example.test:8001",
                                    "http://127.0.0.1:8001/path", "http://user@127.0.0.1:8001"])
def test_auto_start_configuration_rejects_nonlocal_or_ambiguous_urls(control, tmp_path, url):
    with pytest.raises(ValueError):
        control.configure(tmp_path, url)
    assert not (tmp_path / "settings/control.json").exists()


def test_corrupt_preferences_pause_collection_instead_of_reenabling_it(control, tmp_path):
    directory = tmp_path / "settings"
    directory.mkdir()
    (directory / "control.json").write_text('{"enabled":', encoding="utf-8")
    assert control.read_settings()["enabled"] is False
    assert control.status()["collection"] == "configuration_error"


def test_existing_manual_install_still_collects_without_autostart(control):
    assert control.read_settings()["enabled"] is True
    assert control.ensure_service()["service"] == "manual"


def test_enabled_plugin_reuses_existing_compatible_service_without_runtime(control, tmp_path, server):
    control.configure(tmp_path / "missing checkout", server)
    assert control.ensure_service()["service"] == "ready"


def test_missing_runtime_is_actionable_and_does_not_disable_collection(control, tmp_path):
    control.configure(tmp_path / "missing checkout", "http://127.0.0.1:1")
    assert control.ensure_service()["service"] == "runtime_missing"
    assert control.status()["collection"] == "enabled"


def test_paused_plugin_does_not_attempt_service_start(control, tmp_path):
    control.configure(tmp_path / "missing checkout", "http://127.0.0.1:1")
    control.set_enabled(False)
    assert control.ensure_service()["service"] == "paused"


def test_concurrent_sessions_create_only_one_server(control, tmp_path, monkeypatch):
    control.configure(tmp_path, "http://127.0.0.1:1")
    # Starting an actual backend is covered by the isolated runtime smoke test.
    # This boundary substitutes process/network operations, retaining the real lock.
    running = []
    monkeypatch.setattr(control, "probe", lambda url, *args: {"process_id": 42} if running else None)

    def launch(settings, timeout):
        import time
        time.sleep(0.05)
        running.append(42)
        return {"service": "ready"}

    monkeypatch.setattr(control, "launch", launch)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: control.ensure_service(), range(4)))
    assert [item["service"] for item in results] == ["ready"] * 4
    assert running == [42]


def test_probe_refuses_redirects(control):
    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://example.test/private")
            self.end_headers()

        def log_message(self, *args):
            pass

    instance = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    thread = Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        assert control.probe(f"http://127.0.0.1:{instance.server_port}") is None
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join()


def test_paused_hook_keeps_safety_denial_without_sending_evidence(tmp_path, monkeypatch, capsys):
    sys.path.insert(0, str(SCRIPT.parent))
    import capture_event
    monkeypatch.setenv("EVOLVETRACE_CONTROL_DIR", str(tmp_path))
    (tmp_path / "control.json").write_text(json.dumps({"schema_version": "plugin-control/v1",
        "enabled": False, "runtime_root": None, "base_url": "http://127.0.0.1:8001"}))
    sent = []
    monkeypatch.setattr(capture_event, "capture", lambda payload: sent.append(payload))
    assert capture_event.process_payload({"session_id": "synthetic", "hook_event_name": "PreToolUse",
        "tool_name": "Bash", "tool_input": {"command": "mkfs.ext4 /dev/synthetic"}}) == 0
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert sent == []


def test_session_start_waits_for_service_before_capture(control, monkeypatch):
    sys.path.insert(0, str(SCRIPT.parent))
    import capture_event
    ordered = []
    monkeypatch.setattr(capture_event.runtime_control, "ensure_service", lambda: ordered.append("ready") or {"service": "ready"})
    monkeypatch.setattr(capture_event, "capture", lambda payload: ordered.append("sent"))
    capture_event.process_payload({"session_id": "synthetic", "hook_event_name": "SessionStart"})
    assert ordered == ["ready", "sent"]


@pytest.fixture
def synthetic_runtime(tmp_path):
    """A real isolated interpreter and synthetic server, no installed backend needed."""
    root = tmp_path / "source with spaces"
    backend = root / "backend"
    backend.mkdir(parents=True)
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(backend / "venv")],
                   check=True, capture_output=True, timeout=30)
    (backend / "main.py").write_text("# Synthetic runtime marker\n")
    (backend / "static").mkdir()
    (backend / "static/index.html").write_text("Synthetic workbench")
    yield root


def test_real_startup_timeout_stops_the_launched_interpreter(control, synthetic_runtime):
    backend = synthetic_runtime / "backend"
    # No network or Agent command: a deliberately slow import simulates startup.
    (backend / "uvicorn.py").write_text("import time\ntime.sleep(30)\n")
    control.configure(synthetic_runtime, "http://127.0.0.1:1")
    started = time.monotonic()
    assert control.ensure_service(timeout=0.3)["service"] == "start_timeout"
    assert time.monotonic() - started < 4
    # Timeout cleanup must release the runtime so it can be started again.
    (backend / "uvicorn.py").write_text("raise SystemExit(1)\n")
    assert control.ensure_service()["service"] == "start_failed"


@pytest.mark.skipif(os.name == "nt", reason="POSIX signal escalation")
def test_posix_timeout_kills_an_import_ignoring_sigterm(control, synthetic_runtime):
    backend = synthetic_runtime / "backend"
    marker = backend / "synthetic.pid"
    (backend / "uvicorn.py").write_text(
        "import os, signal, time\nfrom pathlib import Path\n"
        "signal.signal(signal.SIGTERM, lambda *args: None)\n"
        "Path('synthetic.pid').write_text(str(os.getpid()))\ntime.sleep(30)\n")
    control.configure(synthetic_runtime, "http://127.0.0.1:1")
    try:
        assert control.ensure_service(timeout=1)["service"] == "start_timeout"
        assert marker.is_file()
        with pytest.raises(ProcessLookupError):
            os.kill(int(marker.read_text()), 0)
    finally:
        if marker.is_file():
            import signal
            try:
                os.kill(int(marker.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_unbuilt_workbench_is_reported_before_creating_a_process(control, synthetic_runtime):
    (synthetic_runtime / "backend/static/index.html").unlink()
    control.configure(synthetic_runtime, "http://127.0.0.1:1")
    assert control.ensure_service()["service"] == "ui_missing"


def test_disabled_preference_is_not_reenabled_by_open(control, server):
    control.configure(Path.cwd(), server)
    control.set_enabled(False)
    result = subprocess.run([sys.executable, str(SCRIPT), "status"], capture_output=True,
                            text=True, check=True)
    assert json.loads(result.stdout)["collection"] == "paused"
    assert json.loads(result.stdout)["service"] == "ready"


def test_external_endpoint_never_triggers_automatic_launch(control, tmp_path, monkeypatch):
    control.configure(tmp_path, "http://127.0.0.1:1")
    monkeypatch.setenv("EVOLVETRACE_API_URL", "http://127.0.0.1:9999/api/audit/events")
    assert control.ensure_service()["service"] == "external_endpoint"


def test_session_start_does_not_post_after_pause_wins_startup_lock(control, monkeypatch):
    sys.path.insert(0, str(SCRIPT.parent))
    import capture_event
    sent = []

    def paused_during_startup():
        control.set_enabled(False)
        return {"service": "paused"}

    monkeypatch.setattr(capture_event.runtime_control, "ensure_service", paused_during_startup)
    monkeypatch.setattr(capture_event, "capture", lambda payload: sent.append(payload))
    capture_event.process_payload({"session_id": "synthetic", "hook_event_name": "SessionStart"})
    assert sent == []


def test_probe_has_whole_operation_deadline_even_for_slow_drip(control):
    class Slow(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            try:
                for _ in range(30):
                    self.wfile.write(b" ")
                    self.wfile.flush()
                    time.sleep(0.1)
            except OSError:
                pass

        def log_message(self, *args):
            pass

    instance = ThreadingHTTPServer(("127.0.0.1", 0), Slow)
    thread = Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        started = time.monotonic()
        assert control.probe(f"http://127.0.0.1:{instance.server_port}") is None
        assert time.monotonic() - started < 2
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join()
