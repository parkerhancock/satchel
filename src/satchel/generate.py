from __future__ import annotations

from pathlib import Path

from satchel.core import Diagnostic, GeneratedFile, ManifestData
from satchel.manifest import get_component_path
from satchel.targets import all_adapters, enabled_adapters


def build_outputs(
    root: Path, data: ManifestData, *, target: str | None = None
) -> list[GeneratedFile]:
    outputs: list[GeneratedFile] = []
    for adapter in enabled_adapters(data, target=target):
        outputs.extend(adapter.outputs(root, data))
    return outputs


def write_outputs(outputs: list[GeneratedFile]) -> None:
    for output in outputs:
        output.path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(output.content, bytes):
            output.path.write_bytes(output.content)
        else:
            output.path.write_text(output.content, encoding="utf-8")


def stale_outputs(outputs: list[GeneratedFile]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for output in outputs:
        if not output.path.exists():
            diagnostics.append(
                Diagnostic(
                    "error",
                    f"generated {output.target} output is missing",
                    str(output.path),
                    code="SATCHEL_GENERATED_MISSING",
                    target=output.target,
                )
            )
            continue
        current = (
            output.path.read_bytes()
            if isinstance(output.content, bytes)
            else output.path.read_text(encoding="utf-8")
        )
        if current != output.content:
            diagnostics.append(
                Diagnostic(
                    "error",
                    f"generated {output.target} output is stale",
                    str(output.path),
                    code="SATCHEL_GENERATED_STALE",
                    target=output.target,
                )
            )
    return diagnostics


def portability_report(root: Path, data: ManifestData) -> list[str]:
    lines = [
        f"package: {data.get('name', '<unknown>')}",
        f"schema: {data.get('schema', '<missing>')}",
        "",
        "targets:",
    ]
    for adapter in all_adapters():
        for finding in adapter.report(root, data):
            if finding.component == "manifest":
                lines.append(f"  {finding.target}: {finding.status} manifest -> {finding.detail}")
                break
            if finding.component == "target":
                lines.append(f"  {finding.target}: {finding.status} -> {finding.detail}")
                break

    lines.extend(["", "marketplaces:"])
    for adapter in all_adapters():
        lines.append(f"  {adapter.name}: {adapter.marketplace_installability(root, data)}")

    skills = get_component_path(data, "skills")
    mcp = get_component_path(data, "mcp")
    hooks = get_component_path(data, "hooks")
    lines.extend(["", "components:"])
    lines.append(f"  skills: {'portable skill directory declared' if skills else 'not declared'}")
    lines.append(f"  mcp: {'portable MCP config declared' if mcp else 'not declared'}")
    hook_status = "parsed only; behavioral parity not guaranteed" if hooks else "not declared"
    lines.append(f"  hooks: {hook_status}")
    return lines
