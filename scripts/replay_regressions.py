"""Re-score frozen evidence. Recorded commands are data and are never executed."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from harness.regression import MAX_SUITE_BYTES, replay_suite


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.output and args.output.resolve() == args.suite.resolve():
            raise ValueError("report output must differ from the input suite")
        with args.suite.open("rb") as stream:
            data = stream.read(MAX_SUITE_BYTES + 1)
        if len(data) > MAX_SUITE_BYTES:
            raise ValueError("suite exceeds 4 MiB")
        report = replay_suite(json.loads(data))
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
            print(json.dumps(report["summary"]))
        else:
            print(rendered, end="")
        return 1 if report["summary"]["errors"] or report["summary"]["regressions"] else 0
    except (OSError, ValueError, TypeError, RecursionError):
        print("Invalid or unreadable regression suite; no recorded command was executed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
