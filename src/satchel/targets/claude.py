from __future__ import annotations

from pathlib import Path
from typing import Any

from satchel.core import Diagnostic, GeneratedFile, ManifestData, PortabilityFinding
from satchel.manifest import get_target
from satchel.targets.base import (
    BaseTargetAdapter,
    component_json_path,
    format_json,
    marketplace_config,
    marketplace_content,
    marketplace_patch_enabled,
    owner,
    require_fields,
    skill_marketplace_paths,
    title_from_name,
    validate_relative_reference,
)


class ClaudeAdapter(BaseTargetAdapter):
    name = "claude"
    enabled_by_default = True
    default_manifest_path = "./.claude-plugin/plugin.json"
    requires_marketplace_owner = True

    def outputs(self, root: Path, data: ManifestData) -> list[GeneratedFile]:
        if not self.enabled(data):
            return []
        outputs = [
            GeneratedFile(
                target="claude",
                path=self.manifest_path(root, data) or root / ".claude-plugin/plugin.json",
                content=format_json(_manifest(root, data)),
            )
        ]
        marketplace_path = self.marketplace_path(root, data)
        if marketplace_path:
            outputs.append(
                GeneratedFile(
                    target="claude-marketplace",
                    path=marketplace_path,
                    content=marketplace_content(
                        marketplace_path,
                        _marketplace(root, data),
                        str(data["name"]),
                        patch=marketplace_patch_enabled(data, "claude"),
                    ),
                    preserve_existing=marketplace_patch_enabled(data, "claude"),
                )
            )
        return outputs

    def report(self, root: Path, data: ManifestData) -> list[PortabilityFinding]:
        findings = super().report(root, data)
        if self.enabled(data):
            findings.extend(
                [
                    PortabilityFinding("claude", "skills", "native", "skills/ when declared"),
                    PortabilityFinding("claude", "commands", "native", "commands/ when declared"),
                    PortabilityFinding("claude", "agents", "native", "agents/ when declared"),
                    PortabilityFinding("claude", "mcp", "native", ".mcp.json default location"),
                    PortabilityFinding("claude", "hooks", "native", "hooks/hooks.json"),
                ]
            )
        return findings

    def validate_outputs(self, root: Path, data: ManifestData) -> list[Diagnostic]:
        if not self.enabled(data):
            return []
        path = self.manifest_path(root, data) or root / ".claude-plugin/plugin.json"
        manifest = _manifest(root, data)
        diagnostics = require_fields(
            manifest,
            ("name", "version", "description"),
            target="claude",
            path=path,
        )
        for field in ("skills", "commands", "agents", "hooks", "mcpServers", "lspServers"):
            if field not in manifest:
                continue
            diagnostic = validate_relative_reference(
                manifest[field],
                target="claude",
                field=field,
                path=path,
            )
            if diagnostic:
                diagnostics.append(diagnostic)
        return diagnostics


def _manifest(root: Path, data: ManifestData) -> dict[str, Any]:
    target = get_target(data, "claude")
    codex_interface = get_target(data, "codex").get("interface", {})
    if not isinstance(codex_interface, dict):
        codex_interface = {}
    display_name = (
        target.get("displayName")
        or target.get("display_name")
        or codex_interface.get("displayName")
        or title_from_name(str(data.get("name", "")))
    )

    manifest: dict[str, Any] = {
        "name": data["name"],
        "displayName": display_name,
        "version": data["version"],
        "description": data["description"],
    }
    author_data = owner(data)
    if author_data:
        manifest["author"] = author_data
    for field in ("homepage", "repository", "license", "keywords"):
        if field in data:
            manifest[field] = data[field]

    fields = (
        ("skills", "skills", True),
        ("commands", "commands", True),
        ("agents", "agents", True),
        ("hooks", "hooks", False),
        ("mcp", "mcpServers", False),
        ("lsp", "lspServers", False),
    )
    for component, manifest_field, trailing_slash in fields:
        value = component_json_path(root, data, component, trailing_slash=trailing_slash)
        if value:
            manifest[manifest_field] = value
    return manifest


def _marketplace(root: Path, data: ManifestData) -> dict[str, Any]:
    target = get_target(data, "claude")
    marketplace = marketplace_config(target)
    plugin: dict[str, Any] = {
        "name": data["name"],
        "source": marketplace.get("source", "./"),
        "description": data["description"],
        "version": data["version"],
    }
    display_name = target.get("displayName") or target.get("display_name")
    if display_name:
        plugin["displayName"] = display_name
    author_data = owner(data)
    if author_data:
        plugin["author"] = author_data
    for field in ("homepage", "repository", "license", "keywords"):
        if field in data:
            plugin[field] = data[field]

    category = marketplace.get("category")
    if category:
        plugin["category"] = category
    skills = skill_marketplace_paths(root, data)
    if skills:
        plugin["skills"] = skills

    result: dict[str, Any] = {
        "$schema": "https://docs.claude.com/schemas/claude-plugin-marketplace-v1.json",
        "name": marketplace.get("name", f"{data['name']}-marketplace"),
        "description": marketplace.get("description", data["description"]),
        "plugins": [plugin],
    }
    owner_data = owner(data)
    if owner_data:
        result["owner"] = owner_data
    return result
