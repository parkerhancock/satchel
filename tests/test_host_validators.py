from __future__ import annotations

import subprocess
from pathlib import Path

from satchel.host_validators import (
    AntigravityHostValidator,
    CommandHostValidator,
    StructuralFallbackValidator,
    registered_host_validators,
)
from satchel.validate import host_diagnostics


def test_registered_host_validators_cover_known_targets() -> None:
    validators = {validator.target: validator for validator in registered_host_validators()}
    assert set(validators) == {
        "antigravity",
        "claude",
        "codex",
        "copilot",
    }
    assert isinstance(validators["antigravity"], AntigravityHostValidator)


def test_command_validator_runs_non_mutating_command(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    validator = CommandHostValidator(
        target="example",
        command=("example", "validate", "{root}"),
    )

    def fake_runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    diagnostics = validator.diagnostics(
        tmp_path,
        timeout=3,
        which=lambda name: f"/bin/{name}",
        runner=fake_runner,
    )

    assert diagnostics == []
    assert calls == [["example", "validate", str(tmp_path)]]


def test_command_validator_reports_missing_cli(tmp_path: Path) -> None:
    validator = CommandHostValidator(
        target="example",
        command=("example", "validate", "{root}"),
    )

    diagnostics = validator.diagnostics(tmp_path, timeout=3, which=lambda name: None)

    assert diagnostics[0].code == "SATCHEL_HOST_CLI_MISSING"
    assert diagnostics[0].target == "example"


def test_command_validator_reports_failure_output(tmp_path: Path) -> None:
    validator = CommandHostValidator(
        target="example",
        command=("example", "validate", "{root}"),
    )

    def fake_runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 2, "bad stdout", "bad stderr")

    diagnostics = validator.diagnostics(
        tmp_path,
        timeout=3,
        which=lambda name: f"/bin/{name}",
        runner=fake_runner,
    )

    assert diagnostics[0].code == "SATCHEL_HOST_VALIDATOR_FAILED"
    assert "bad stdout" in diagnostics[0].message
    assert "bad stderr" in diagnostics[0].message


def test_antigravity_validator_uses_generated_plugin_directory(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    validator = AntigravityHostValidator()
    data = {
        "name": "demo-plugin",
        "targets": {
            "antigravity": {
                "enabled": True,
                "output": "./.agents/plugins/demo-plugin",
            }
        },
    }

    def fake_runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    diagnostics = validator.diagnostics(
        tmp_path,
        data=data,
        timeout=3,
        which=lambda name: f"/bin/{name}" if name == "agy" else None,
        runner=fake_runner,
    )

    assert diagnostics == []
    assert calls == [["agy", "plugin", "validate", str(tmp_path / ".agents/plugins/demo-plugin")]]


def test_structural_fallback_distinguishes_missing_and_unavailable_cli(tmp_path: Path) -> None:
    validator = StructuralFallbackValidator(
        target="example",
        command_names=("example",),
        unavailable_message="example has no validator",
        missing_message="example is missing",
    )

    missing = validator.diagnostics(tmp_path, timeout=3, which=lambda name: None)
    unavailable = validator.diagnostics(tmp_path, timeout=3, which=lambda name: f"/bin/{name}")

    assert missing[0].code == "SATCHEL_HOST_CLI_MISSING"
    assert unavailable[0].code == "SATCHEL_HOST_VALIDATOR_UNAVAILABLE"


def test_host_diagnostics_filters_target(tmp_path: Path) -> None:
    data = {
        "schema": "satchel/v0",
        "name": "demo",
        "version": "0.1.0",
        "description": "Demo",
        "targets": {
            "codex": {"enabled": True},
            "claude": {"enabled": True},
            "copilot": {"enabled": False},
        },
    }

    diagnostics = host_diagnostics(tmp_path, data, target="codex")

    assert diagnostics
    assert {diagnostic.target for diagnostic in diagnostics} == {"codex"}
