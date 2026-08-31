from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

from satchel.core import Diagnostic, GeneratedFile, ManifestData, PortabilityFinding, SatchelError
from satchel.manifest import get_target, resolve_under_root
from satchel.targets.base import BaseTargetAdapter, format_json, require_fields, title_from_name


class AnthropicAdapter(BaseTargetAdapter):
    """Anthropic Connectors Directory submission target.

    This is NOT the Claude Code plugin target (that is ``claude``). The
    Connectors Directory lists a *remote MCP server* in Claude's connector
    catalog and is submitted through a manual review flow. This adapter emits
    the connector metadata plus a submission checklist; it does not produce an
    install manifest, because the Directory has no self-serve upload format.
    """

    name = "anthropic"
    enabled_by_default = False
    default_manifest_path = "./anthropic/connector.json"
    supports_marketplace = False

    def validate(self, root: Path, data: ManifestData) -> list[Diagnostic]:
        diagnostics = super().validate(root, data)
        if not self.enabled(data):
            return diagnostics

        target = get_target(data, "anthropic")
        submission = target.get("submission")
        if submission is not None:
            diagnostics.extend(_validate_submission_path(root, submission))

        connector = target.get("connector", {})
        if connector is not None and not isinstance(connector, dict):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "targets.anthropic.connector must be a mapping",
                    "satchel.yaml",
                    code="SATCHEL_TARGET_FIELD_TYPE",
                    target="anthropic",
                    component="connector",
                )
            )

        compatibility = target.get("compatibility", {})
        if compatibility is not None and not isinstance(compatibility, dict):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "targets.anthropic.compatibility must be a mapping",
                    "satchel.yaml",
                    code="SATCHEL_TARGET_FIELD_TYPE",
                    target="anthropic",
                    component="compatibility",
                )
            )
        return diagnostics

    def outputs(self, root: Path, data: ManifestData) -> list[GeneratedFile]:
        if not self.enabled(data):
            return []

        return [
            GeneratedFile(
                target="anthropic",
                path=self.manifest_path(root, data) or root / "anthropic/connector.json",
                content=format_json(_manifest(data)),
            ),
            GeneratedFile(
                target="anthropic-submission",
                path=_submission_path(root, data),
                content=_submission_markdown(data),
            ),
            GeneratedFile(
                target="anthropic-form",
                path=root / "anthropic/mcp-directory-form-questions.md",
                content=_form_reference_markdown(),
            ),
        ]

    def report(self, root: Path, data: ManifestData) -> list[PortabilityFinding]:
        findings = super().report(root, data)
        if self.enabled(data):
            findings.extend(
                [
                    PortabilityFinding(
                        "anthropic",
                        "mcp",
                        "native",
                        "remote HTTPS MCP endpoint declared in targets.anthropic.connector.mcpUrl",
                    ),
                    PortabilityFinding(
                        "anthropic",
                        "skills",
                        "ignored",
                        "Connectors Directory lists MCP tools; skills ship via the claude target",
                    ),
                ]
            )
        return findings

    def validate_outputs(self, root: Path, data: ManifestData) -> list[Diagnostic]:
        if not self.enabled(data):
            return []

        path = self.manifest_path(root, data) or root / "anthropic/connector.json"
        manifest = _manifest(data)
        diagnostics = require_fields(
            manifest,
            ("name", "version", "description", "format"),
            target="anthropic",
            path=path,
        )

        connector = manifest.get("connector")
        if not isinstance(connector, dict):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "anthropic output connector must be an object",
                    str(path),
                    code="SATCHEL_OUTPUT_FIELD_TYPE",
                    target="anthropic",
                    component="connector",
                )
            )
            return diagnostics

        for field in ("displayName", "shortDescription", "mcpUrl"):
            value = connector.get(field)
            if not isinstance(value, str) or not value.strip():
                diagnostics.append(
                    Diagnostic(
                        "error",
                        f"anthropic connector missing required field {field!r}",
                        str(path),
                        code="SATCHEL_OUTPUT_FIELD_MISSING",
                        target="anthropic",
                        component=field,
                    )
                )

        for field in ("mcpUrl", "privacyUrl", "termsUrl", "supportUrl"):
            value = connector.get(field)
            if isinstance(value, str) and value and not _is_https_url(value):
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        f"anthropic connector {field} should be an HTTPS URL",
                        str(path),
                        code="SATCHEL_ANTHROPIC_URL_NOT_HTTPS",
                        target="anthropic",
                        component=field,
                    )
                )

        display_name = connector.get("displayName")
        if isinstance(display_name, str) and _claims_anthropic_brand(display_name):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "anthropic connector displayName should not lead with 'Claude' or "
                    "'Anthropic'; the Directory grants no rights to those marks",
                    str(path),
                    code="SATCHEL_ANTHROPIC_BRAND_IN_NAME",
                    target="anthropic",
                    component="displayName",
                )
            )
        return diagnostics

    def marketplace_diagnostics(
        self, root: Path, data: ManifestData, *, release: bool = False
    ) -> list[Diagnostic]:
        if not self.enabled(data) or not release:
            return []

        target = get_target(data, "anthropic")
        connector = target.get("connector", {})
        if not isinstance(connector, dict):
            connector = {}

        diagnostics: list[Diagnostic] = []
        for field in ("mcpUrl", "privacyUrl", "termsUrl", "supportUrl"):
            value = connector.get(field)
            if not isinstance(value, str) or not value.strip():
                diagnostics.append(
                    Diagnostic(
                        "error",
                        f"anthropic release requires targets.anthropic.connector.{field}",
                        "satchel.yaml",
                        code="SATCHEL_ANTHROPIC_RELEASE_FIELD_MISSING",
                        target="anthropic",
                        component=field,
                    )
                )
        return diagnostics


def _manifest(data: ManifestData) -> dict[str, Any]:
    return {
        "format": "satchel-anthropic-connector/v0",
        "name": data["name"],
        "version": data["version"],
        "description": data["description"],
        "connector": _connector(data),
        "compatibility": _compatibility(data),
    }


def _connector(data: ManifestData) -> dict[str, Any]:
    target = get_target(data, "anthropic")
    raw_connector = target.get("connector", {})
    connector = raw_connector if isinstance(raw_connector, dict) else {}

    result: dict[str, Any] = {
        "displayName": connector.get("displayName")
        or title_from_name(str(data.get("name", ""))),
        "shortDescription": connector.get("shortDescription") or data.get("description", ""),
        "mcpUrl": connector.get("mcpUrl", ""),
    }

    for field in (
        "longDescription",
        "category",
        "privacyUrl",
        "termsUrl",
        "supportUrl",
        "icon",
        "homepageUrl",
    ):
        value = connector.get(field)
        if value:
            result[field] = value

    safety = connector.get("safety")
    if isinstance(safety, dict):
        result["safety"] = safety
    return result


def _compatibility(data: ManifestData) -> dict[str, Any]:
    target = get_target(data, "anthropic")
    raw_compatibility = target.get("compatibility", {})
    compatibility = raw_compatibility if isinstance(raw_compatibility, dict) else {}
    result: dict[str, Any] = {
        "requireReadOnlyHints": compatibility.get("requireReadOnlyHints", True),
        "oauth": compatibility.get("oauth", False),
        "highRisk": compatibility.get("highRisk", False),
    }
    for field in ("notes", "goldenPrompts"):
        value = compatibility.get(field)
        if value:
            result[field] = value
    return result


def _submission_path(root: Path, data: ManifestData) -> Path:
    target = get_target(data, "anthropic")
    submission = target.get("submission")
    if submission is None:
        return root / "anthropic/connector-submission.md"
    if isinstance(submission, str):
        return resolve_under_root(root, submission, label="targets.anthropic.submission")
    if isinstance(submission, dict):
        raw_path = submission.get("path", "./anthropic/connector-submission.md")
        if not isinstance(raw_path, str):
            raise SatchelError("targets.anthropic.submission.path must be a path")
        return resolve_under_root(root, raw_path, label="targets.anthropic.submission.path")
    raise SatchelError("targets.anthropic.submission must be a path or mapping")


def _validate_submission_path(root: Path, submission: Any) -> list[Diagnostic]:
    try:
        _submission_path(root, {"targets": {"anthropic": {"submission": submission}}})
    except SatchelError as exc:
        return [
            Diagnostic(
                "error",
                str(exc),
                "satchel.yaml",
                code="SATCHEL_PATH_INVALID",
                target="anthropic",
                component="submission",
            )
        ]
    return []


def _form_reference_markdown() -> str:
    """Source-linked preparation reference for Anthropic's live submission form.

    Emitted next to ``connector-submission.md`` so every packaged connector carries
    a durable checklist without redistributing the third-party questionnaire.
    """
    return (
        files("satchel.targets")
        .joinpath("assets/anthropic-mcp-directory-form.md")
        .read_text(encoding="utf-8")
    )


def _submission_markdown(data: ManifestData) -> str:
    manifest = _manifest(data)
    connector = manifest["connector"]
    compatibility = manifest["compatibility"]
    safety = connector.get("safety", {})
    safety_lines = (
        "\n".join(f"- {key}: {value}" for key, value in sorted(safety.items()))
        if isinstance(safety, dict) and safety
        else "- Not declared"
    )
    auth_line = (
        "OAuth 2.0 (authorization-code + PKCE; certs from recognized authorities, §5.D) — "
        "expose `.well-known/oauth-authorization-server` + `oauth-protected-resource`"
        if compatibility.get("oauth")
        else "No user auth (public data; keep upstream API keys server-side)"
    )
    high_risk_line = (
        "Yes — comply with Universal Usage Standards and High-Risk Use Case requirements"
        if compatibility.get("highRisk")
        else "Not flagged; Usage Policy still applies"
    )

    return f"""# Anthropic Connectors Directory Submission: {connector["displayName"]}

Generated by Satchel from `targets.anthropic`.

This is the **Anthropic Connectors Directory** submission (a remote MCP server
listed in Claude's connector catalog). It is NOT a Claude Code plugin — that is
the separate `claude` target. The Directory submission is a manual review flow;
this file is the metadata and checklist you bring to it.

## Connector Metadata

- Display name: {connector["displayName"]}
- Short description: {connector["shortDescription"]}
- MCP URL: {connector.get("mcpUrl", "") or "TODO"}
- Privacy URL: {connector.get("privacyUrl", "") or "TODO"}
- Terms URL: {connector.get("termsUrl", "") or "TODO"}
- Support URL: {connector.get("supportUrl", "") or "TODO"}
- Icon: {connector.get("icon", "") or "TODO"}
- Category: {connector.get("category", "") or "TODO"}

## Compatibility

- Auth: {auth_line}
- Require read-only hints: {compatibility["requireReadOnlyHints"]}
- High-risk use case (health/legal/finance): {high_risk_line}

## Safety

{safety_lines}

## Submission Steps (manual)

1. Confirm the server answers Streamable HTTP at the MCP URL and a health check responds (§5.F).
2. If OAuth, expose `.well-known` authorization-server + protected-resource docs (§5.D).
3. Add the MCP URL as a custom connector in Claude.ai (web); run golden prompts; confirm read-only.
4. Confirm display name, logo, and favicon pass brand review (no `Claude`/`Anthropic` dominant).
5. Use `mcp-directory-form-questions.md` to prepare, then answer Anthropic's live form.
6. Submit at https://claude.com/connectors; respond to review (mcp-review@anthropic.com).

## Release Checklist

Maps to the Software Directory Policy (support.claude.com/en/articles/13145358).

- [ ] Public **HTTPS** MCP endpoint is reachable from Claude (not HTTP).
- [ ] **Streamable HTTP** transport supported (§5.F; SSE optional, being deprecated).
- [ ] OAuth **2.0** fully implemented for all tools needing auth, certs from recognized CAs (§5.D).
- [ ] **CORS** configured for browser-based auth (claude.ai web).
- [ ] Every tool has a **`title`** + `readOnlyHint`/`destructiveHint` annotations (§5.E).
- [ ] Tool names ≤ **64 characters** (§5.C).
- [ ] **Token-frugal** responses — size commensurate with the task; heavy output opt-in (§5.B).
- [ ] Graceful, **actionable errors** (no generic failures) (§5.A).
- [ ] Privacy policy, terms, and support URLs live on a stable domain (§3.A).
- [ ] **Endpoint ownership (§3.F):** you own/control the API endpoints — OR, for a public-data
      connector, leave the ownership attestation unchecked and explain (you own the serving
      endpoint; data is public-domain/government); confirm treatment with mcp-review@anthropic.com.
- [ ] Logo is a square (1:1) SVG; **favicon resolves** via `google.com/s2/favicons?domain=<domain>`
      (needs the domain indexed by Google).
- [ ] Display name / logo / favicon do not misuse Anthropic marks.
- [ ] No money/crypto (§4.A); no AI image/video/audio gen (§4.B); no ads (§4.C).
- [ ] Universal Usage Standards + High-Risk Use Case requirements met (if applicable).
- [ ] Tested live as a custom connector on **Claude.ai (web)**, latest build.
- [ ] Golden prompts cover positive, negative, and boundary cases.
- [ ] Canonical / OAuth issuer URL is stable (changing it forces re-verification).
- [ ] Standard test account with sample data provided; valid ≥30 days (§3.D).
"""


def _is_https_url(value: str) -> bool:
    return value.startswith("https://")


def _claims_anthropic_brand(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered.startswith(("claude", "anthropic"))
