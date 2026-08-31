from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from satchel.core import Diagnostic, GeneratedFile, ManifestData, PortabilityFinding, SatchelError
from satchel.manifest import get_component_path, get_target, rel_json_path, resolve_under_root


class TargetAdapter(Protocol):
    name: str
    enabled_by_default: bool
    default_manifest_path: str | None
    supports_marketplace: bool
    requires_marketplace_owner: bool

    def enabled(self, data: ManifestData) -> bool: ...

    def validate(self, root: Path, data: ManifestData) -> list[Diagnostic]: ...

    def outputs(self, root: Path, data: ManifestData) -> list[GeneratedFile]: ...

    def report(self, root: Path, data: ManifestData) -> list[PortabilityFinding]: ...

    def validate_outputs(self, root: Path, data: ManifestData) -> list[Diagnostic]: ...

    def marketplace_diagnostics(
        self, root: Path, data: ManifestData, *, release: bool = False
    ) -> list[Diagnostic]: ...

    def marketplace_installability(self, root: Path, data: ManifestData) -> str: ...


class BaseTargetAdapter:
    name = ""
    enabled_by_default = False
    default_manifest_path: str | None = None
    supports_marketplace = True
    requires_marketplace_owner = False

    def enabled(self, data: ManifestData) -> bool:
        targets = data.get("targets", {})
        if isinstance(targets, dict) and self.name in targets:
            target = targets.get(self.name)
            if not isinstance(target, dict):
                return False
            return target.get("enabled", True) is not False
        return self.enabled_by_default

    def validate(self, root: Path, data: ManifestData) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        target = get_target(data, self.name)
        not_applicable = target.get("notApplicable")
        if not_applicable is not None:
            if not isinstance(not_applicable, str) or not not_applicable.strip():
                diagnostics.append(
                    Diagnostic(
                        "error",
                        f"targets.{self.name}.notApplicable must be a non-empty string",
                        "satchel.yaml",
                        code="SATCHEL_TARGET_NOT_APPLICABLE_TYPE",
                        target=self.name,
                        component="notApplicable",
                    )
                )
            elif self.enabled(data):
                diagnostics.append(
                    Diagnostic(
                        "error",
                        f"targets.{self.name}.notApplicable requires enabled: false",
                        "satchel.yaml",
                        code="SATCHEL_TARGET_NOT_APPLICABLE_ENABLED",
                        target=self.name,
                        component="notApplicable",
                    )
                )

        if not self.enabled(data):
            return diagnostics

        if self.default_manifest_path is not None:
            diagnostics.extend(
                self._validate_path_field(
                    root,
                    target.get("manifest", self.default_manifest_path),
                    f"targets.{self.name}.manifest",
                )
            )
        else:
            raw_manifest = target.get("manifest")
            if raw_manifest is not None:
                diagnostics.extend(
                    self._validate_path_field(
                        root,
                        raw_manifest,
                        f"targets.{self.name}.manifest",
                    )
                )

        marketplace = target.get("marketplace")
        if marketplace is None:
            return diagnostics
        if not isinstance(marketplace, dict):
            diagnostics.append(
                Diagnostic(
                    "error",
                    f"targets.{self.name}.marketplace must be a mapping",
                    "satchel.yaml",
                    code="SATCHEL_TARGET_FIELD_TYPE",
                    target=self.name,
                )
            )
            return diagnostics
        marketplace_path = marketplace.get("path")
        if marketplace_path is not None:
            diagnostics.extend(
                self._validate_path_field(
                    root,
                    marketplace_path,
                    f"targets.{self.name}.marketplace.path",
                )
            )
        return diagnostics

    def outputs(self, root: Path, data: ManifestData) -> list[GeneratedFile]:
        return []

    def report(self, root: Path, data: ManifestData) -> list[PortabilityFinding]:
        if not self.enabled(data):
            reason = self._not_applicable_reason(data)
            if reason:
                return [
                    PortabilityFinding(
                        self.name,
                        "target",
                        "not applicable",
                        reason,
                    )
                ]
            return [
                PortabilityFinding(
                    self.name,
                    "target",
                    "ignored",
                    "target disabled",
                )
            ]
        manifest_path = self.manifest_path(root, data)
        if manifest_path is None:
            return [
                PortabilityFinding(
                    self.name,
                    "target",
                    "native",
                    "enabled",
                )
            ]
        return [
            PortabilityFinding(
                self.name,
                "manifest",
                "native",
                manifest_path.relative_to(root).as_posix(),
            )
        ]

    def validate_outputs(self, root: Path, data: ManifestData) -> list[Diagnostic]:
        return []

    def marketplace_diagnostics(
        self, root: Path, data: ManifestData, *, release: bool = False
    ) -> list[Diagnostic]:
        if not self.enabled(data) or not self.supports_marketplace:
            return []

        target = get_target(data, self.name)
        marketplace = target.get("marketplace")
        if marketplace is None:
            if not release:
                return []
            return [
                Diagnostic(
                    "error",
                    f"{self.name} release installs require targets.{self.name}.marketplace",
                    "satchel.yaml",
                    code="SATCHEL_MARKETPLACE_MISSING",
                    target=self.name,
                )
            ]
        if not isinstance(marketplace, dict):
            return []

        diagnostics: list[Diagnostic] = []
        if self.requires_marketplace_owner and not self._marketplace_owner_available(
            root, data, marketplace
        ):
            diagnostics.append(
                Diagnostic(
                    "error",
                    f"{self.name} marketplace requires author metadata for its owner",
                    "satchel.yaml",
                    code="SATCHEL_MARKETPLACE_OWNER_MISSING",
                    target=self.name,
                )
            )

        source_declared = "source" in marketplace
        source = marketplace.get("source")
        if _marketplace_source_is_remote(source):
            return diagnostics
        if not source_declared and not release:
            return diagnostics

        severity = "error" if release else "warning"
        message = (
            f"{self.name} marketplace source is local-only; use a remote GitHub "
            "or URL source for installable releases"
        )
        if not source_declared:
            message = (
                f"{self.name} marketplace source is missing; release installs need a remote source"
            )
        code = (
            "SATCHEL_MARKETPLACE_SOURCE_MISSING"
            if not source_declared
            else "SATCHEL_MARKETPLACE_LOCAL_SOURCE"
        )
        diagnostics.append(
            Diagnostic(
                severity,
                message,
                "satchel.yaml",
                code=code,
                target=self.name,
            )
        )
        return diagnostics

    def marketplace_installability(self, root: Path, data: ManifestData) -> str:
        if not self.enabled(data):
            if self._not_applicable_reason(data):
                return "not applicable"
            return "disabled"
        if not self.supports_marketplace:
            return "unsupported"
        target = get_target(data, self.name)
        marketplace = target.get("marketplace")
        if not isinstance(marketplace, dict):
            return "not declared"
        if self.requires_marketplace_owner and not self._marketplace_owner_available(
            root, data, marketplace
        ):
            return "incomplete (owner missing)"
        if _marketplace_source_is_remote(marketplace.get("source")):
            return "remote-ready"
        return "local-only"

    def _not_applicable_reason(self, data: ManifestData) -> str | None:
        value = get_target(data, self.name).get("notApplicable")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _marketplace_owner_available(
        self, root: Path, data: ManifestData, marketplace: dict[str, Any]
    ) -> bool:
        if owner(data):
            return True
        if marketplace.get("patch") is not True:
            return False
        try:
            path = self.marketplace_path(root, data)
        except SatchelError:
            return False
        if path is None or not path.is_file():
            return False
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(existing, dict):
            return False
        existing_owner = existing.get("owner")
        return (
            isinstance(existing_owner, dict)
            and isinstance(existing_owner.get("name"), str)
            and bool(existing_owner["name"].strip())
        )

    def manifest_path(self, root: Path, data: ManifestData) -> Path | None:
        if self.default_manifest_path is None:
            return None
        target = get_target(data, self.name)
        raw_path = target.get("manifest", self.default_manifest_path)
        if not isinstance(raw_path, str):
            raw_path = self.default_manifest_path
        return resolve_under_root(root, raw_path, label=f"targets.{self.name}.manifest")

    def marketplace_path(self, root: Path, data: ManifestData) -> Path | None:
        target = get_target(data, self.name)
        marketplace = target.get("marketplace")
        if not isinstance(marketplace, dict):
            return None
        raw_path = marketplace.get("path")
        if not isinstance(raw_path, str):
            return None
        return resolve_under_root(root, raw_path, label=f"targets.{self.name}.marketplace.path")

    def _validate_path_field(self, root: Path, raw_path: Any, label: str) -> list[Diagnostic]:
        if not isinstance(raw_path, str):
            return [
                Diagnostic(
                    "error",
                    f"{label} must be a path",
                    "satchel.yaml",
                    code="SATCHEL_PATH_TYPE",
                    target=self.name,
                )
            ]
        try:
            resolve_under_root(root, raw_path, label=label)
        except SatchelError as exc:
            return [
                Diagnostic(
                    "error",
                    str(exc),
                    "satchel.yaml",
                    code="SATCHEL_PATH_INVALID",
                    target=self.name,
                )
            ]
        return []


def common_manifest(data: ManifestData) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "name": data["name"],
        "version": data["version"],
        "description": data["description"],
    }
    author_data = owner(data)
    if author_data:
        manifest["author"] = author_data
    for field in ("homepage", "repository", "license", "keywords"):
        if field in data:
            manifest[field] = data[field]
    return manifest


def marketplace_config(target: dict[str, Any]) -> dict[str, Any]:
    marketplace = target.get("marketplace", {})
    if isinstance(marketplace, dict):
        return marketplace
    return {}


def marketplace_patch_enabled(data: ManifestData, target: str) -> bool:
    return marketplace_config(get_target(data, target)).get("patch") is True


def marketplace_content(
    path: Path, generated: dict[str, Any], plugin_name: str, *, patch: bool
) -> str:
    if not patch:
        return format_json(generated)
    return format_json(patch_marketplace(path, generated, plugin_name))


def patch_marketplace(path: Path, generated: dict[str, Any], plugin_name: str) -> dict[str, Any]:
    if not path.exists():
        return generated
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SatchelError(f"cannot patch invalid marketplace JSON: {path}") from exc
    if not isinstance(existing, dict):
        raise SatchelError(f"cannot patch marketplace JSON that is not an object: {path}")
    return _merge_marketplace(existing, generated, plugin_name)


def owner(data: ManifestData) -> dict[str, str]:
    author = data.get("author")
    if isinstance(author, str) and author.strip():
        return {"name": author.strip()}
    if not isinstance(author, dict):
        return {}
    name = author.get("name")
    if not isinstance(name, str) or not name.strip():
        return {}
    result = {"name": name.strip()}
    for key in ("email", "url"):
        value = author.get(key)
        if isinstance(value, str) and value:
            result[key] = value
    return result


def title_from_name(name: str) -> str:
    return " ".join(part.capitalize() for part in name.split("-") if part)


def component_json_path(
    root: Path,
    data: ManifestData,
    component: str,
    *,
    relative_to: Path | None = None,
    trailing_slash: bool = False,
) -> str | None:
    raw_path = get_component_path(data, component)
    if not raw_path:
        return None
    path = resolve_under_root(root, raw_path, label=f"components.{component}.path")
    reference_root = relative_to or root
    try:
        return rel_json_path(reference_root, path, trailing_slash=trailing_slash)
    except ValueError as exc:
        raise SatchelError(
            f"components.{component}.path must be inside the target plugin root: {reference_root}"
        ) from exc


def component_path(root: Path, data: ManifestData, component: str) -> Path | None:
    raw_path = get_component_path(data, component)
    if not raw_path:
        return None
    return resolve_under_root(root, raw_path, label=f"components.{component}.path")


def skill_marketplace_paths(root: Path, data: ManifestData) -> list[str]:
    skills_root = component_path(root, data, "skills")
    if not skills_root or not skills_root.is_dir():
        return []
    return [
        rel_json_path(root, path)
        for path in sorted(skills_root.iterdir())
        if path.is_dir() and (path / "SKILL.md").exists()
    ]


def copied_tree_outputs(
    target: str, root: Path, source: Path | None, destination: Path
) -> list[GeneratedFile]:
    if source is None or not source.is_dir():
        return []
    if source.resolve() == destination.resolve():
        return []

    outputs: list[GeneratedFile] = []
    for source_file in sorted(path for path in source.rglob("*") if path.is_file()):
        if source_file.is_symlink():
            continue
        resolved = source_file.resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError as exc:
            raise SatchelError(f"component file escapes package root: {source_file}") from exc
        relative = source_file.relative_to(source)
        outputs.append(
            GeneratedFile(
                target=target,
                path=destination / relative,
                content=source_file.read_bytes(),
            )
        )
    return outputs


def json_component_content(root: Path, data: ManifestData, component: str) -> str | None:
    path = component_path(root, data, component)
    if path is None or not path.exists():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SatchelError(f"components.{component}.path is not valid JSON: {path}") from exc
    return format_json(parsed)


def format_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=True) + "\n"


def _merge_marketplace(
    existing: dict[str, Any], generated: dict[str, Any], plugin_name: str
) -> dict[str, Any]:
    merged = _merge_generated_fields(
        existing,
        generated,
        nested_keys={"interface", "metadata", "owner"},
    )
    generated_plugins = generated.get("plugins")
    if isinstance(generated_plugins, list):
        merged["plugins"] = _merge_plugins(existing.get("plugins"), generated_plugins, plugin_name)
    return merged


def _merge_plugins(existing: Any, generated: list[Any], plugin_name: str) -> list[Any]:
    generated_by_name = {
        plugin.get("name"): plugin
        for plugin in generated
        if isinstance(plugin, dict) and isinstance(plugin.get("name"), str)
    }
    placed: set[str] = set()
    result: list[Any] = []

    if isinstance(existing, list):
        for plugin in existing:
            name = plugin.get("name") if isinstance(plugin, dict) else None
            generated_plugin = generated_by_name.get(name)
            if isinstance(plugin, dict) and isinstance(generated_plugin, dict):
                result.append(
                    _merge_generated_fields(
                        plugin,
                        generated_plugin,
                        nested_keys={"policy"},
                    )
                )
                if isinstance(name, str):
                    placed.add(name)
            else:
                result.append(plugin)

    for plugin in generated:
        if not isinstance(plugin, dict):
            result.append(plugin)
            continue
        name = plugin.get("name")
        if name == plugin_name and name not in placed:
            result.append(plugin)
            placed.add(str(name))
        elif isinstance(name, str) and name not in placed and name in generated_by_name:
            result.append(plugin)
            placed.add(name)
    return result


def _merge_generated_fields(
    existing: dict[str, Any], generated: dict[str, Any], *, nested_keys: set[str]
) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in generated.items():
        current = merged.get(key)
        if key in nested_keys and isinstance(current, dict) and isinstance(value, dict):
            nested = dict(current)
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged


def require_fields(
    document: dict[str, Any], fields: tuple[str, ...], *, target: str, path: Path
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for field in fields:
        value = document.get(field)
        if not isinstance(value, str) or not value.strip():
            diagnostics.append(
                Diagnostic(
                    "error",
                    f"{target} output missing required field {field!r}",
                    str(path),
                    code="SATCHEL_OUTPUT_FIELD_MISSING",
                    target=target,
                )
            )
    return diagnostics


def validate_relative_reference(
    value: Any, *, target: str, field: str, path: Path
) -> Diagnostic | None:
    if not isinstance(value, str):
        return Diagnostic(
            "error",
            f"{target} {field} must be a path string",
            str(path),
            code="SATCHEL_OUTPUT_PATH_TYPE",
            target=target,
            component=field,
        )
    if value.startswith("./"):
        return None
    return Diagnostic(
        "warning",
        f"{target} {field} should start with './'",
        str(path),
        code="SATCHEL_OUTPUT_PATH_STYLE",
        target=target,
        component=field,
    )


def _marketplace_source_is_remote(source: Any) -> bool:
    if isinstance(source, str):
        return _remote_string(source)
    if not isinstance(source, dict):
        return False

    kind = source.get("source") or source.get("type")
    if isinstance(kind, str) and kind.lower() == "local":
        return False

    for key in ("url", "git", "repositoryUrl"):
        value = source.get(key)
        if isinstance(value, str) and _remote_string(value):
            return True

    repo = source.get("repo") or source.get("repository")
    if isinstance(repo, str) and "/" in repo and not repo.startswith((".", "/")):
        return True

    return False


def _remote_string(value: str) -> bool:
    stripped = value.strip()
    if not stripped or stripped in {".", "./"}:
        return False
    return stripped.startswith(("http://", "https://", "git@", "ssh://", "git+"))
