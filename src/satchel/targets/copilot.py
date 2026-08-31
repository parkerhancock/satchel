from __future__ import annotations

from pathlib import Path
from typing import Any

from satchel.core import Diagnostic, GeneratedFile, ManifestData, PortabilityFinding, SatchelError
from satchel.manifest import get_target, resolve_under_root
from satchel.targets.base import (
    BaseTargetAdapter,
    common_manifest,
    component_json_path,
    format_json,
    marketplace_config,
    marketplace_content,
    marketplace_patch_enabled,
    owner,
    require_fields,
    validate_relative_reference,
)


class CopilotAdapter(BaseTargetAdapter):
    name = "copilot"
    enabled_by_default = False
    default_manifest_path = "./.github/plugin/plugin.json"
    requires_marketplace_owner = True

    def validate(self, root: Path, data: ManifestData) -> list[Diagnostic]:
        diagnostics = super().validate(root, data)
        if not self.enabled(data):
            return diagnostics
        target = get_target(data, "copilot")
        root_manifest = target.get("rootManifest")
        if root_manifest is not None:
            diagnostics.extend(
                self._validate_path_field(root, root_manifest, "targets.copilot.rootManifest")
            )
        marketplace = target.get("marketplace")
        if isinstance(marketplace, dict):
            source = marketplace.get("source")
            if isinstance(source, dict) and "type" in source and "source" not in source:
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "targets.copilot.marketplace.source uses legacy 'type'; "
                        "use 'source' for the source discriminator",
                        "satchel.yaml",
                        code="SATCHEL_COPILOT_MARKETPLACE_SOURCE_LEGACY",
                        target="copilot",
                    )
                )
        return diagnostics

    def outputs(self, root: Path, data: ManifestData) -> list[GeneratedFile]:
        if not self.enabled(data):
            return []
        manifest = format_json(_manifest(root, data))
        outputs = [
            GeneratedFile(
                target="copilot",
                path=self.manifest_path(root, data) or root / ".github/plugin/plugin.json",
                content=manifest,
            )
        ]

        root_manifest_path = _root_manifest_path(root, data)
        if root_manifest_path:
            outputs.append(
                GeneratedFile(
                    target="copilot-root",
                    path=root_manifest_path,
                    content=manifest,
                )
            )

        marketplace_path = self.marketplace_path(root, data)
        if marketplace_path:
            outputs.append(
                GeneratedFile(
                    target="copilot-marketplace",
                    path=marketplace_path,
                    content=marketplace_content(
                        marketplace_path,
                        _marketplace(data),
                        str(data["name"]),
                        patch=marketplace_patch_enabled(data, "copilot"),
                    ),
                    preserve_existing=marketplace_patch_enabled(data, "copilot"),
                )
            )
        return outputs

    def report(self, root: Path, data: ManifestData) -> list[PortabilityFinding]:
        findings = super().report(root, data)
        if self.enabled(data):
            findings.extend(
                [
                    PortabilityFinding("copilot", "skills", "native", "skills/ when declared"),
                    PortabilityFinding("copilot", "agents", "native", "agents/ when declared"),
                    PortabilityFinding(
                        "copilot",
                        "hooks",
                        "approximated",
                        "hook path and plugin-root token differ from Claude",
                    ),
                    PortabilityFinding("copilot", "mcp", "native", ".mcp.json through mcpServers"),
                ]
            )
        return findings

    def validate_outputs(self, root: Path, data: ManifestData) -> list[Diagnostic]:
        if not self.enabled(data):
            return []
        path = self.manifest_path(root, data) or root / ".github/plugin/plugin.json"
        manifest = _manifest(root, data)
        diagnostics = require_fields(manifest, ("name",), target="copilot", path=path)
        for field in ("skills", "agents", "commands", "hooks", "mcpServers", "lspServers"):
            if field in manifest:
                diagnostic = validate_relative_reference(
                    manifest[field],
                    target="copilot",
                    field=field,
                    path=path,
                )
                if diagnostic:
                    diagnostics.append(diagnostic)
        return diagnostics


def _root_manifest_path(root: Path, data: ManifestData) -> Path | None:
    target = get_target(data, "copilot")
    raw_path = target.get("rootManifest")
    if raw_path is None:
        return None
    if not isinstance(raw_path, str):
        raise SatchelError("targets.copilot.rootManifest must be a path")
    return resolve_under_root(root, raw_path, label="targets.copilot.rootManifest")


def _manifest(root: Path, data: ManifestData) -> dict[str, Any]:
    target = get_target(data, "copilot")
    manifest = common_manifest(data)

    for field in ("category", "tags"):
        if field in target:
            manifest[field] = target[field]

    fields = (
        ("skills", "skills", True),
        ("agents", "agents", True),
        ("commands", "commands", True),
        ("hooks", "hooks", False),
        ("mcp", "mcpServers", False),
        ("lsp", "lspServers", False),
    )
    for component, manifest_field, trailing_slash in fields:
        value = component_json_path(root, data, component, trailing_slash=trailing_slash)
        if value:
            manifest[manifest_field] = value
    return manifest


def _marketplace(data: ManifestData) -> dict[str, Any]:
    target = get_target(data, "copilot")
    marketplace = marketplace_config(target)
    plugin: dict[str, Any] = {
        "name": data["name"],
        "description": data["description"],
        "version": data["version"],
        "source": _normalized_source(marketplace.get("source", "./")),
    }
    category = marketplace.get("category") or target.get("category")
    if category:
        plugin["category"] = category

    result: dict[str, Any] = {
        "name": marketplace.get("name", f"{data['name']}-marketplace"),
        "metadata": {
            "description": marketplace.get("description", data["description"]),
            "version": marketplace.get("version", data["version"]),
        },
        "plugins": [plugin],
    }
    owner_data = owner(data)
    if owner_data:
        result["owner"] = {
            key: value for key, value in owner_data.items() if key in {"name", "email"}
        }
    return result


def _normalized_source(source: Any) -> Any:
    if not isinstance(source, dict) or "source" in source or "type" not in source:
        return source
    normalized = dict(source)
    normalized["source"] = normalized.pop("type")
    return normalized
