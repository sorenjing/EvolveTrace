"""Persistent collection preference and bounded local service startup (stdlib only)."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8001"


def control_dir() -> Path:
    # Stable across plugin updates and shared by Hook and explicit controls.
    return Path(os.getenv("EVOLVETRACE_CONTROL_DIR", str(Path.home() / ".evolvetrace")))


def validate_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or
            parsed.username or parsed.password or parsed.path not in {"", "/"} or
            parsed.query or parsed.fragment):
        raise ValueError("Use an http://127.0.0.1:<port> local service address.")
    port = parsed.port or 80
    if not 1 <= port <= 65535:
        raise ValueError("Invalid service port.")
    return f"http://127.0.0.1:{port}"


def read_settings() -> dict:
    defaults = {"schema_version": "plugin-control/v1", "enabled": True,
                "runtime_root": None, "base_url": DEFAULT_URL}
    try:
        value = json.loads((control_dir() / "control.json").read_text(encoding="utf-8"))
        if (not isinstance(value, dict) or value.get("schema_version") != "plugin-control/v1" or
                type(value.get("enabled")) is not bool or
                not (value.get("runtime_root") is None or
                     isinstance(value["runtime_root"], str) and Path(value["runtime_root"]).is_absolute())):
            raise ValueError("Invalid settings")
        return {**defaults, **value, "base_url": validate_url(value["base_url"])}
    except FileNotFoundError:
        return defaults
    except (OSError, ValueError, KeyError, TypeError):
        # A broken preference must never silently undo a user's pause.
        return {**defaults, "enabled": False, "configuration_error": True}


@contextmanager
def control_lock(timeout: float = 10):
    directory = control_dir()
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "control.lock").open("a+b") as handle:
        handle.write(b"\0")
        handle.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Another EvolveTrace control operation is in progress.")
                time.sleep(0.05)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def write_settings(value: dict) -> None:
    directory = control_dir()
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as file:
        temporary = Path(file.name)
        json.dump(value, file)
    try:
        os.replace(temporary, directory / "control.json")
    finally:
        temporary.unlink(missing_ok=True)


def configure(runtime: Path, url: str = DEFAULT_URL) -> None:
    value = {"schema_version": "plugin-control/v1", "enabled": True,
             "runtime_root": str(runtime.resolve()), "base_url": validate_url(url)}
    with control_lock():
        write_settings(value)


def set_enabled(enabled: bool) -> None:
    with control_lock():
        value = read_settings()
        if value.get("configuration_error"):
            raise ValueError("Preferences are unreadable. Configure the runtime again.")
        write_settings({**value, "enabled": enabled})


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _probe(url: str) -> dict | None:
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(validate_url(url) + "/api/activity/status", timeout=0.5) as response:
            body = response.read(65537)
        if len(body) > 65536:
            return None
        value = json.loads(body)
        if (isinstance(value, dict) and value.get("schema_version") == "activity-status/v1" and
                type(value.get("process_id")) is int and value["process_id"] > 0 and
                isinstance(value.get("started_at"), str)):
            return value
    except (OSError, ValueError, TypeError):
        pass
    return None


def probe(url: str, timeout: float = 0.9) -> dict | None:
    # Socket timeouts alone do not bound a slow-drip response or its headers.
    # A disposable stdlib worker gives the whole probe a wall-clock deadline.
    if timeout <= 0:
        return None
    try:
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--probe", validate_url(url)],
                                capture_output=True, text=True, timeout=timeout, **options)
        value = json.loads(result.stdout)
        return value if result.returncode == 0 and isinstance(value, dict) else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def status() -> dict:
    settings = read_settings()
    observed = probe(settings["base_url"])
    return {"schema_version": "plugin-control-status/v1",
            "collection": "configuration_error" if settings.get("configuration_error") else
                          "enabled" if settings["enabled"] else "paused",
            "auto_start": bool(settings["runtime_root"] and settings["enabled"]),
            "service": "ready" if observed else "unavailable",
            "base_url": settings["base_url"],
            "process_id": observed["process_id"] if observed else None,
            "received_event_count": observed.get("received_event_count") if observed else None,
            "note": "Service reachability does not prove current Hook trust or complete collection."}


def launch(settings: dict, timeout: float) -> dict:
    if timeout <= 0:
        return {"service": "start_timeout"}
    root = Path(settings["runtime_root"])
    backend = root / "backend"
    python = backend / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file() or not (backend / "main.py").is_file():
        return {"service": "runtime_missing"}
    if not (backend / "static/index.html").is_file():
        return {"service": "ui_missing"}
    port = urllib.parse.urlsplit(settings["base_url"]).port
    # Invoke the installed interpreter directly, never a shell or an install command.
    command = [str(python), "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)]
    directory = control_dir()
    options = {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with (directory / "service.log").open("ab") as log:
        process = subprocess.Popen(command, cwd=backend, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=log, **options)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return {"service": "start_failed"}
        if probe(settings["base_url"], min(0.9, max(0, deadline - time.monotonic()))):
            return {"service": "ready"}
        time.sleep(0.1)
    # Clean up only this live launch's process tree, never an existing server PID.
    if process.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=2)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                # Uvicorn can defer SIGTERM until an application import returns.
                # It must not become a surviving server after our timeout.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        process.wait(timeout=2)
    return {"service": "start_timeout"}


def ensure_service(timeout: float = 8) -> dict:
    settings = read_settings()
    if not settings["enabled"]:
        return {"service": "paused"}
    if not settings["runtime_root"]:
        return {"service": "manual"}
    # A caller-selected collection endpoint is not a request to start our local runtime.
    endpoint = os.getenv("EVOLVETRACE_API_URL")
    if endpoint and endpoint != settings["base_url"] + "/api/audit/events":
        return {"service": "external_endpoint"}
    deadline = time.monotonic() + timeout
    try:
        with control_lock(timeout=timeout):
            settings = read_settings()
            if not settings["enabled"]:
                return {"service": "paused"}
            if probe(settings["base_url"], min(0.9, max(0, deadline - time.monotonic()))):
                return {"service": "ready"}
            return launch(settings, max(0, deadline - time.monotonic()))
    except (OSError, ValueError, TimeoutError, subprocess.SubprocessError):
        return {"service": "start_failed"}


MESSAGES = {
    "runtime_missing": "Runtime missing. Install backend dependencies, then enable with the source directory again.",
    "ui_missing": "Workbench missing. Build the static UI once in the configured source directory.",
    "start_failed": "Local service did not start. Check EvolveTrace service.log and whether the port is occupied.",
    "start_timeout": "Local service startup timed out; this launch was stopped. Check EvolveTrace service.log.",
}


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--probe":
        print(json.dumps(_probe(sys.argv[2])))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["enable", "pause", "status", "open"])
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()
    try:
        if args.action == "pause":
            set_enabled(False)
        elif args.action == "enable":
            if args.runtime:
                configure(args.runtime, args.url)
            else:
                set_enabled(True)
            outcome = ensure_service()
            if outcome["service"] not in {"ready"}:
                print(json.dumps({**status(), "startup": outcome["service"],
                    "message": MESSAGES.get(outcome["service"], "Enable with --runtime <source-directory> for automatic startup.")}))
                return 1
        elif args.action == "open":
            if not probe(read_settings()["base_url"]):
                print(json.dumps({**status(), "message": "Enable collection or start the local service first."}))
                return 1
            import webbrowser
            webbrowser.open(read_settings()["base_url"])
        print(json.dumps(status()))
        return 0
    except (OSError, ValueError, TimeoutError) as error:
        print(json.dumps({"collection": "configuration_error", "message": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
