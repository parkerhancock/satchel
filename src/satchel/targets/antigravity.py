from __future__ import annotations

from pathlib import Path

from satchel.core import Diagnostic, GeneratedFile, ManifestData, PortabilityFinding
from satchel.manifest import get_target, resolve_under_root
from satchel.targets.base import (
    BaseTargetAdapter,
    component_path,
    copied_tree_outputs,
    format_json,
    json_component_content,
)


class AntigravityAdapter(BaseTargetAdapter):
    name = "antigravity"
    enabled_by_default = False
    default_manifest_path = None
    supports_marketplace = False

    def validate(self, root: Path, data: ManifestData) -> list[Diagnostic]:
        diagnostics = super().validate(root, data)
        if not self.enabled(data):
            return diagnostics
        target = get_target(data, "antigravity")
        raw_output = target.get("output", f"./.agents/plugins/{data.get('name', 'plugin')}")
        diagnostics.extend(
            self._validate_path_field(root, raw_output, "targets.antigravity.output")
        )
        return diagnostics

    def outputs(self, root: Path, data: ManifestData) -> list[GeneratedFile]:
        if not self.enabled(data):
            return []
        output_root = antigravity_output_root(root, data)
        outputs = [
            GeneratedFile(
                target="antigravity",
                path=output_root / "plugin.json",
                content=format_json(
                    {
                        "$schema": "https://antigravity.google/schemas/v1/plugin.json",
                        "name": data["name"],
                        "description": data["description"],
                    }
                ),
            )
        ]

        mcp_content = json_component_content(root, data, "mcp")
        if mcp_content:
            outputs.append(
                GeneratedFile(
                    target="antigravity-mcp",
                    path=output_root / "mcp_config.json",
                    content=mcp_content,
                )
            )

        hooks_content = json_component_content(root, data, "hooks")
        if hooks_content:
            outputs.append(
                GeneratedFile(
                    target="antigravity-hooks",
                    path=output_root / "hooks.json",
                    content=hooks_content,
                )
            )

        for component in ("skills", "agents", "rules"):
            outputs.extend(
                copied_tree_outputs(
                    f"antigravity-{component}",
                    root,
                    component_path(root, data, component),
                    output_root / component,
                )
            )
        return outputs

    def report(self, root: Path, data: ManifestData) -> list[PortabilityFinding]:
        if not self.enabled(data):
            return super().report(root, data)
        output_root = antigravity_output_root(root, data)
        return [
            PortabilityFinding(
                "antigravity",
                "target",
                "generated",
                output_root.relative_to(root).as_posix(),
            ),
            PortabilityFinding(
                "antigravity",
                "mcp",
                "generated",
                ".mcp.json is transformed to mcp_config.json when declared",
            ),
            PortabilityFinding(
                "antigravity",
                "hooks",
                "approximated",
                "hook events differ from Codex, Claude, and Copilot",
            ),
            PortabilityFinding(
                "antigravity",
                "marketplace",
                "unsupported",
                "install/update marketplace behavior still needs host verification",
            ),
        ]

    def validate_outputs(self, root: Path, data: ManifestData) -> list[Diagnostic]:
        if not self.enabled(data):
            return []
        target = get_target(data, "antigravity")
        diagnostics: list[Diagnostic] = []
        if target.get("experimental") is not True:
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "antigravity target should be marked experimental: true",
                    "satchel.yaml",
                    code="SATCHEL_TARGET_EXPERIMENTAL_UNMARKED",
                    target="antigravity",
                )
            )
        output_root = antigravity_output_root(root, data)
        try:
            output_root.relative_to(root / ".agents/plugins")
        except ValueError:
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "antigravity output is usually expected under ./.agents/plugins/",
                    str(output_root),
                    code="SATCHEL_OUTPUT_PATH_STYLE",
                    target="antigravity",
                )
            )
        return diagnostics


def antigravity_output_root(root: Path, data: ManifestData) -> Path:
    target = get_target(data, "antigravity")
    raw_output = target.get("output", f"./.agents/plugins/{data['name']}")
    if not isinstance(raw_output, str):
        raw_output = f"./.agents/plugins/{data['name']}"
    return resolve_under_root(root, raw_output, label="targets.antigravity.output")
