"""Pure, conservative command descriptions, never an execution or safety policy."""

import re
import shlex


VERSION = "command-classification/v1"
OPERATIONS = {
    "find_files": "read_search", "search_content": "read_search", "read_file": "read_search",
    "modify_files": "edit", "verify_tests": "build_test", "verify_static": "build_test",
    "build_package": "build_test", "run_program": "other", "manage_dependencies": "dependencies",
    "vcs_read": "git", "vcs_write": "git", "network": "network", "unknown": "other",
}
_QUOTED = re.compile(r'''"(?:\\.|[^"\\])*"|'[^']*' ''', re.VERBOSE)


def tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=False)
    except ValueError:
        return []


def _executable(value: str) -> str:
    return value.strip("\"'").replace("\\", "/").rsplit("/", 1)[-1].lower().removesuffix(".exe")


def _skip_options(args: list[str], value_options: set[str]) -> list[str]:
    while args and args[0].startswith("-"):
        option = args.pop(0)
        if option in value_options:
            if not args:
                return []
            args.pop(0)
        elif "=" not in option and option not in {"--no-pager", "--quiet", "-q", "--silent", "--offline", "--frozen", "--no-sync"}:
            return []  # Unknown options may consume the next argument.
    return args


def _script_operation(name: str) -> str:
    words = set(re.split(r"[:_-]", name))
    if words & {"test", "pytest", "vitest", "jest", "unittest"}:
        return "verify_tests"
    if words & {"lint", "check", "typecheck", "typechecking", "audit", "security"}:
        return "verify_static"
    if words & {"build", "compile", "package", "pack"}:
        return "build_package"
    if words & {"start", "dev", "serve", "preview"}:
        return "run_program"
    return "unknown"


def _simple(parts: list[str], depth: int = 0) -> tuple[str, str]:
    if not parts or depth >= 4:
        return "unknown", "unrecognized"
    executable, args = _executable(parts[0]), [value.strip("\"'").lower() for value in parts[1:]]
    operation = "unknown"
    if executable == "git":
        args = _skip_options(args, {"-c", "-C".lower(), "--git-dir", "--work-tree"})
        if args and args[0] in {"status", "diff", "log", "show", "rev-parse", "ls-files", "ls-tree", "grep", "blame"}:
            operation = "vcs_read"
        elif args and args[0] in {"add", "commit", "push", "pull", "fetch", "merge", "rebase", "reset", "clean", "switch", "checkout", "restore", "stash", "tag", "branch"}:
            operation = "vcs_write"
    elif executable in {"rg", "grep", "select-string"}:
        operation = "find_files" if executable == "rg" and "--files" in args else "search_content"
    elif executable in {"find", "ls", "dir", "get-childitem"}:
        operation = "modify_files" if executable == "find" and "-delete" in args else "find_files"
        if executable == "find" and any(value in {"-exec", "-execdir", "-ok", "-okdir"} for value in args):
            operation = "unknown"
    elif executable in {"cat", "head", "tail", "get-content"}:
        operation = "read_file"
    elif executable == "sed":
        if any(value == "--in-place" or value.startswith(("-i", "--in-place=")) for value in args):
            operation = "modify_files"
        elif len(args) >= 2 and args[0] == "-n" and re.fullmatch(r"\d+(?:,\d+)?p", args[1]):
            operation = "read_file"
    elif executable in {"rm", "cp", "mv", "mkdir", "remove-item", "set-content", "add-content", "copy-item", "move-item", "new-item"}:
        operation = "modify_files"
    elif executable in {"curl", "wget", "invoke-webrequest", "invoke-restmethod"}:
        operation = "network"
    elif executable in {"pytest", "vitest", "jest"}:
        operation = "verify_tests"
    elif executable in {"ruff", "eslint", "tsc"}:
        operation = "verify_static"
    elif executable in {"make", "cmake", "msbuild"}:
        operation = "build_package"
    elif executable in {"python", "python3"} and args[:1] == ["-m"] and len(args) > 1:
        return _simple([args[1], *args[2:]], depth + 1) if args[1] != "compileall" else ("build_package", "known_command")
    elif executable == "uv" and args[:1] == ["run"]:
        child = _skip_options(args[1:], {"--project", "--directory", "--python", "--package"})
        return _simple(child, depth + 1)
    elif executable == "uv" and args[:1] == ["pip"]:
        return _simple(["pip", *args[1:]], depth + 1)
    elif executable in {"npm", "pnpm", "yarn", "pip", "pip3", "uv", "poetry", "cargo", "go", "dotnet"}:
        args = _skip_options(args, {"--prefix", "--dir", "-c", "--directory"})
        action = args[0] if args else ""
        if action in {"install", "ci", "add", "update", "sync", "download", "uninstall", "remove", "restore"}:
            operation = "manage_dependencies"
        elif executable in {"npm", "pnpm", "yarn"} and args:
            script = args[1] if action in {"run", "run-script"} and len(args) > 1 else action
            operation = _script_operation(script)
            return operation, "script_name_hint" if operation != "unknown" else "unrecognized"
        elif action in {"test", "build", "check", "run"}:
            operation = {"test": "verify_tests", "build": "build_package", "check": "verify_static", "run": "run_program"}[action]
    return operation, "known_command" if operation != "unknown" else "unrecognized"


def classify_command(tool_name: str, command: str) -> dict:
    tool = tool_name.split(".")[-1].lower()
    named = {"apply_patch": "modify_files", "edit": "modify_files", "write": "modify_files",
             "read": "read_file", "read_file": "read_file", "glob": "find_files",
             "list_directory": "find_files", "grep": "search_content"}
    if tool in named:
        operation = named[tool]
        return {"category": OPERATIONS[operation], "operation": operation, "basis": "known_tool", "shape": "tool"}
    masked = _QUOTED.sub(lambda match: " " * len(match.group()), command)
    operators = list(re.finditer(r"&&|\|\||[;&|\n]", masked))
    substitution = any(value in command for value in ("$(", "${", "`"))
    if operators or any(value in masked for value in (">", "<")) or substitution:
        operation, basis = "unknown", "unrecognized"
        if not operators and not substitution:
            candidate, _ = _simple(tokens(command))
            if candidate == "modify_files":
                # Redirected output does not erase a known mutation's freshness boundary.
                operation, basis = candidate, "compound_hint"
        if len(operators) == 1 and not any(value in masked for value in (">", "<")) and not substitution:
            operator = operators[0]
            left, right = tokens(command[:operator.start()]), tokens(command[operator.end():])
            if left and _executable(left[0]) in {"cd", "set-location"} and operator.group() == "&&":
                operation, _ = _simple(right)
            elif right and _executable(right[0]) in {"head", "tail"} and operator.group() == "|":
                candidate, _ = _simple(left)
                if candidate in {"find_files", "search_content", "read_file"}:
                    operation = candidate
            if operation != "unknown":
                basis = "compound_hint"
        return {"category": "mixed", "operation": operation, "basis": basis, "shape": "compound"}
    operation, basis = _simple(tokens(command))
    return {"category": OPERATIONS[operation], "operation": operation, "basis": basis, "shape": "single"}


def expected_nonzero(tool_name: str, command: str) -> str | None:
    """Recognize only documented query exit-1 meanings in simple shell calls."""
    if tool_name.split(".")[-1].lower() not in {"bash", "shell", "exec_command", "powershell"}:
        return None
    if classify_command(tool_name, command)["shape"] != "single":
        return None
    parts = tokens(command)
    if not parts:
        return None
    executable = _executable(parts[0])
    if executable in {"rg", "grep"}:
        return "no_matches"
    args = [value.lower() for value in parts[1:]]
    if "--" in args:
        args = args[:args.index("--")]
    if executable == "git" and args[:1] == ["diff"] and "--no-index" not in args and any(value in {"--exit-code", "--quiet"} for value in args):
        return "differences_found"
    return None
