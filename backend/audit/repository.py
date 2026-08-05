import json
import sqlite3
import threading
from pathlib import Path
from typing import Iterable

from .models import AuditEvent
from .risk import RiskFinding


class AuditRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    cwd TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    turn_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    cwd TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    risks_json TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_events_session_order
                    ON events(session_id, sequence, timestamp, event_id);
                """
            )

    def next_sequence(self, session_id: str) -> int:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM events WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return int(row[0])

    def event_sequence(self, event_id: str) -> int | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT sequence FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
        return int(row[0]) if row is not None else None

    def add_event(self, event: AuditEvent, findings: Iterable[RiskFinding] = ()) -> bool:
        risk_json = json.dumps(
            [finding.to_dict() for finding in findings], ensure_ascii=False, default=str
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO sessions(session_id, cwd, started_at, last_seen)
                VALUES (?, ?, ?, ?)
                """,
                (event.session_id, event.cwd, event.timestamp, event.timestamp),
            )
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO events(
                    event_id, session_id, event_type, timestamp, turn_id, sequence,
                    cwd, tool_name, details_json, risks_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.session_id,
                    event.event_type,
                    event.timestamp,
                    event.turn_id,
                    event.sequence,
                    event.cwd,
                    event.tool_name,
                    json.dumps(event.details, ensure_ascii=False, default=str),
                    risk_json,
                ),
            )
            if cursor.rowcount == 0:
                return False
            connection.execute(
                """
                UPDATE sessions
                SET last_seen = CASE WHEN last_seen < ? THEN ? ELSE last_seen END
                WHERE session_id = ?
                """,
                (event.timestamp, event.timestamp, event.session_id),
            )
        return True

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> dict:
        return {
            "event_id": row["event_id"],
            "session_id": row["session_id"],
            "event_type": row["event_type"],
            "timestamp": row["timestamp"],
            "turn_id": row["turn_id"],
            "sequence": row["sequence"],
            "cwd": row["cwd"],
            "tool_name": row["tool_name"],
            "details": json.loads(row["details_json"]),
            "risk_findings": json.loads(row["risks_json"]),
        }

    @staticmethod
    def _session_from_row(row: sqlite3.Row) -> dict:
        return {
            "session_id": row["session_id"],
            "cwd": row["cwd"],
            "started_at": row["started_at"],
            "last_seen": row["last_seen"],
            "event_count": row["event_count"],
            "tool_call_count": row["tool_call_count"],
            "modified_file_count": row["modified_file_count"],
            "risk_count": row["risk_count"],
        }

    def list_sessions(self) -> list[dict]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    s.*,
                    COUNT(e.event_id) AS event_count,
                    SUM(CASE WHEN e.tool_name <> '' THEN 1 ELSE 0 END) AS tool_call_count,
                    SUM(
                        CASE WHEN json_array_length(json_extract(e.details_json, '$.changed_files')) > 0
                        THEN json_array_length(json_extract(e.details_json, '$.changed_files'))
                        ELSE 0 END
                    ) AS modified_file_count,
                    SUM(json_array_length(e.risks_json)) AS risk_count
                FROM sessions s
                LEFT JOIN events e ON e.session_id = s.session_id
                GROUP BY s.session_id
                ORDER BY s.last_seen DESC, s.session_id DESC
                """
            ).fetchall()
        return [
            {
                **self._session_from_row(row),
                "tool_call_count": row["tool_call_count"] or 0,
                "modified_file_count": row["modified_file_count"] or 0,
                "risk_count": row["risk_count"] or 0,
            }
            for row in rows
        ]

    def get_session(self, session_id: str) -> dict | None:
        with self._lock, self._connect() as connection:
            session_row = connection.execute(
                """
                SELECT
                    s.*,
                    COUNT(e.event_id) AS event_count,
                    SUM(CASE WHEN e.tool_name <> '' THEN 1 ELSE 0 END) AS tool_call_count,
                    SUM(
                        CASE WHEN json_array_length(json_extract(e.details_json, '$.changed_files')) > 0
                        THEN json_array_length(json_extract(e.details_json, '$.changed_files'))
                        ELSE 0 END
                    ) AS modified_file_count,
                    SUM(json_array_length(e.risks_json)) AS risk_count
                FROM sessions s
                LEFT JOIN events e ON e.session_id = s.session_id
                WHERE s.session_id = ?
                GROUP BY s.session_id
                """,
                (session_id,),
            ).fetchone()
            if session_row is None:
                return None
            event_rows = connection.execute(
                """
                SELECT * FROM events
                WHERE session_id = ?
                ORDER BY sequence ASC, timestamp ASC, event_id ASC
                """,
                (session_id,),
            ).fetchall()
        return {
            **self._session_from_row(session_row),
            "tool_call_count": session_row["tool_call_count"] or 0,
            "modified_file_count": session_row["modified_file_count"] or 0,
            "risk_count": session_row["risk_count"] or 0,
            "events": [self._event_from_row(row) for row in event_rows],
        }

    def delete_session(self, session_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            return cursor.rowcount > 0
