from __future__ import annotations

from pathlib import Path

from satchel.core import Diagnostic, ManifestData
from satchel.host_validators import registered_host_validators
from satchel.targets import enabled_adapters


def structural_diagnostics(
    root: Path, data: ManifestData, *, target: str | None = None
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for adapter in enabled_adapters(data, target=target):
        diagnostics.extend(adapter.validate_outputs(root, data))
    return diagnostics


def marketplace_diagnostics(
    root: Path, data: ManifestData, *, release: bool = False, target: str | None = None
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for adapter in enabled_adapters(data, target=target):
        diagnostics.extend(adapter.marketplace_diagnostics(root, data, release=release))
    return diagnostics


def host_diagnostics(
    root: Path, data: ManifestData, *, timeout: int = 30, target: str | None = None
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    enabled = {adapter.name for adapter in enabled_adapters(data, target=target)}
    validators = {validator.target: validator for validator in registered_host_validators()}
    for name in sorted(enabled):
        validator = validators.get(name)
        if validator is not None:
            diagnostics.extend(validator.diagnostics(root, data=data, timeout=timeout))
    return diagnostics
