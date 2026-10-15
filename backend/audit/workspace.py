"""Local index and explicit review state alongside immutable audit evidence."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from uuid import uuid4

from .repository import AuditRepository
from .redaction import redact_value


def project_identity(workspace_root: str, relative_path: str) -> str:
    identity = str(Path(workspace_root).resolve()).casefold() if PureWindowsPath(workspace_root).is_absolute() else str(Path(workspace_root).resolve())
    return hashlib.sha256(f"{identity}\0{relative_path}".encode()).hexdigest()[:32]


def relative_path(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError("relative_path must be a nonempty workspace-relative path")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or PureWindowsPath(value).drive or ".." in path.parts:
        raise ValueError("project path must be workspace-relative")
    return path.as_posix()


class WorkspaceRepository(AuditRepository):
    def _initialize(self) -> None:
        super()._initialize()
        with self._lock, self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS activity_projects (
                    project_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
                    workspace_root TEXT NOT NULL, name TEXT NOT NULL,
                    relative_path TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS activity_decisions (
                    project_id TEXT NOT NULL, scope TEXT NOT NULL, target TEXT NOT NULL,
                    PRIMARY KEY (project_id, scope, target),
                    FOREIGN KEY (project_id) REFERENCES activity_projects(project_id)
                );
                CREATE TABLE IF NOT EXISTS activity_memory (
                    memory_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                    session_id TEXT NOT NULL, note TEXT NOT NULL,
                    evidence_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES activity_projects(project_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS activity_execution_directories (
                    event_id TEXT PRIMARY KEY, cwd TEXT NOT NULL,
                    rule_version TEXT NOT NULL, observed_at TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS activity_execution_results (
                    event_id TEXT PRIMARY KEY, result_json TEXT NOT NULL,
                    rule_version TEXT NOT NULL, observed_at TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS activity_evidence_retries (
                    event_id TEXT PRIMARY KEY, attempts INTEGER NOT NULL,
                    next_attempt REAL NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
                );
            """)

    def register(self, payload: dict) -> dict:
        if payload.get("schema_version") != "workspace-index/v1":
            raise ValueError("expected workspace-index/v1")
        raw_root = payload.get("workspace_root")
        if not isinstance(raw_root, str) or not Path(raw_root).is_absolute() or "\x00" in raw_root:
            raise ValueError("workspace_root must be an absolute local path")
        root = Path(raw_root).resolve()
        projects = payload.get("projects")
        if not isinstance(projects, list) or len(projects) > 500:
            raise ValueError("projects must be a list of at most 500 entries")
        workspace_id = project_identity(str(root), "workspace")
        records, identities, names = [], set(), set()
        for item in projects:
            if not isinstance(item, dict):
                raise ValueError("invalid project index entry")
            name = item.get("name")
            if not isinstance(name, str) or not name.strip() or len(name) > 200 or redact_value(name) != name:
                raise ValueError("invalid project name")
            relative = relative_path(item.get("relative_path"))
            if not (root / relative).resolve().is_relative_to(root):
                raise ValueError("project path escapes workspace")
            if redact_value(relative) != relative:
                raise ValueError("project path contains sensitive data")
            identity = project_identity(str(root), relative)
            if identity in identities or name in names:
                raise ValueError("duplicate project identity or name")
            identities.add(identity)
            names.add(name)
            records.append({"project_id": identity, "workspace_id": workspace_id, "name": name,
                            "relative_path": relative, "active": True})
        with self._lock, self._connect() as connection:
            connection.execute("UPDATE activity_projects SET active = 0 WHERE workspace_id = ?", (workspace_id,))
            for record in records:
                connection.execute("""INSERT INTO activity_projects VALUES (?, ?, ?, ?, ?, 1)
                    ON CONFLICT(project_id) DO UPDATE SET name=excluded.name, active=1""",
                    (record["project_id"], workspace_id, str(root), record["name"], record["relative_path"]))
        return {"schema_version": "workspace-index/v1", "workspace_id": workspace_id, "projects": records}

    def projects(self) -> list[dict]:
        with self._lock, self._connect() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM activity_projects ORDER BY workspace_id, relative_path")]

    def events(self, limit: int) -> tuple[list[dict], bool]:
        with self._lock, self._connect() as connection:
            rows = connection.execute("SELECT * FROM events ORDER BY rowid DESC LIMIT ?", (limit + 1,)).fetchall()
        return [self._event_from_row(row) for row in reversed(rows[:limit])], len(rows) > limit

    def referenced_events(self, session_id: str, refs: list[str]) -> list[dict]:
        placeholders = ",".join("?" for _ in refs)
        with self._lock, self._connect() as connection:
            rows = connection.execute(f"SELECT * FROM events WHERE session_id = ? AND event_id IN ({placeholders})", (session_id, *refs)).fetchall()
        return [self._event_from_row(row) for row in rows]

    _PENDING_EVIDENCE = """FROM events e
        LEFT JOIN activity_execution_results r ON r.event_id = e.event_id
        LEFT JOIN activity_evidence_retries retry ON retry.event_id = e.event_id
        WHERE r.event_id IS NULL
          AND (lower(e.tool_name) IN ('bash', 'shell', 'exec_command')
               OR lower(e.tool_name) LIKE '%.exec_command'
               OR lower(e.tool_name) LIKE '%.bash' OR lower(e.tool_name) LIKE '%.shell')
          AND json_type(e.details_json, '$.tool_use_id') = 'text'
          AND length(json_extract(e.details_json, '$.tool_use_id')) > 0
          AND json_type(e.details_json, '$.transcript_path') = 'text'
          AND length(json_extract(e.details_json, '$.transcript_path')) > 0"""

    def pending_execution_evidence(self, now: float, limit: int) -> list[dict]:
        with self._lock, self._connect() as connection:
            rows = connection.execute("SELECT e.* " + self._PENDING_EVIDENCE + """
                AND (retry.next_attempt IS NULL OR retry.next_attempt <= ?)
                ORDER BY COALESCE(retry.next_attempt, 0), e.rowid LIMIT ?""", (now, limit)).fetchall()
        return [self._event_from_row(row) for row in rows]

    def pending_execution_count(self) -> int:
        with self._lock, self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) " + self._PENDING_EVIDENCE).fetchone()[0])

    def defer_execution_evidence(self, refs: list[str], now: float) -> None:
        with self._lock, self._connect() as connection:
            for identity in refs:
                connection.execute("""INSERT INTO activity_evidence_retries
                    SELECT ?, 1, ? WHERE EXISTS (SELECT 1 FROM events WHERE event_id = ?)
                    ON CONFLICT(event_id) DO UPDATE SET attempts=attempts+1,
                    next_attempt=? + MIN(300, 5 * (1 << MIN(attempts, 6)))""",
                    (identity, now + 5, identity, now))

    def execution_directories(self, refs: list[str]) -> dict[str, str]:
        result = {}
        with self._lock, self._connect() as connection:
            for offset in range(0, len(refs), 500):
                batch = refs[offset:offset + 500]
                placeholders = ",".join("?" for _ in batch)
                result.update(connection.execute(
                    f"SELECT event_id, cwd FROM activity_execution_directories WHERE event_id IN ({placeholders})", batch
                ).fetchall())
        return result

    def cache_execution_directories(self, events: list[dict]) -> None:
        # Derived evidence receipts are separate from immutable Hook events.
        rows = [(event["event_id"], event["cwd"], "codex-command-directory/v1",
                 datetime.now(timezone.utc).isoformat(), event["event_id"])
                for event in events if event["_directory_source"] == "execution_record" and event["cwd"]]
        if rows:
            with self._lock, self._connect() as connection:
                connection.executemany("""INSERT OR IGNORE INTO activity_execution_directories
                    SELECT ?, ?, ?, ? WHERE EXISTS (SELECT 1 FROM events WHERE event_id = ?)""", rows)

    def execution_results(self, refs: list[str]) -> dict[str, dict]:
        result = {}
        with self._lock, self._connect() as connection:
            for offset in range(0, len(refs), 500):
                batch = refs[offset:offset + 500]
                placeholders = ",".join("?" for _ in batch)
                for row in connection.execute(f"SELECT event_id, result_json FROM activity_execution_results WHERE event_id IN ({placeholders})", batch):
                    result[row[0]] = json.loads(row[1])
        return result

    def cache_execution_results(self, events: list[dict]) -> None:
        rows = [(event["event_id"], json.dumps(event["_execution_result"]), "codex-command-result/v1",
                 datetime.now(timezone.utc).isoformat(), event["event_id"])
                for event in events if "_execution_result" in event]
        if rows:
            with self._lock, self._connect() as connection:
                connection.executemany("""INSERT OR IGNORE INTO activity_execution_results
                    SELECT ?, ?, ?, ? WHERE EXISTS (SELECT 1 FROM events WHERE event_id = ?)""", rows)

    def decisions(self, project_id: str) -> set[tuple[str, str]]:
        with self._lock, self._connect() as connection:
            return {(row[0], row[1]) for row in connection.execute("SELECT scope, target FROM activity_decisions WHERE project_id = ?", (project_id,))}

    def decide(self, project_id: str, scope: str, target: str, remove: bool = False) -> None:
        with self._lock, self._connect() as connection:
            if remove:
                connection.execute("DELETE FROM activity_decisions WHERE project_id = ? AND scope = ? AND target = ?", (project_id, scope, target))
            else:
                connection.execute("INSERT OR IGNORE INTO activity_decisions VALUES (?, ?, ?)", (project_id, scope, target))

    def remember(self, project_id: str, session_id: str, note: str, refs: list[str]) -> dict:
        record = {"memory_id": uuid4().hex, "project_id": project_id, "session_id": session_id,
                  "note": redact_value(note), "evidence_refs": refs,
                  "created_at": datetime.now(timezone.utc).isoformat(), "status": "human_reviewed"}
        with self._lock, self._connect() as connection:
            connection.execute("INSERT INTO activity_memory VALUES (?, ?, ?, ?, ?, ?)",
                (record["memory_id"], project_id, session_id, record["note"], json.dumps(refs), record["created_at"]))
        return record

    def memory(self, project_id: str) -> list[dict]:
        with self._lock, self._connect() as connection:
            rows = connection.execute("SELECT * FROM activity_memory WHERE project_id = ? ORDER BY created_at DESC LIMIT 20", (project_id,)).fetchall()
        return [{"memory_id": row["memory_id"], "project_id": project_id, "session_id": row["session_id"],
                 "note": row["note"], "evidence_refs": json.loads(row["evidence_json"]),
                 "created_at": row["created_at"], "status": "human_reviewed"} for row in rows]
