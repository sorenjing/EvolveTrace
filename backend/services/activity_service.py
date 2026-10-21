"""Cross-project audit queries; discovery remains in the Context component."""

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import re

from audit.activity import analyze_activity, rule_policy
from services.execution_evidence import resolve_execution_evidence
from audit.repository import AuditRepository
from audit.workspace import WorkspaceRepository
from services.evidence_worker import ExecutionEvidenceWorker


class ActivityService:
    def __init__(self, audit_repository: AuditRepository):
        self.repository = WorkspaceRepository(audit_repository.database_path)
        self.audit_repository = audit_repository
        self.evidence_worker = ExecutionEvidenceWorker(self.repository)

    @staticmethod
    def _public(project: dict) -> dict:
        return {**{key: value for key, value in project.items() if key != "workspace_root"}, "active": bool(project["active"])}

    def _project(self, project_id: str) -> dict:
        project = next((item for item in self.repository.projects() if item["project_id"] == project_id), None)
        if project is None:
            raise LookupError("registered project not found")
        return project

    def status(self, capture: dict, now: datetime | None = None) -> dict:
        last = capture["last_received_at"]
        state = "awaiting_events"
        if last is not None:
            age = ((now or datetime.now(timezone.utc)) - datetime.fromisoformat(last)).total_seconds()
            state = "receiving" if age <= 60 else "quiet"
        return {"schema_version": "activity-status/v1", **capture,
                "evidence_worker": self.evidence_worker.status(),
                "capture_state": state, "recent_seconds": 60,
                "stored_event_count": self.audit_repository.stored_event_count(),
                "registered_project_count": sum(bool(project["active"]) for project in self.repository.projects()),
                "coverage": "captured_hook_events_only"}

    @staticmethod
    def _locations(projects: list[dict]) -> list[tuple[Path, dict]]:
        return sorted((((Path(project["workspace_root"]) / project["relative_path"]).resolve(), project)
                       for project in projects if project["active"]), key=lambda item: len(item[0].parts), reverse=True)

    @staticmethod
    def _match(cwd: str, locations: list[tuple[Path, dict]]) -> dict | None:
        if not cwd or "\x00" in cwd or not Path(cwd).is_absolute():
            return None
        try:
            path = Path(cwd).resolve()
        except (OSError, ValueError):
            return None
        for root, project in locations:
            if path.is_relative_to(root):
                return project
        return None

    def _resolve_directories(self, events: list[dict]) -> tuple[list[dict], dict]:
        return resolve_execution_evidence(events, self.repository)

    def report(self, project_id: str | None = None, limit: int = 20000, session_id: str | None = None) -> dict:
        if not 1 <= limit <= 20000:
            raise ValueError("limit must be between 1 and 20000")
        projects = self.repository.projects()
        if project_id:
            self._project(project_id)
        events, truncated = self.repository.events(limit)
        # Preserve the global bounded scan: a filter must not silently expand it.
        if session_id is not None:
            events = [event for event in events if event["session_id"] == session_id]
        events, metadata_scan = self._resolve_directories(events)
        groups, unknown = defaultdict(list), 0
        sources = {"hook_cwd": 0, "tool_workdir": 0, "execution_record": 0}
        locations, directory_cache = self._locations(projects), {}
        # Match each event, not the session's initial directory: a session can
        # switch repositories, and those actions must not contaminate memory.
        for event in events:
            cwd = event["cwd"]
            if cwd not in directory_cache:
                directory_cache[cwd] = self._match(cwd, locations)
            project = directory_cache[cwd]
            if project is None:
                unknown += 1
            else:
                groups[project["project_id"]].append(event)
                sources[event["_directory_source"]] += 1
        result = []
        for project in projects:
            identity = project["project_id"]
            if project_id and identity != project_id:
                continue
            activity = analyze_activity(groups[identity])
            decisions = self.repository.decisions(identity)
            for finding in activity["findings"]:
                finding["suppressed"] = ("ignore", finding["finding_id"]) in decisions or ("mute", finding["code"]) in decisions
            activity["muted_rules"] = sorted(target for scope, target in decisions if scope == "mute")
            session_events = defaultdict(list)
            for event in groups[identity]:
                session_events[event["session_id"]].append(event)
            sessions = [{"session_id": sid, "event_count": len(items),
                         "started_at": min(item["timestamp"] for item in items),
                         "last_seen": max(item["timestamp"] for item in items)}
                        for sid, items in session_events.items()]
            sessions.sort(key=lambda item: (item["last_seen"], item["session_id"]), reverse=True)
            result.append({**self._public(project), "session_count": len(sessions),
                           "sessions": sessions, "activity": activity,
                           **({"event_ids": [event["event_id"] for event in groups[identity]]} if session_id is not None else {})})
        return {"schema_version": "workspace-activity/v1", "projects": result,
                "overall_activity": analyze_activity(events),
                "attribution_sources": sources, "execution_metadata_scan": metadata_scan,
                "observed_event_count": len(events), "unattributed_event_count": unknown,
                "event_limit": limit, "truncated": truncated, "coverage": "captured_hook_events_only",
                "scope": {"session_id": session_id, "project_id": project_id}, "rule_policy": rule_policy()}

    def decide(self, payload: dict) -> dict:
        project_id = str(payload.get("project_id", ""))
        self._project(project_id)
        action, code = payload.get("action"), payload.get("code")
        if not isinstance(action, str) or not isinstance(code, str) or action not in {"ignore", "mute", "unmute"} or code not in {"repeated_read", "repeated_build", "failed_retry"}:
            raise ValueError("invalid activity decision")
        if action == "unmute":
            self.repository.decide(project_id, "mute", code, remove=True)
        else:
            findings = self.report(project_id)["projects"][0]["activity"]["findings"]
            finding = next((item for item in findings if item["finding_id"] == payload.get("finding_id") and item["session_id"] == payload.get("session_id") and item["code"] == code), None)
            if finding is None:
                raise ValueError("finding is not present in captured project evidence")
            self.repository.decide(project_id, action, code if action == "mute" else finding["finding_id"])
        return {"project_id": project_id, "action": action, "code": code}

    def remember(self, payload: dict) -> dict:
        project_id = str(payload.get("project_id", ""))
        project = self._project(project_id)
        note, refs = payload.get("note"), payload.get("evidence_refs")
        if payload.get("confirmed") is not True:
            raise ValueError("audit memory requires explicit human confirmation")
        if not isinstance(note, str) or not note.strip() or len(note) > 1000:
            raise ValueError("reviewed note must contain 1 to 1000 characters")
        if not isinstance(refs, list) or not 1 <= len(refs) <= 20 or not all(isinstance(ref, str) for ref in refs):
            raise ValueError("memory requires 1 to 20 evidence references")
        session_id = str(payload.get("session_id", ""))
        events = self.repository.referenced_events(session_id, refs)
        events, _ = self._resolve_directories(events)
        locations = self._locations(self.repository.projects())
        valid = {event["event_id"] for event in events if (matched := self._match(event["cwd"], locations)) and matched["project_id"] == project["project_id"]}
        if not set(refs).issubset(valid):
            raise ValueError("evidence does not belong to the selected project/session")
        applicability = payload.get("applicability", "")
        if not isinstance(applicability, str) or len(applicability) > 300:
            raise ValueError("applicability must contain at most 300 characters")
        expiry = payload.get("expires_at")
        if expiry is not None:
            try:
                timestamp = datetime.fromisoformat(expiry)
                if timestamp.utcoffset() is None or timestamp <= datetime.now(timezone.utc):
                    raise ValueError("expiry must be a future timezone-aware timestamp")
                expiry = timestamp.astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid memory expiry") from exc
        supersedes = payload.get("supersedes")
        if supersedes is not None and (not isinstance(supersedes, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", supersedes)):
            raise ValueError("invalid replaced memory id")
        return self.repository.remember(project_id, session_id, note.strip(), list(dict.fromkeys(refs)),
                                        applicability=applicability.strip(), expires_at=expiry, supersedes=supersedes)

    def revoke_memory(self, memory_id: str, payload: dict) -> dict:
        project_id = str(payload.get("project_id", ""))
        self._project(project_id)
        if payload.get("confirmed") is not True:
            raise ValueError("revoking memory requires explicit human confirmation")
        return self.repository.revoke_memory(project_id, memory_id)

    def memory(self, project_id: str) -> dict:
        project = self._project(project_id)
        return {"schema_version": "audit-memory/v1", "project": self._public(project),
                "entries": self.repository.memory(project_id), "history": self.repository.memory(project_id, history=True),
                "recalls": self.repository.memory_recalls(project_id), "limit": 20,
                "authority": "human_reviewed_observation", "freshness": "historical"}

    def record_memory_recall(self, payload: dict) -> dict:
        fields = {"schema_version", "project_id", "reported_at", "trigger", "context_status", "context_freshness", "memory_ids", "truncated"}
        if set(payload) != fields or payload["schema_version"] != "audit-memory-recall/v1":
            raise ValueError("expected bounded audit-memory-recall/v1 report")
        self._project(payload["project_id"])
        at = payload["reported_at"]
        if not isinstance(at, str) or len(at) > 64:
            raise ValueError("reported_at must be a timezone-aware timestamp")
        try:
            timestamp = datetime.fromisoformat(at)
        except ValueError as exc:
            raise ValueError("reported_at must be a timezone-aware timestamp") from exc
        if timestamp.utcoffset() is None:
            raise ValueError("reported_at must be a timezone-aware timestamp")
        if payload["trigger"] not in ("manual", "SessionStart:startup", "SessionStart:resume", "SessionStart:compact", "SessionStart:clear", "SessionStart:unknown"):
            raise ValueError("invalid recall trigger")
        if payload["context_status"] not in ("returned", "partial", "blocked") or payload["context_freshness"] not in ("current", "stale", "new", "unknown", "missing"):
            raise ValueError("invalid context status or freshness")
        ids = payload["memory_ids"]
        if (not isinstance(ids, list) or len(ids) > 20
                or not all(isinstance(item, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", item) for item in ids)
                or len(set(ids)) != len(ids) or type(payload["truncated"]) is not bool):
            raise ValueError("invalid returned memory identifiers")
        return self.repository.record_memory_recall(payload)
