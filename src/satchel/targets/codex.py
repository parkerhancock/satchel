from __future__ import annotations

from pathlib import Path
from typing import Any

from satchel.core import Diagnostic, GeneratedFile, ManifestData, PortabilityFinding
from satchel.manifest import get_target, resolve_under_root
from satchel.targets.base import (
    BaseTargetAdapter,
    common_manifest,
    component_json_path,
    format_json,
    marketplace_config,
    marketplace_content,
    marketplace_patch_enabled,
    require_fields,
    title_from_name,
    validate_relative_reference,
)


class CodexAdapter(BaseTargetAdapter):
    name = "codex"
    enabled_by_default = True
    default_manifest_path = "./.codex-plugin/plugin.json"

    def outputs(self, root: Path, data: ManifestData) -> list[GeneratedFile]:
        if not self.enabled(data):
            return []
        outputs = [
            GeneratedFile(
                target="codex",
                path=self.manifest_path(root, data) or root / ".codex-plugin/plugin.json",
                content=format_json(_manifest(root, data)),
            )
        ]
        marketplace_path = self.marketplace_path(root, data)
        if marketplace_path:
            outputs.append(
                GeneratedFile(
                    target="codex-marketplace",
                    path=marketplace_path,
                    content=marketplace_content(
                        marketplace_path,
                        _marketplace(data),
                        str(data["name"]),
                        patch=marketplace_patch_enabled(data, "codex"),
                    ),
                    preserve_existing=marketplace_patch_enabled(data, "codex"),
                )
            )
        return outputs

    def report(self, root: Path, data: ManifestData) -> list[PortabilityFinding]:
        findings = super().report(root, data)
        if self.enabled(data):
            findings.extend(
                [
                    PortabilityFinding("codex", "skills", "native", "skills/ when declared"),
                    PortabilityFinding("codex", "mcp", "native", ".mcp.json through mcpServers"),
                    PortabilityFinding(
                        "codex",
                        "hooks",
                        "approximated",
                        "plugin hooks require host feature flag",
                    ),
                    PortabilityFinding("codex", "apps", "native", ".app.json when declared"),
                ]
            )
        return findings

    def validate_outputs(self, root: Path, data: ManifestData) -> list[Diagnostic]:
        if not self.enabled(data):
            return []
        path = self.manifest_path(root, data) or root / ".codex-plugin/plugin.json"
        manifest = _manifest(root, data)
        diagnostics = require_fields(
            manifest,
            ("name", "version", "description"),
            target="codex",
            path=path,
        )
        for field in ("skills", "mcpServers", "apps", "hooks"):
            if field in manifest:
                diagnostic = validate_relative_reference(
                    manifest[field],
                    target="codex",
                    field=field,
                    path=path,
                )
                if diagnostic:
                    diagnostics.append(diagnostic)
        if "interface" in manifest and not isinstance(manifest["interface"], dict):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "codex interface must be an object",
                    str(path),
                    code="SATCHEL_OUTPUT_FIELD_TYPE",
                    target="codex",
                    component="interface",
                )
            )
        return diagnostics


def _manifest(root: Path, data: ManifestData) -> dict[str, Any]:
    target = get_target(data, "codex")
    interface = target.get("interface", {})
    if not isinstance(interface, dict):
        interface = {}

    manifest_path = _manifest_path(root, data)
    plugin_root = manifest_path.parent.parent
    manifest = common_manifest(data)
    skills = component_json_path(
        root,
        data,
        "skills",
        relative_to=plugin_root,
        trailing_slash=True,
    )
    if skills:
        manifest["skills"] = skills
    mcp = component_json_path(root, data, "mcp", relative_to=plugin_root)
    if mcp:
        manifest["mcpServers"] = mcp
    apps = component_json_path(root, data, "apps", relative_to=plugin_root)
    if apps:
        manifest["apps"] = apps
    hooks = component_json_path(root, data, "hooks", relative_to=plugin_root)
    if hooks:
        manifest["hooks"] = hooks

    codex_interface = _interface(data, interface)
    if codex_interface:
        manifest["interface"] = codex_interface
    return manifest


def _manifest_path(root: Path, data: ManifestData) -> Path:
    target = get_target(data, "codex")
    raw_path = target.get("manifest", "./.codex-plugin/plugin.json")
    if not isinstance(raw_path, str):
        raw_path = "./.codex-plugin/plugin.json"
    return resolve_under_root(root, raw_path, label="targets.codex.manifest")


def _marketplace(data: ManifestData) -> dict[str, Any]:
    target = get_target(data, "codex")
    marketplace = marketplace_config(target)
    interface = target.get("interface", {})
    if not isinstance(interface, dict):
        interface = {}

    display_name = interface.get("displayName") or title_from_name(str(data.get("name", "")))
    return {
        "name": marketplace.get("name", f"{data['name']}-marketplace"),
        "interface": {
            "displayName": marketplace.get("displayName", display_name),
        },
        "plugins": [
            {
                "name": data["name"],
                "source": marketplace.get("source", {"source": "local", "path": "./"}),
                "policy": {
                    "installation": marketplace.get("installation", "AVAILABLE"),
                    "authentication": marketplace.get("authentication", "ON_INSTALL"),
                },
                "category": marketplace.get("category", interface.get("category", "Productivity")),
            }
        ],
    }


def _interface(data: ManifestData, interface: dict[str, Any]) -> dict[str, Any]:
    author = data.get("author")
    author_name = author.get("name") if isinstance(author, dict) else author
    result: dict[str, Any] = {}
    defaults = {
        "displayName": title_from_name(str(data.get("name", ""))),
        "shortDescription": data.get("description"),
        "developerName": author_name,
        "category": "Productivity",
    }

    for field, default in defaults.items():
        value = interface.get(field, default)
        if value:
            result[field] = value

    for field in (
        "longDescription",
        "capabilities",
        "websiteURL",
        "privacyPolicyURL",
        "termsOfServiceURL",
        "defaultPrompt",
        "brandColor",
        "composerIcon",
        "logo",
        "screenshots",
    ):
        if field in interface:
            result[field] = interface[field]
    return result
