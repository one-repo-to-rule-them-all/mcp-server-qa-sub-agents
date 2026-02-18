"""Shared AuditTrail schema for inter-agent coordination."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TechStackManifest:
    """Protocol emitted by the Inspector before generation begins."""

    backend_lang: str = "unknown"
    frontend_framework: str = "unknown"
    db_type: str = "unknown"
    auth_mechanism: str = "unknown"
    recommended_test_harness: str = "pytest"


@dataclass
class FailurePayload:
    """Failure payload consumed by the Healer loop."""

    error: str
    selector: str
    dom_snapshot: str
    traceback: str = ""


@dataclass
class AuditTrail:
    """Shared context schema used by all seven QA council agents."""

    session_id: str
    repo_url: str
    branch: str
    repo_path: str = ""
    manifest: TechStackManifest = field(default_factory=TechStackManifest)
    testable_surfaces: dict[str, Any] = field(default_factory=dict)
    generated_artifacts: list[dict[str, str]] = field(default_factory=list)
    executor_results: dict[str, Any] = field(default_factory=dict)
    failure_payloads: list[FailurePayload] = field(default_factory=list)
    repair_logs: list[str] = field(default_factory=list)
    quality_gate_report: dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Serialize audit trail and nested dataclasses to a JSON-ready dictionary."""
        payload = asdict(self)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AuditTrail":
        """Restore an AuditTrail instance from persisted JSON."""
        manifest_payload = payload.get("manifest", {}) or {}
        failures_payload = payload.get("failure_payloads", []) or []
        return cls(
            session_id=payload.get("session_id", ""),
            repo_url=payload.get("repo_url", ""),
            branch=payload.get("branch", "main"),
            repo_path=payload.get("repo_path", ""),
            manifest=TechStackManifest(**manifest_payload),
            testable_surfaces=payload.get("testable_surfaces", {}),
            generated_artifacts=payload.get("generated_artifacts", []),
            executor_results=payload.get("executor_results", {}),
            failure_payloads=[FailurePayload(**item) for item in failures_payload],
            repair_logs=payload.get("repair_logs", []),
            quality_gate_report=payload.get("quality_gate_report", {}),
            started_at=payload.get("started_at", datetime.now(timezone.utc).isoformat()),
            updated_at=payload.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )

