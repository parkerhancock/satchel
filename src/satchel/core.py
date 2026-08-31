from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SatchelError(Exception):
    """Raised when a package cannot be processed safely."""


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    message: str
    path: str | None = None
    code: str = "SATCHEL000"
    target: str | None = None
    component: str | None = None

    def format(self) -> str:
        prefix = f"{self.severity}: {self.code}: "
        if self.path:
            return f"{prefix}{self.path}: {self.message}"
        return f"{prefix}{self.message}"

    def to_json(self) -> dict[str, str]:
        data = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        if self.path:
            data["path"] = self.path
        if self.target:
            data["target"] = self.target
        if self.component:
            data["component"] = self.component
        return data


@dataclass(frozen=True)
class GeneratedFile:
    target: str
    path: Path
    content: str | bytes
    preserve_existing: bool = False


@dataclass(frozen=True)
class PortabilityFinding:
    target: str
    component: str
    status: str
    detail: str


ManifestData = dict[str, Any]
