from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from satchel.core import Diagnostic, GeneratedFile, ManifestData, PortabilityFinding, SatchelError
from satchel.manifest import get_component_path, get_target, resolve_under_root
from satchel.targets.base import (
    BaseTargetAdapter,
    component_json_path,
    component_path,
    format_json,
    require_fields,
    title_from_name,
)

# Deterministic namespace for the plugin GUID Satchel derives when
# targets.cowork.id is not set, mirroring the "deterministic UUID v5" the
# Microsoft-authored Convert-ClaudePluginToMOS3.ps1 conversion script uses.
_COWORK_GUID_NAMESPACE = uuid.UUID("6f6e0c9a-6e6d-4f7e-9d6b-6f6f6c6f726b")


class CoworkAdapter(BaseTargetAdapter):
    """Microsoft 365 Copilot Cowork plugin target.

    A Cowork plugin manifest can bundle skills, but its connectors are
    references to an already-running *remote* MCP server declared under
    ``targets.cowork.connector`` -- there is no local/stdio transport, and
    nothing here converts one. If the package's ``mcp`` component declares a
    stdio server (a ``command``, not a ``url``), that entry cannot back a
    Cowork connector as-is; validation flags it rather than silently
    dropping it or guessing at a URL.
    """

    name = "cowork"
    enabled_by_default = False
    default_manifest_path = "./cowork/manifest.json"
    supports_marketplace = False

    def validate(self, root: Path, data: ManifestData) -> list[Diagnostic]:
        diagnostics = super().validate(root, data)
        if not self.enabled(data):
            return diagnostics

        target = get_target(data, "cowork")
        connector = target.get("connector")
        if connector is not None and not isinstance(connector, dict):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "targets.cowork.connector must be a mapping",
                    "satchel.yaml",
                    code="SATCHEL_TARGET_FIELD_TYPE",
                    target="cowork",
                    component="connector",
                )
            )

        developer = target.get("developer")
        if not isinstance(developer, dict):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "targets.cowork.developer must be a mapping with required "
                    "Microsoft 365 app metadata",
                    "satchel.yaml",
                    code="SATCHEL_TARGET_FIELD_TYPE",
                    target="cowork",
                    component="developer",
                )
            )
        else:
            diagnostics.extend(
                _required_mapping_fields(
                    developer,
                    ("name", "websiteUrl", "privacyUrl", "termsOfUseUrl"),
                    component="developer",
                )
            )

        icons = target.get("icons")
        if not isinstance(icons, dict):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "targets.cowork.icons must be a mapping with outline and color paths",
                    "satchel.yaml",
                    code="SATCHEL_TARGET_FIELD_TYPE",
                    target="cowork",
                    component="icons",
                )
            )
        else:
            diagnostics.extend(
                _required_mapping_fields(icons, ("outline", "color"), component="icons")
            )
            for field in ("outline", "color"):
                raw_path = icons.get(field)
                if not isinstance(raw_path, str) or not raw_path.strip():
                    continue
                try:
                    icon_path = resolve_under_root(
                        root, raw_path, label=f"targets.cowork.icons.{field}"
                    )
                except SatchelError as exc:
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            str(exc),
                            "satchel.yaml",
                            code="SATCHEL_PATH_INVALID",
                            target="cowork",
                            component=field,
                        )
                    )
                    continue
                if not icon_path.is_file():
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            f"targets.cowork.icons.{field} does not exist: {raw_path}",
                            raw_path,
                            code="SATCHEL_COMPONENT_PATH_MISSING",
                            target="cowork",
                            component=field,
                        )
                    )

        accent_color = target.get("accentColor")
        if not isinstance(accent_color, str) or not re.fullmatch(
            r"#[0-9A-Fa-f]{6}", accent_color
        ):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "targets.cowork.accentColor must be a six-digit HTML hex color",
                    "satchel.yaml",
                    code="SATCHEL_COWORK_ACCENT_COLOR_INVALID",
                    target="cowork",
                    component="accentColor",
                )
            )

        diagnostics.extend(_flag_non_remote_mcp_servers(root, data))
        return diagnostics

    def outputs(self, root: Path, data: ManifestData) -> list[GeneratedFile]:
        if not self.enabled(data):
            return []
        return [
            GeneratedFile(
                target="cowork",
                path=self.manifest_path(root, data) or root / "cowork/manifest.json",
                content=format_json(_manifest(root, data)),
            )
        ]

    def report(self, root: Path, data: ManifestData) -> list[PortabilityFinding]:
        findings = super().report(root, data)
        if not self.enabled(data):
            return findings

        skills_path = get_component_path(data, "skills")
        findings.append(
            PortabilityFinding(
                "cowork",
                "skills",
                "native" if skills_path else "ignored",
                "SKILL.md copied verbatim into agentSkills[]"
                if skills_path
                else "no skills component declared",
            )
        )

        connector = get_target(data, "cowork").get("connector", {})
        mcp_url = connector.get("mcpServerUrl") if isinstance(connector, dict) else None
        if isinstance(mcp_url, str) and mcp_url.strip():
            findings.append(
                PortabilityFinding(
                    "cowork",
                    "mcp",
                    "native",
                    "remote MCP server declared in targets.cowork.connector.mcpServerUrl",
                )
            )
        elif _local_mcp_servers(root, data):
            findings.append(
                PortabilityFinding(
                    "cowork",
                    "mcp",
                    "blocked",
                    "local mcp component has no remote HTTP server; Cowork's "
                    "agentConnectors has no local/stdio transport to fall back to",
                )
            )
        return findings

    def validate_outputs(self, root: Path, data: ManifestData) -> list[Diagnostic]:
        if not self.enabled(data):
            return []
        path = self.manifest_path(root, data) or root / "cowork/manifest.json"
        manifest = _manifest(root, data)
        diagnostics = require_fields(
            {
                "id": manifest.get("id"),
                "version": manifest.get("version"),
            },
            ("id", "version"),
            target="cowork",
            path=path,
        )

        for field in ("developer", "icons"):
            if not isinstance(manifest.get(field), dict) or not manifest[field]:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        f"cowork output {field} must be a non-empty object",
                        str(path),
                        code="SATCHEL_OUTPUT_FIELD_MISSING",
                        target="cowork",
                        component=field,
                    )
                )
        accent_color = manifest.get("accentColor")
        if not isinstance(accent_color, str) or not accent_color:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "cowork output accentColor must be a non-empty string",
                    str(path),
                    code="SATCHEL_OUTPUT_FIELD_MISSING",
                    target="cowork",
                    component="accentColor",
                )
            )

        name_block = manifest.get("name")
        description_block = manifest.get("description")
        for label, block in (("name", name_block), ("description", description_block)):
            if not isinstance(block, dict) or not all(
                isinstance(block.get(key), str) and block[key].strip()
                for key in ("short", "full")
            ):
                diagnostics.append(
                    Diagnostic(
                        "error",
                        f"cowork output {label} must have non-empty 'short' and 'full' strings",
                        str(path),
                        code="SATCHEL_OUTPUT_FIELD_MISSING",
                        target="cowork",
                        component=label,
                    )
                )

        connectors = manifest.get("agentConnectors")
        if isinstance(connectors, list):
            for entry in connectors:
                if not isinstance(entry, dict):
                    continue
                url = entry.get("toolSource", {}).get("remoteMcpServer", {}).get("mcpServerUrl")
                if isinstance(url, str) and url and not _is_https_url(url):
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "cowork connector mcpServerUrl must be HTTPS -- Cowork's "
                            "transport contract requires Streamable HTTP over TLS 1.2+",
                            str(path),
                            code="SATCHEL_COWORK_MCP_NOT_HTTPS",
                            target="cowork",
                            component="mcpServerUrl",
                        )
                    )
        return diagnostics


def _manifest(root: Path, data: ManifestData) -> dict[str, Any]:
    target = get_target(data, "cowork")
    display_name = (
        target.get("displayName") or title_from_name(str(data.get("name", "")))
    )
    description = str(data.get("description", ""))

    plugin_id = target.get("id") or str(
        uuid.uuid5(_COWORK_GUID_NAMESPACE, str(data.get("name", "")))
    )
    manifest: dict[str, Any] = {
        "$schema": "https://developer.microsoft.com/json-schemas/teams/v1.28/MicrosoftTeams.schema.json",
        "manifestVersion": "1.28",
        "id": plugin_id,
        "version": data["version"],
        "name": {
            "short": target.get("name", {}).get("short", display_name)
            if isinstance(target.get("name"), dict)
            else display_name,
            "full": target.get("name", {}).get("full", display_name)
            if isinstance(target.get("name"), dict)
            else display_name,
        },
        "description": {
            "short": target.get("description", {}).get("short", description)
            if isinstance(target.get("description"), dict)
            else description,
            "full": target.get("description", {}).get("full", description)
            if isinstance(target.get("description"), dict)
            else description,
        },
    }

    developer = target.get("developer")
    if isinstance(developer, dict) and developer:
        manifest["developer"] = developer

    icons = target.get("icons")
    if isinstance(icons, dict) and icons:
        manifest["icons"] = icons

    accent_color = target.get("accentColor")
    if isinstance(accent_color, str) and accent_color:
        manifest["accentColor"] = accent_color

    skills = component_json_path(root, data, "skills", trailing_slash=False)
    if skills:
        manifest["agentSkills"] = [{"folder": skills}]

    connector = _connector(data)
    if connector:
        manifest["agentConnectors"] = [connector]

    return manifest


def _connector(data: ManifestData) -> dict[str, Any] | None:
    target = get_target(data, "cowork")
    raw_connector = target.get("connector")
    connector = raw_connector if isinstance(raw_connector, dict) else {}
    mcp_url = connector.get("mcpServerUrl")
    if not isinstance(mcp_url, str) or not mcp_url.strip():
        return None

    tool_source: dict[str, Any] = {"remoteMcpServer": {"mcpServerUrl": mcp_url}}
    auth_type = connector.get("authType", "None")
    if auth_type and auth_type != "None":
        authorization: dict[str, Any] = {"type": auth_type}
        reference_id = connector.get("referenceId")
        if reference_id:
            authorization["referenceId"] = reference_id
        tool_source["remoteMcpServer"]["authorization"] = authorization

    result: dict[str, Any] = {
        "id": connector.get("id") or data["name"],
        "displayName": connector.get("displayName") or title_from_name(str(data.get("name", ""))),
        "toolSource": tool_source,
    }
    description = connector.get("description")
    if description:
        result["description"] = description
    return result


def _local_mcp_servers(root: Path, data: ManifestData) -> dict[str, Any]:
    """Read the package's mcp component file and return its declared servers.

    Returns an empty dict if there's no mcp component, the file is missing,
    or it doesn't parse -- this is a best-effort read for diagnostics, not a
    structural validator (``_validate_component_paths`` already covers
    existence/type errors for the component path itself).
    """
    mcp_path = component_path(root, data, "mcp")
    if mcp_path is None or not mcp_path.is_file():
        return {}
    try:
        parsed = json.loads(mcp_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    servers = parsed.get("mcpServers") if isinstance(parsed, dict) else None
    return servers if isinstance(servers, dict) else {}


def _flag_non_remote_mcp_servers(root: Path, data: ManifestData) -> list[Diagnostic]:
    servers = _local_mcp_servers(root, data)
    if not servers:
        return []

    mcp_component_path = get_component_path(data, "mcp") or "the mcp component"
    diagnostics: list[Diagnostic] = []
    for server_name, entry in servers.items():
        if not isinstance(entry, dict):
            continue
        url = entry.get("url")
        if isinstance(url, str) and url.strip():
            continue  # remote-shaped entry; Cowork's HTTPS requirement is checked separately
        if "command" in entry:
            diagnostics.append(
                Diagnostic(
                    "error",
                    f"mcp server {server_name!r} in {mcp_component_path} is declared via a "
                    "local command (stdio) -- Cowork's agentConnectors only supports a "
                    "remoteMcpServer with an HTTPS mcpServerUrl. Deploy this server "
                    "remotely and configure targets.cowork.connector.mcpServerUrl to "
                    "point at it; the local declaration cannot be converted automatically.",
                    mcp_component_path,
                    code="SATCHEL_COWORK_MCP_NOT_REMOTE",
                    target="cowork",
                    component=server_name,
                )
            )
    return diagnostics


def _is_https_url(value: str) -> bool:
    return value.startswith("https://")


def _required_mapping_fields(
    mapping: dict[str, Any], fields: tuple[str, ...], *, component: str
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for field in fields:
        value = mapping.get(field)
        if isinstance(value, str) and value.strip():
            continue
        diagnostics.append(
            Diagnostic(
                "error",
                f"targets.cowork.{component}.{field} is required",
                "satchel.yaml",
                code="SATCHEL_COWORK_FIELD_MISSING",
                target="cowork",
                component=field,
            )
        )
    return diagnostics
