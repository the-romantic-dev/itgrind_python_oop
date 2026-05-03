from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from models.enums import AuditLevel
from models.errors import InvalidOperationError



@dataclass
class AuditEntry:
    level: AuditLevel | str
    event_type: str
    message: str
    data: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    entry_id: str = field(default_factory=lambda: f"audit_{uuid4().hex[:10]}")

    def __post_init__(self) -> None:
        self.level = self._coerce_level(self.level)

        if not isinstance(self.event_type, str) or not self.event_type.strip():
            raise InvalidOperationError("Audit event type cannot be empty")

        if not isinstance(self.message, str) or not self.message.strip():
            raise InvalidOperationError("Audit message cannot be empty")

        if self.data is None:
            self.data = {}

        if not isinstance(self.data, dict):
            raise InvalidOperationError("Audit data must be a dictionary")

    @staticmethod
    def _coerce_level(level: AuditLevel | str) -> AuditLevel:
        if isinstance(level, AuditLevel):
            return level

        if isinstance(level, str):
            normalized = level.lower().strip()

            for item in AuditLevel:
                if item.value.lower() == normalized or item.name.lower() == normalized:
                    return item

        raise InvalidOperationError(f"Invalid audit level: {level}")

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "level": self.level.value,
            "event_type": self.event_type,
            "message": self.message,
            "data": self._make_json_safe(self.data),
            "created_at": self.created_at.isoformat(),
        }

    def __str__(self) -> str:
        return (
            f"AuditEntry | "
            f"id={self.entry_id} | "
            f"level={self.level.value} | "
            f"type={self.event_type} | "
            f"message={self.message}"
        )

    @staticmethod
    def _make_json_safe(value):
        if isinstance(value, dict):
            return {
                str(key): AuditEntry._make_json_safe(item)
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [
                AuditEntry._make_json_safe(item)
                for item in value
            ]

        if isinstance(value, tuple):
            return [
                AuditEntry._make_json_safe(item)
                for item in value
            ]

        if isinstance(value, (datetime,)):
            return value.isoformat()

        if isinstance(value, Decimal):
            return str(value)

        if isinstance(value, UUID):
            return str(value)

        if hasattr(value, "value"):
            return value.value

        return value
    

class AuditLog:
    def __init__(
        self,
        file_path: str | Path | None = None,
        autosave: bool = False,
    ):
        self.entries: list[AuditEntry] = []
        self.file_path = Path(file_path) if file_path is not None else None
        self.autosave = autosave

    def log(
        self,
        level: AuditLevel | str,
        event_type: str,
        message: str,
        data: dict | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            level=level,
            event_type=event_type,
            message=message,
            data=data or {},
        )

        self.entries.append(entry)

        if self.autosave:
            if self.file_path is None:
                raise InvalidOperationError("Audit file path is not set")

            self.save_to_file(self.file_path)

        return entry

    def filter(
        self,
        level: AuditLevel | str | None = None,
        event_type: str | None = None,
        client_id: str | None = None,
        transaction_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[AuditEntry]:
        result = self.entries

        if level is not None:
            level = AuditEntry._coerce_level(level)
            result = [
                entry
                for entry in result
                if entry.level == level
            ]

        if event_type is not None:
            result = [
                entry
                for entry in result
                if entry.event_type == event_type
            ]

        if client_id is not None:
            result = [
                entry
                for entry in result
                if self._contains_value(entry.data, client_id)
            ]

        if transaction_id is not None:
            result = [
                entry
                for entry in result
                if self._contains_value(entry.data, transaction_id)
            ]

        if date_from is not None:
            result = [
                entry
                for entry in result
                if entry.created_at >= date_from
            ]

        if date_to is not None:
            result = [
                entry
                for entry in result
                if entry.created_at <= date_to
            ]

        return result

    def save_to_file(
        self,
        file_path: str | Path | None = None,
    ) -> Path:
        path = Path(file_path) if file_path is not None else self.file_path

        if path is None:
            raise InvalidOperationError("Audit file path is not set")

        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as file:
            json.dump(
                [entry.to_dict() for entry in self.entries],
                file,
                ensure_ascii=False,
                indent=4,
            )

        return path

    def get_suspicious_operations(self) -> list[dict]:
        suspicious_keywords = {
            "suspicious",
            "blocked",
            "security",
            "risk",
            "night",
        }

        result = []

        for entry in self.entries:
            text = f"{entry.event_type} {entry.message}".lower()

            if entry.level == AuditLevel.SECURITY:
                result.append(entry.to_dict())
                continue

            if any(keyword in text for keyword in suspicious_keywords):
                result.append(entry.to_dict())

        return result

    def get_error_statistics(self) -> dict:
        stats = {
            "total_errors": 0,
            "by_event_type": {},
            "by_level": {
                level.value: 0
                for level in AuditLevel
            },
        }

        for entry in self.entries:
            stats["by_level"][entry.level.value] += 1

            if entry.level == AuditLevel.ERROR:
                stats["total_errors"] += 1
                stats["by_event_type"][entry.event_type] = (
                    stats["by_event_type"].get(entry.event_type, 0) + 1
                )

        return stats

    def get_client_risk_profile(self, client_id: str) -> dict:
        client_entries = self.filter(client_id=client_id)

        profile = {
            "client_id": client_id,
            "total_events": len(client_entries),
            "security_events": 0,
            "warnings": 0,
            "errors": 0,
            "suspicious_events": [],
        }

        for entry in client_entries:
            if entry.level == AuditLevel.SECURITY:
                profile["security_events"] += 1
                profile["suspicious_events"].append(entry.to_dict())

            elif entry.level == AuditLevel.WARNING:
                profile["warnings"] += 1

            elif entry.level == AuditLevel.ERROR:
                profile["errors"] += 1

        return profile

    @staticmethod
    def _contains_value(data, target: str) -> bool:
        if isinstance(data, dict):
            return any(
                AuditLog._contains_value(value, target)
                for value in data.values()
            )

        if isinstance(data, list):
            return any(
                AuditLog._contains_value(value, target)
                for value in data
            )

        return str(data) == str(target)

    def to_dict(self) -> list[dict]:
        return [
            entry.to_dict()
            for entry in self.entries
        ]

    def __len__(self) -> int:
        return len(self.entries)
