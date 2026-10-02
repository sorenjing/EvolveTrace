"""Command-line workflows for AI Context Kit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from . import __version__
from .adapters import ManagedFileError, render_adapters, write_managed_file
from .config import ConfigError, find_workspace, load_config
from .discovery import discover_projects
from .facts import extract_facts
from .harness_export import build_harness_bundle
from .evolvetrace_client import submit_task
from .locking import workspace_write_lock
from .pack_install import PackInstaller
from .personal_pack import PersonalAIPack
from .publish import publish_bundle
from .repository_context import evaluate_freshness, inspect_repository
from .render import (
    MarkerError,
    render_chatgpt_project_context,
    render_project_memory,
    render_workspace,
    slugify,
)
from .state import (
    ProjectState,
    StateError,
    WorkspaceState,
    _atomic_text,
    classify_projects,
    fingerprint_facts,
    load_state,
    write_state,
)
from .task_contracts import ContextReceipt, task_envelope_from_dict
from .task_workspace import prepare_task
from .workspace_discovery import DiscoveryResult, resolve_workspace


CONFIG_TEMPLATE = """version = 1
max_file_bytes = 1048576

[discovery]
include = ["."]
exclude = [".git", ".ai", "node_modules", ".venv", "venv", "dist", "build", "target", "coverage"]

[projects]
"""
GLOBAL_TEMPLATE = """# Global context

Record stable preferences, environment constraints, and conventions shared by every project.
"""
CURRENT_TEMPLATE = """# Current work

Record only short-lived cross-session state here. Clear it when the work is complete.
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aictx", description="Offline shared context for AI coding tools")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "scan", "status", "check"):
        command = subparsers.add_parser(name)
        command.add_argument("--workspace", type=Path)
        if name == "status":
            command.add_argument("--pack-target", type=Path)
        if name == "init":
            command.add_argument("--dry-run", action="store_true")
    update = subparsers.add_parser("update")
    update.add_argument("project", nargs="?")
    update.add_argument("--workspace", type=Path)
    update.add_argument("--dry-run", action="store_true")
    update.add_argument("--manifest", type=Path)
    update.add_argument("--target", type=Path)
    setup = subparsers.add_parser("setup", description="Validate a Personal AI Pack manifest.")
    setup.add_argument("--manifest", type=Path, required=True)
    install = subparsers.add_parser("install", description="Install managed platform adapters.")
    install.add_argument("--manifest", type=Path, required=True)
    install.add_argument("--target", type=Path, required=True)
    doctor = subparsers.add_parser("doctor", description="Diagnose a Personal AI Pack installation.")
    doctor.add_argument("--target", type=Path, required=True)
    uninstall = subparsers.add_parser("uninstall", description="Remove only managed pack files.")
    uninstall.add_argument("--target", type=Path, required=True)
    locate = subparsers.add_parser("locate", description="Resolve a bounded local workspace.")
    locate.add_argument("--manifest", type=Path, required=True)
    locate.add_argument("--start", type=Path, default=Path.cwd())
    locate.add_argument("--workspace", type=Path)
    locate.add_argument("--portfolio", type=Path)
    locate.add_argument("--local-override", type=Path)
    locate.add_argument("--json", action="store_true")
    export = subparsers.add_parser(
        "export", description="Create a portable context handoff for a supported target."
    )
    export.add_argument("target", choices=("chatgpt-project", "harness"))
    export.add_argument("project")
    export.add_argument("--workspace", type=Path)
    export.add_argument("--output", type=Path)
    export.add_argument("--format")
    publish = subparsers.add_parser(
        "publish", description="Create a reviewable directory for explicit remote publication."
    )
    publish.add_argument("target", choices=("github",))
    publish.add_argument("project")
    publish.add_argument("--workspace", type=Path)
    publish.add_argument("--output", type=Path)
    task = subparsers.add_parser("task", description="Prepare or submit a context-aware task.")
    task_commands = task.add_subparsers(dest="task_command", required=True)
    prepare = task_commands.add_parser("prepare")
    prepare.add_argument("project")
    prepare.add_argument("--intent", required=True)
    prepare.add_argument("--platform", default="codex")
    prepare.add_argument("--skill", action="append", default=[])
    prepare.add_argument("--contract", type=Path)
    prepare.add_argument("--workspace", type=Path)
    submit = task_commands.add_parser("submit")
    submit.add_argument("task_id")
    submit.add_argument("--evolvetrace-url", required=True)
    submit.add_argument("--workspace", type=Path)
    repo = subparsers.add_parser("repo", description="Inspect read-only Git context.")
    repo_commands = repo.add_subparsers(dest="repo_command", required=True)
    inspect = repo_commands.add_parser("inspect")
    inspect.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    inspect.add_argument("--context-commit")
    inspect.add_argument("--json", action="store_true")
    return parser


def _root(value: Path | None, *, initializing: bool) -> Path:
    start = (value or Path.cwd()).resolve()
    if initializing:
        return start
    return find_workspace(start)


def _facts(root: Path):
    config = load_config(root)
    facts = [extract_facts(project, config) for project in discover_projects(config)]
    identities: dict[str, str] = {}
    for item in facts:
        identity = slugify(item.project.name)
        previous = identities.get(identity)
        if previous is not None:
            raise ConfigError(
                f"project name collision: {previous} and {item.project.relative_path} both use {identity}.md"
            )
        identities[identity] = item.project.relative_path
    return facts


def _read_exact(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return stream.read()


def _write_if_changed(path: Path, contents: str, *, dry_run: bool) -> bool:
    existing = _read_exact(path) if path.exists() else None
    if existing == contents:
        return False
    if not dry_run:
        _atomic_text(path, contents)
    return True


def _initialize(root: Path, *, dry_run: bool) -> None:
    if not (root / ".aictx.toml").exists():
        _write_if_changed(root / ".aictx.toml", CONFIG_TEMPLATE, dry_run=dry_run)
    for path, contents in (
        (root / ".ai/GLOBAL.md", GLOBAL_TEMPLATE),
        (root / ".ai/CURRENT.md", CURRENT_TEMPLATE),
    ):
        if not path.exists():
            _write_if_changed(path, contents, dry_run=dry_run)
    for relative, contents in render_adapters().items():
        write_managed_file(root / relative, contents, dry_run=dry_run)


def _update(root: Path, selected: str | None, *, dry_run: bool) -> None:
    facts = _facts(root)
    if selected:
        matching = [item for item in facts if item.project.name == selected or slugify(item.project.name) == selected]
        if not matching:
            raise ConfigError(f"unknown project: {selected}")
        update_names = {item.project.name for item in matching}
    else:
        update_names = {item.project.name for item in facts}

    old_state = load_state(root)
    current_names = {item.project.name for item in facts}
    new_projects = {
        name: state for name, state in old_state.projects.items() if name in current_names
    }
    for item in facts:
        if item.project.name not in update_names:
            continue
        target = root / ".ai" / "projects" / f"{slugify(item.project.name)}.md"
        existing = _read_exact(target) if target.exists() else None
        rendered = render_project_memory(item, existing)
        _write_if_changed(target, rendered, dry_run=dry_run)
        fingerprint = fingerprint_facts(item)
        new_projects[item.project.name] = ProjectState(
            item.project.relative_path, fingerprint, fingerprint, item.git_head, item.git_branch
        )
    _write_if_changed(root / ".ai/WORKSPACE.md", render_workspace(facts), dry_run=dry_run)
    if not dry_run:
        write_state(root, WorkspaceState(new_projects))


def _select_project(root: Path, selected: str):
    matching = [
        item
        for item in _facts(root)
        if item.project.name == selected or slugify(item.project.name) == selected
    ]
    if not matching:
        raise ConfigError(f"unknown project: {selected}")
    return matching[0]


def _export_chatgpt_project_context(root: Path, selected: str, output: Path | None) -> Path:
    facts = _select_project(root, selected)
    memory_path = root / ".ai" / "projects" / f"{slugify(facts.project.name)}.md"
    global_path = root / ".ai" / "GLOBAL.md"
    project_memory = _read_exact(memory_path) if memory_path.exists() else None
    global_context = _read_exact(global_path) if global_path.exists() else None
    destination = output or root / ".ai" / "exports" / f"{slugify(facts.project.name)}-chatgpt-project.md"
    if not destination.is_absolute():
        destination = root / destination
    _atomic_text(destination, render_chatgpt_project_context(facts, project_memory, global_context))
    return destination


def _export_harness_context(root: Path, selected: str, output: Path | None) -> None:
    bundle = build_harness_bundle(root, selected)
    rendered = json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output is None or str(output) == "-":
        print(rendered, end="")
        return
    destination = output if output.is_absolute() else root / output
    _atomic_text(destination, rendered)
    print(f"exported harness context to {destination}")


def _discovery_payload(result: DiscoveryResult) -> dict[str, object]:
    return {
        "status": result.status,
        "source": result.source,
        "workspace_root": str(result.workspace_root) if result.workspace_root else None,
        "portfolio_root": str(result.portfolio_root) if result.portfolio_root else None,
        "candidates": [str(path) for path in result.candidates],
        "findings": list(result.findings),
    }


def _print_discovery(result: DiscoveryResult, *, as_json: bool) -> None:
    payload = _discovery_payload(result)
    if as_json:
        print(json.dumps(payload, sort_keys=True))
        return
    print(f"status: {result.status}")
    print(f"source: {result.source}")
    if result.workspace_root:
        print(f"workspace: {result.workspace_root}")
    if result.portfolio_root:
        print(f"portfolio: {result.portfolio_root}")
    for candidate in result.candidates:
        print(f"candidate: {candidate}")
    for finding in result.findings:
        print(f"finding: {finding}")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "repo":
            repository = inspect_repository(args.path)
            freshness = evaluate_freshness(args.context_commit, repository)
            if args.json:
                print(json.dumps({"repository": repository.to_dict(), "context_freshness": freshness.to_dict()}, sort_keys=True))
            else:
                print(f"Repository: {repository.repository_name}")
                print(f"Branch: {repository.branch or ('detached HEAD' if repository.head_commit else 'unborn')}")
                print(f"HEAD: {repository.head_commit or 'none'}")
                print(f"Working tree: {'unknown' if repository.dirty is None else 'dirty' if repository.dirty else 'clean'}")
                print(f"Upstream: {repository.upstream or 'none'}")
                print(f"Ahead: {repository.ahead if repository.ahead is not None else 'unknown'}")
                print(f"Behind: {repository.behind if repository.behind is not None else 'unknown'}")
                print(f"Context local: {freshness.local}")
                print(f"Context remote (cached ref): {freshness.remote}")
                if repository.error:
                    print(f"Inspection: {repository.error}")
            return 2 if repository.error == "not_git_repository" else 0
        if args.command == "setup":
            pack = PersonalAIPack.load(args.manifest)
            print(f"personal AI pack is valid: {pack.pack_id}")
            return 0
        if args.command == "locate":
            pack = PersonalAIPack.load(args.manifest)
            result = resolve_workspace(
                start=args.start,
                pack=pack,
                workspace=args.workspace,
                portfolio=args.portfolio,
                local_override=args.local_override,
            )
            _print_discovery(result, as_json=args.json)
            if result.status == "resolved":
                return 0
            return 2 if result.status == "invalid" else 1
        if args.command in {"install", "uninstall", "doctor"}:
            installer = PackInstaller(args.target)
            if args.command == "install":
                pack = PersonalAIPack.load(args.manifest)
                installer.install(pack, args.manifest)
                print(f"installed personal AI pack: {pack.pack_id}")
                return 0
            if args.command == "uninstall":
                installer.uninstall()
                print("uninstalled managed personal AI pack files")
                return 0
            findings = installer.doctor()
            if findings:
                print("\n".join(findings))
                return 1
            print("personal AI pack installation is valid")
            return 0
        if args.command == "status" and args.pack_target is not None:
            print(json.dumps(PackInstaller(args.pack_target).status(), sort_keys=True))
            return 0
        if args.command == "update" and (args.manifest is not None or args.target is not None):
            if args.manifest is None or args.target is None:
                raise ConfigError("pack update requires both --manifest and --target")
            pack = PersonalAIPack.load(args.manifest)
            PackInstaller(args.target).install(pack, args.manifest)
            print(f"updated personal AI pack: {pack.pack_id}")
            return 0
        root = _root(args.workspace, initializing=args.command == "init")
        if args.command == "init":
            if args.dry_run:
                _initialize(root, dry_run=True)
            else:
                with workspace_write_lock(root):
                    _initialize(root, dry_run=False)
                    _update(root, None, dry_run=False)
            print(f"initialized {root}")
            return 0
        if args.command == "scan":
            for item in _facts(root):
                print(f"{item.project.name}\t{item.project.relative_path}\t{', '.join(item.technologies)}")
            return 0
        if args.command == "status":
            statuses = classify_projects(_facts(root), load_state(root))
            for name, status in statuses.items():
                print(f"{status}\t{name}")
            return 1 if any(status != "current" for status in statuses.values()) else 0
        if args.command == "update":
            if args.dry_run:
                _update(root, args.project, dry_run=True)
            else:
                with workspace_write_lock(root):
                    _update(root, args.project, dry_run=False)
            print("dry run complete" if args.dry_run else "context updated")
            return 0
        if args.command == "check":
            findings: list[str] = []
            facts = _facts(root)
            try:
                load_state(root, strict=True)
            except StateError as exc:
                findings.append(str(exc))
            for item in facts:
                target = root / ".ai/projects" / f"{slugify(item.project.name)}.md"
                if not target.exists():
                    findings.append(f"missing project memory: {target}")
                    continue
                try:
                    render_project_memory(item, _read_exact(target))
                except MarkerError as exc:
                    findings.append(f"marker error in {target}: {exc}")
            for relative, expected in render_adapters().items():
                target = root / relative
                if not target.exists():
                    findings.append(f"missing adapter: {relative}")
                elif _read_exact(target) != expected:
                    findings.append(f"adapter content mismatch: {relative}")
            if findings:
                print("\n".join(findings))
                return 1
            print("context is valid")
            return 0
        if args.command == "export":
            if args.target == "chatgpt-project":
                destination = _export_chatgpt_project_context(root, args.project, args.output)
                print(f"exported ChatGPT project context to {destination}")
                return 0
            if args.target == "harness":
                if args.format != "json":
                    raise ConfigError("harness export requires --format json")
                _export_harness_context(root, args.project, args.output)
                return 0
        if args.command == "publish":
            destination = args.output or root / ".ai" / "published"
            if not destination.is_absolute():
                destination = root / destination
            with workspace_write_lock(root):
                output = publish_bundle(root, args.project, destination)
            print(f"published {output}; review and commit the directory to GitHub")
            return 0
        if args.command == "task" and args.task_command == "prepare":
            contract = None
            if args.contract is not None:
                try:
                    contract = json.loads(args.contract.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise ConfigError(f"invalid task contract file: {exc}") from exc
                if not isinstance(contract, dict):
                    raise ConfigError("task contract file must contain an object")
            prepared = prepare_task(
                root,
                args.project,
                intent=args.intent,
                platform=args.platform,
                skill_ids=tuple(args.skill),
                contract=contract,
            )
            print(f"Task ID: {prepared.envelope.task_id}")
            print(f"Bundle ID: {prepared.bundle['bundle_id']}")
            print(f"Artifacts: {prepared.task_directory.as_posix()}")
            return 0
        if args.command == "task" and args.task_command == "submit":
            if Path(args.task_id).name != args.task_id:
                raise ConfigError("invalid task_id")
            directory = root / ".ai" / "tasks" / args.task_id
            envelope_payload = json.loads((directory / "envelope.json").read_text(encoding="utf-8"))
            bundle = json.loads((directory / "bundle.json").read_text(encoding="utf-8"))
            receipt_payload = json.loads((directory / "receipt.json").read_text(encoding="utf-8"))
            try:
                envelope = task_envelope_from_dict(envelope_payload)
            except ValueError as exc:
                raise ConfigError(str(exc)) from exc
            receipt = ContextReceipt(
                **{
                    **receipt_payload,
                    "delivered_source_ids": tuple(receipt_payload["delivered_source_ids"]),
                    "loaded_skill_ids": tuple(receipt_payload["loaded_skill_ids"]),
                }
            )
            result = submit_task(
                args.evolvetrace_url,
                envelope=envelope,
                bundle=bundle,
                receipt=receipt,
            )
            if not result.completed:
                print(f"observability incomplete for Task ID: {args.task_id}")
                return 0
            _atomic_text(
                directory / "receipt.json",
                json.dumps(
                    result.delivered_receipt.to_dict(),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
            )
            print(f"submitted Task ID: {result.task_id}")
            print(f"Snapshot ID: {result.snapshot_id}")
            print(f"Receipt ID: {result.receipt_id}")
            return 0
    except (ConfigError, MarkerError, ManagedFileError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2
    return 2


def entrypoint() -> None:
    raise SystemExit(main())
