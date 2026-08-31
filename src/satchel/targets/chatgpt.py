from __future__ import annotations

from pathlib import Path
from typing import Any

from satchel.core import Diagnostic, GeneratedFile, ManifestData, PortabilityFinding, SatchelError
from satchel.manifest import get_target, resolve_under_root
from satchel.targets.base import BaseTargetAdapter, format_json, require_fields, title_from_name


class ChatGPTAdapter(BaseTargetAdapter):
    name = "chatgpt"
    enabled_by_default = False
    default_manifest_path = "./chatgpt/app.json"
    supports_marketplace = False

    def validate(self, root: Path, data: ManifestData) -> list[Diagnostic]:
        diagnostics = super().validate(root, data)
        if not self.enabled(data):
            return diagnostics

        target = get_target(data, "chatgpt")
        submission = target.get("submission")
        if submission is not None:
            diagnostics.extend(_validate_submission_path(root, submission))

        app = target.get("app", {})
        if app is not None and not isinstance(app, dict):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "targets.chatgpt.app must be a mapping",
                    "satchel.yaml",
                    code="SATCHEL_TARGET_FIELD_TYPE",
                    target="chatgpt",
                    component="app",
                )
            )

        compatibility = target.get("compatibility", {})
        if compatibility is not None and not isinstance(compatibility, dict):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "targets.chatgpt.compatibility must be a mapping",
                    "satchel.yaml",
                    code="SATCHEL_TARGET_FIELD_TYPE",
                    target="chatgpt",
                    component="compatibility",
                )
            )
        return diagnostics

    def outputs(self, root: Path, data: ManifestData) -> list[GeneratedFile]:
        if not self.enabled(data):
            return []

        return [
            GeneratedFile(
                target="chatgpt",
                path=self.manifest_path(root, data) or root / "chatgpt/app.json",
                content=format_json(_manifest(data)),
            ),
            GeneratedFile(
                target="chatgpt-submission",
                path=_submission_path(root, data),
                content=_submission_markdown(data),
            ),
        ]

    def report(self, root: Path, data: ManifestData) -> list[PortabilityFinding]:
        findings = super().report(root, data)
        if self.enabled(data):
            findings.extend(
                [
                    PortabilityFinding(
                        "chatgpt",
                        "mcp",
                        "native",
                        "remote HTTPS MCP endpoint declared in targets.chatgpt.app.mcpUrl",
                    ),
                    PortabilityFinding(
                        "chatgpt",
                        "skills",
                        "ignored",
                        "ChatGPT Apps use MCP tools; Satchel skills are not submitted",
                    ),
                    PortabilityFinding(
                        "chatgpt",
                        "ui",
                        "optional",
                        "Apps SDK UI resources are declared in the MCP server, not generated here",
                    ),
                ]
            )
        return findings

    def validate_outputs(self, root: Path, data: ManifestData) -> list[Diagnostic]:
        if not self.enabled(data):
            return []

        path = self.manifest_path(root, data) or root / "chatgpt/app.json"
        manifest = _manifest(data)
        diagnostics = require_fields(
            manifest,
            ("name", "version", "description", "format"),
            target="chatgpt",
            path=path,
        )

        app = manifest.get("app")
        if not isinstance(app, dict):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "chatgpt output app must be an object",
                    str(path),
                    code="SATCHEL_OUTPUT_FIELD_TYPE",
                    target="chatgpt",
                    component="app",
                )
            )
            return diagnostics

        for field in ("displayName", "shortDescription", "mcpUrl"):
            value = app.get(field)
            if not isinstance(value, str) or not value.strip():
                diagnostics.append(
                    Diagnostic(
                        "error",
                        f"chatgpt app missing required field {field!r}",
                        str(path),
                        code="SATCHEL_OUTPUT_FIELD_MISSING",
                        target="chatgpt",
                        component=field,
                    )
                )

        for field in ("mcpUrl", "privacyUrl", "termsUrl", "supportUrl"):
            value = app.get(field)
            if isinstance(value, str) and value and not _is_https_url(value):
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        f"chatgpt app {field} should be an HTTPS URL",
                        str(path),
                        code="SATCHEL_CHATGPT_URL_NOT_HTTPS",
                        target="chatgpt",
                        component=field,
                    )
                )
        return diagnostics

    def marketplace_diagnostics(
        self, root: Path, data: ManifestData, *, release: bool = False
    ) -> list[Diagnostic]:
        if not self.enabled(data) or not release:
            return []

        target = get_target(data, "chatgpt")
        app = target.get("app", {})
        if not isinstance(app, dict):
            app = {}

        diagnostics: list[Diagnostic] = []
        for field in ("privacyUrl", "termsUrl", "supportUrl"):
            value = app.get(field)
            if not isinstance(value, str) or not value.strip():
                diagnostics.append(
                    Diagnostic(
                        "error",
                        f"chatgpt release requires targets.chatgpt.app.{field}",
                        "satchel.yaml",
                        code="SATCHEL_CHATGPT_RELEASE_FIELD_MISSING",
                        target="chatgpt",
                        component=field,
                    )
                )
        return diagnostics


def _manifest(data: ManifestData) -> dict[str, Any]:
    return {
        "format": "satchel-chatgpt-app/v0",
        "name": data["name"],
        "version": data["version"],
        "description": data["description"],
        "app": _app(data),
        "compatibility": _compatibility(data),
    }


def _app(data: ManifestData) -> dict[str, Any]:
    target = get_target(data, "chatgpt")
    raw_app = target.get("app", {})
    app = raw_app if isinstance(raw_app, dict) else {}

    result: dict[str, Any] = {
        "displayName": app.get("displayName") or title_from_name(str(data.get("name", ""))),
        "shortDescription": app.get("shortDescription") or data.get("description", ""),
        "mcpUrl": app.get("mcpUrl", ""),
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
        value = app.get(field)
        if value:
            result[field] = value

    safety = app.get("safety")
    if isinstance(safety, dict):
        result["safety"] = safety
    return result


def _compatibility(data: ManifestData) -> dict[str, Any]:
    target = get_target(data, "chatgpt")
    raw_compatibility = target.get("compatibility", {})
    compatibility = raw_compatibility if isinstance(raw_compatibility, dict) else {}
    result: dict[str, Any] = {
        "requireReadOnlyHints": compatibility.get("requireReadOnlyHints", True),
        "requireSearchFetch": compatibility.get("requireSearchFetch", False),
        "toolOnly": compatibility.get("toolOnly", True),
    }
    for field in ("notes", "goldenPrompts"):
        value = compatibility.get(field)
        if value:
            result[field] = value
    return result


def _submission_path(root: Path, data: ManifestData) -> Path:
    target = get_target(data, "chatgpt")
    submission = target.get("submission")
    if submission is None:
        return root / "chatgpt/app-submission.md"
    if isinstance(submission, str):
        return resolve_under_root(root, submission, label="targets.chatgpt.submission")
    if isinstance(submission, dict):
        raw_path = submission.get("path", "./chatgpt/app-submission.md")
        if not isinstance(raw_path, str):
            raise SatchelError("targets.chatgpt.submission.path must be a path")
        return resolve_under_root(root, raw_path, label="targets.chatgpt.submission.path")
    raise SatchelError("targets.chatgpt.submission must be a path or mapping")


def _validate_submission_path(root: Path, submission: Any) -> list[Diagnostic]:
    try:
        _submission_path(root, {"targets": {"chatgpt": {"submission": submission}}})
    except SatchelError as exc:
        return [
            Diagnostic(
                "error",
                str(exc),
                "satchel.yaml",
                code="SATCHEL_PATH_INVALID",
                target="chatgpt",
                component="submission",
            )
        ]
    return []


def _submission_markdown(data: ManifestData) -> str:
    manifest = _manifest(data)
    app = manifest["app"]
    compatibility = manifest["compatibility"]
    safety = app.get("safety", {})
    safety_lines = (
        "\n".join(f"- {key}: {value}" for key, value in sorted(safety.items()))
        if isinstance(safety, dict) and safety
        else "- Not declared"
    )

    return f"""# ChatGPT App Submission: {app["displayName"]}

Generated by Satchel from `targets.chatgpt`.

## App Metadata

- Name: {app["displayName"]}
- Short description: {app["shortDescription"]}
- MCP URL: {app.get("mcpUrl", "") or "TODO"}
- Privacy URL: {app.get("privacyUrl", "") or "TODO"}
- Terms URL: {app.get("termsUrl", "") or "TODO"}
- Support URL: {app.get("supportUrl", "") or "TODO"}
- Icon: {app.get("icon", "") or "TODO"}
- Category: {app.get("category", "") or "TODO"}

## Compatibility

- Tool-only app: {compatibility["toolOnly"]}
- Require read-only hints: {compatibility["requireReadOnlyHints"]}
- Require `search`/`fetch`: {compatibility["requireSearchFetch"]}

## Safety

{safety_lines}

## Release Checklist

- [ ] Public HTTPS `/mcp` endpoint is reachable from ChatGPT.
- [ ] MCP server lists the expected public tools.
- [ ] Read-only tools include `readOnlyHint`.
- [ ] Privacy policy, terms, and support URLs are live.
- [ ] App behavior has been tested in ChatGPT developer mode.
- [ ] Golden prompts cover positive, negative, and boundary cases.
- [ ] Logs avoid storing sensitive user content unless the policy says otherwise.
"""


def _is_https_url(value: str) -> bool:
    return value.startswith("https://")
