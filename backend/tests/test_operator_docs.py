from pathlib import Path


ROOT = Path(__file__).parents[2]
USAGE = ROOT / "docs" / "usage.md"
OBSERVABILITY = ROOT / "docs" / "observability.md"
OBSERVE_SCRIPT = ROOT / "scripts" / "observe.ps1"
START_SCRIPT = ROOT / "start.ps1"
BUILD_SCRIPT = ROOT / "scripts" / "build_static_ui.ps1"


def test_usage_documents_the_single_process_operator_flow() -> None:
    text = USAGE.read_text(encoding="utf-8")

    for phrase in (
        "http://127.0.0.1:8001",
        "./start.ps1 -NoBrowser",
        "plugin/",
        "aictx task prepare",
        "aictx task submit",
        "临时目录",
    ):
        assert phrase in text
    assert "打开 `http://127.0.0.1:3000`" not in text


def test_observability_guide_covers_the_evidence_chain() -> None:
    text = OBSERVABILITY.read_text(encoding="utf-8")

    for phrase in (
        "/health",
        "/api/audit/sessions",
        "/api/harness/tasks",
        "/api/harness/runs/unbound",
        "Hook",
        "Evaluation",
        "Review",
        "generated",
        "effective",
        "隐藏思维链",
    ):
        assert phrase in text


def test_observe_script_is_read_only_and_portable() -> None:
    text = OBSERVE_SCRIPT.read_text(encoding="utf-8")

    assert "[string]$BaseUrl" in text
    assert "[switch]$ExpectEvidence" in text
    for endpoint in (
        "/health",
        "/api/audit/sessions",
        "/api/harness/tasks",
        "/api/harness/runs/unbound",
    ):
        assert endpoint in text
    for mutation in ("-Method Post", "-Method Delete", "seed_demo", "evaluate", "review"):
        assert mutation not in text
    assert "D:\\" not in text


def test_entry_docs_link_to_usage_and_observability() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    runbook = (ROOT / "RUN.md").read_text(encoding="utf-8")
    plugin = (ROOT / "plugin" / "README.md").read_text(encoding="utf-8")

    for text in (readme, runbook, plugin):
        assert "docs/usage.md" in text or "../docs/usage.md" in text
        assert "docs/observability.md" in text or "../docs/observability.md" in text


def test_start_script_uses_the_venv_python_module_entrypoint() -> None:
    text = START_SCRIPT.read_text(encoding="utf-8")

    assert "venv\\Scripts\\python.exe" in text
    assert "-m uvicorn main:app" in text


def test_static_ui_build_stops_when_npm_fails() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert text.count("$LASTEXITCODE") >= 2
    assert "throw" in text
