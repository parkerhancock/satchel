from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from satchel.core import Diagnostic, ManifestData
from satchel.targets.antigravity import antigravity_output_root

Which = Callable[[str], str | None]
Runner = Callable[..., subprocess.CompletedProcess[str]]


class HostValidatorPlugin(Protocol):
    target: str

    def diagnostics(
        self,
        root: Path,
        *,
        data: ManifestData | None = None,
        timeout: int,
        which: Which = shutil.which,
        runner: Runner = subprocess.run,
    ) -> list[Diagnostic]: ...


@dataclass(frozen=True)
class CommandHostValidator:
    target: str
    command: tuple[str, ...]
    missing_message: str | None = None

    def diagnostics(
        self,
        root: Path,
        *,
        data: ManifestData | None = None,
        timeout: int,
        which: Which = shutil.which,
        runner: Runner = subprocess.run,
    ) -> list[Diagnostic]:
        del data
        if not which(self.command[0]):
            message = self.missing_message or f"{self.target} validator not found; skipped"
            return [
                Diagnostic(
                    "warning",
                    message,
                    self.target,
                    code="SATCHEL_HOST_CLI_MISSING",
                    target=self.target,
                )
            ]

        command = [part.format(root=str(root)) for part in self.command]
        try:
            result = runner(
                command,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return [
                Diagnostic(
                    "error",
                    f"{self.target} validator timed out after {timeout}s",
                    self.target,
                    code="SATCHEL_HOST_VALIDATOR_TIMEOUT",
                    target=self.target,
                )
            ]

        output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        if result.returncode != 0:
            message = f"{self.target} validator failed"
            if output:
                message = f"{message}: {output}"
            return [
                Diagnostic(
                    "error",
                    message,
                    self.target,
                    code="SATCHEL_HOST_VALIDATOR_FAILED",
                    target=self.target,
                )
            ]
        return []


@dataclass(frozen=True)
class StructuralFallbackValidator:
    target: str
    unavailable_message: str
    command_names: tuple[str, ...] = ()
    missing_message: str | None = None

    def diagnostics(
        self,
        root: Path,
        *,
        data: ManifestData | None = None,
        timeout: int,
        which: Which = shutil.which,
        runner: Runner = subprocess.run,
    ) -> list[Diagnostic]:
        del root, data, timeout, runner
        if self.command_names and not any(which(name) for name in self.command_names):
            return [
                Diagnostic(
                    "warning",
                    self.missing_message
                    or f"{self.target} CLI not found; structural checks were used",
                    self.target,
                    code="SATCHEL_HOST_CLI_MISSING",
                    target=self.target,
                )
            ]
        return [
            Diagnostic(
                "warning",
                self.unavailable_message,
                self.target,
                code="SATCHEL_HOST_VALIDATOR_UNAVAILABLE",
                target=self.target,
            )
        ]


@dataclass(frozen=True)
class AntigravityHostValidator:
    target: str = "antigravity"

    def diagnostics(
        self,
        root: Path,
        *,
        data: ManifestData | None = None,
        timeout: int,
        which: Which = shutil.which,
        runner: Runner = subprocess.run,
    ) -> list[Diagnostic]:
        executable = next((name for name in ("agy", "antigravity") if which(name)), None)
        if executable is None:
            return [
                Diagnostic(
                    "warning",
                    "antigravity CLI not found; structural checks were used",
                    self.target,
                    code="SATCHEL_HOST_CLI_MISSING",
                    target=self.target,
                )
            ]

        plugin_root = antigravity_output_root(root, data) if data is not None else root
        validator = CommandHostValidator(
            target=self.target,
            command=(executable, "plugin", "validate", "{root}"),
        )
        return validator.diagnostics(
            plugin_root,
            timeout=timeout,
            which=which,
            runner=runner,
        )


def registered_host_validators() -> tuple[HostValidatorPlugin, ...]:
    return (
        CommandHostValidator(
            target="claude",
            command=("claude", "plugin", "validate", "{root}"),
            missing_message="claude validator not found; skipped",
        ),
        StructuralFallbackValidator(
            target="codex",
            unavailable_message=(
                "codex has no non-mutating plugin validator; structural checks were used"
            ),
        ),
        StructuralFallbackValidator(
            target="copilot",
            command_names=("copilot",),
            unavailable_message=(
                "copilot CLI is installed, but no non-mutating plugin validator is documented; "
                "structural checks were used"
            ),
            missing_message="copilot CLI not found; structural checks were used",
        ),
        AntigravityHostValidator(),
    )
