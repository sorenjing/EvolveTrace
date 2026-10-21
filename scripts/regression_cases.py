"""Export a local Run draft, then freeze separately reviewed labels. Never runs commands."""

import argparse
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from harness.regression import MAX_SUITE_BYTES
from harness.regression_export import freeze_draft


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def export_local(args) -> dict:
    parts = urlsplit(args.url)
    host = parts.hostname
    if host == "localhost":
        host = "127.0.0.1"
    if (parts.scheme != "http" or not host or not ipaddress.ip_address(host).is_loopback
            or parts.username or parts.password or parts.path not in {"", "/"} or parts.query or parts.fragment):
        raise ValueError("use a plain loopback HTTP origin")
    if not all(re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value) for value in (args.task_id, args.run_id)):
        raise ValueError("invalid task or run identifier")
    authority = f"[{host}]" if ":" in host else host
    if parts.port is not None:
        authority += f":{parts.port}"
    path = f"/api/harness/tasks/{args.task_id}/runs/{args.run_id}/regression-draft"
    request = Request(urlunsplit(("http", authority, path, "", "")), method="POST",
                      headers={"Content-Type": "application/json", "Accept": "application/json"},
                      data=json.dumps({"workspace_root": args.workspace_root, "case_id": args.case_id}).encode())
    with build_opener(ProxyHandler({}), NoRedirects()).open(request, timeout=5) as response:
        data = response.read(MAX_SUITE_BYTES + 1)
    if len(data) > MAX_SUITE_BYTES:
        raise ValueError("draft exceeds 4 MiB")
    draft = json.loads(data)
    if not isinstance(draft, dict) or draft.get("schema_version") != "regression-draft/v1":
        raise ValueError("invalid draft response")
    return draft


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    export = actions.add_parser("export", help="export a private local draft; review before sharing")
    export.add_argument("--url", default="http://127.0.0.1:8001")
    for name in ("task-id", "run-id", "workspace-root", "case-id"):
        export.add_argument("--" + name, required=True)
    export.add_argument("--output", type=Path, required=True)
    freeze = actions.add_parser("freeze", help="freeze human-reviewed expected results; does not score them")
    freeze.add_argument("draft", type=Path)
    freeze.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("output already exists")
        if args.action == "export":
            result = export_local(args)
        else:
            with args.draft.open("rb") as stream:
                data = stream.read(MAX_SUITE_BYTES + 1)
            if len(data) > MAX_SUITE_BYTES:
                raise ValueError("draft exceeds 4 MiB")
            result = freeze_draft(json.loads(data))
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if len(rendered.encode("utf-8")) > MAX_SUITE_BYTES:
            rendered = json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
        if len(rendered.encode("utf-8")) > MAX_SUITE_BYTES:
            raise ValueError("serialized output exceeds 4 MiB")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
        print("Local draft saved; review labels and privacy before freezing or sharing." if args.action == "export"
              else "Reviewed suite saved; run replay_regressions.py to compare evaluator results.")
        return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print("Export/freeze failed: check source, loopback service, portability, review, digest and unused output path.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
