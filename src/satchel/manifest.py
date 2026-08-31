from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from satchel.core import Diagnostic, ManifestData, SatchelError

SATCHEL_SCHEMA = "satchel/v0"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def load_manifest(package_root: str | Path) -> tuple[Path, ManifestData]:
    root = Path(package_root).expanduser().resolve()
    manifest_path = root / "satchel.yaml"
    if not manifest_path.exists():
        raise SatchelError(f"missing manifest: {manifest_path}")

    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SatchelError("satchel.yaml must contain a YAML mapping")
    return root, raw


def validate_manifest(root: Path, data: ManifestData) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    if data.get("schema") != SATCHEL_SCHEMA:
        diagnostics.append(
            Diagnostic(
                "error",
                f"schema must be {SATCHEL_SCHEMA!r}",
                "satchel.yaml",
                code="SATCHEL_SCHEMA_INVALID",
            )
        )

    name = data.get("name")
    if not isinstance(name, str) or not name:
        diagnostics.append(
            Diagnostic("error", "name is required", "satchel.yaml", code="SATCHEL_FIELD_REQUIRED")
        )
    elif not NAME_RE.fullmatch(name):
        diagnostics.append(
            Diagnostic(
                "error",
                "name must be kebab-case lowercase ASCII",
                "satchel.yaml",
                code="SATCHEL_NAME_INVALID",
            )
        )

    for field in ("version", "description"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            diagnostics.append(
                Diagnostic(
                    "error",
                    f"{field} is required",
                    "satchel.yaml",
                    code="SATCHEL_FIELD_REQUIRED",
                )
            )

    diagnostics.extend(_validate_component_paths(root, data))
    diagnostics.extend(_validate_target_paths(root, data))
    diagnostics.extend(_validate_skills(root, data))
    return diagnostics


def raise_for_errors(diagnostics: list[Diagnostic]) -> None:
    errors = [diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"]
    if errors:
        joined = "\n".join(error.format() for error in errors)
        raise SatchelError(joined)


def get_component_path(data: ManifestData, name: str) -> str | None:
    components = data.get("components", {})
    if not isinstance(components, dict):
        return None

    component = components.get(name)
    if isinstance(component, str):
        return component
    if isinstance(component, dict):
        path = component.get("path")
        if isinstance(path, str):
            return path
    return None


def get_target(data: ManifestData, name: str) -> dict[str, Any]:
    targets = data.get("targets", {})
    if not isinstance(targets, dict):
        return {}
    target = targets.get(name, {})
    if isinstance(target, dict):
        return target
    return {}


def target_enabled(data: ManifestData, name: str) -> bool:
    try:
        from satchel.targets import all_adapters
    except ImportError:
        all_adapters = None

    if all_adapters:
        for adapter in all_adapters():
            if adapter.name == name:
                return adapter.enabled(data)

    target = get_target(data, name)
    return target.get("enabled", True) is not False


def resolve_under_root(root: Path, raw_path: str, *, label: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        raise SatchelError(f"{label} must be relative: {raw_path}")

    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SatchelError(f"{label} escapes package root: {raw_path}") from exc
    return resolved


def rel_json_path(root: Path, path: Path, *, trailing_slash: bool = False) -> str:
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    if trailing_slash and not relative.endswith("/"):
        relative = f"{relative}/"
    return f"./{relative}"


def _validate_component_paths(root: Path, data: ManifestData) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    components = data.get("components", {})
    if components is not None and not isinstance(components, dict):
        return [
            Diagnostic(
                "error",
                "components must be a mapping",
                "satchel.yaml",
                code="SATCHEL_COMPONENTS_TYPE",
            )
        ]

    for name in ("skills", "mcp", "hooks", "agents", "commands", "lsp", "rules", "apps"):
        raw_path = get_component_path(data, name)
        if not raw_path:
            continue
        try:
            path = resolve_under_root(root, raw_path, label=f"components.{name}.path")
        except SatchelError as exc:
            diagnostics.append(
                Diagnostic(
                    "error",
                    str(exc),
                    "satchel.yaml",
                    code="SATCHEL_COMPONENT_PATH_INVALID",
                    component=name,
                )
            )
            continue
        if not path.exists():
            diagnostics.append(
                Diagnostic(
                    "error",
                    f"components.{name}.path does not exist: {raw_path}",
                    raw_path,
                    code="SATCHEL_COMPONENT_PATH_MISSING",
                    component=name,
                )
            )
    return diagnostics


def _validate_target_paths(root: Path, data: ManifestData) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    targets = data.get("targets", {})
    if targets is not None and not isinstance(targets, dict):
        return [
            Diagnostic(
                "error",
                "targets must be a mapping",
                "satchel.yaml",
                code="SATCHEL_TARGETS_TYPE",
            )
        ]

    if isinstance(targets, dict):
        for name, target in targets.items():
            if not isinstance(target, dict):
                diagnostics.append(
                    Diagnostic(
                        "error",
                        f"targets.{name} must be a mapping",
                        "satchel.yaml",
                        code="SATCHEL_TARGET_TYPE",
                        target=name,
                    )
                )

    from satchel.targets import all_adapters

    known_targets = set()
    for adapter in all_adapters():
        known_targets.add(adapter.name)
        diagnostics.extend(adapter.validate(root, data))

    if isinstance(targets, dict):
        for name in sorted(set(targets) - known_targets):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    f"unknown target {name!r} will be ignored",
                    "satchel.yaml",
                    code="SATCHEL_TARGET_UNKNOWN",
                    target=name,
                )
            )
    return diagnostics


def _validate_skills(root: Path, data: ManifestData) -> list[Diagnostic]:
    raw_path = get_component_path(data, "skills")
    if not raw_path:
        return []

    try:
        skills_root = resolve_under_root(root, raw_path, label="components.skills.path")
    except SatchelError as exc:
        return [
            Diagnostic(
                "error",
                str(exc),
                "satchel.yaml",
                code="SATCHEL_COMPONENT_PATH_INVALID",
                component="skills",
            )
        ]

    if not skills_root.exists():
        return []
    if not skills_root.is_dir():
        return [
            Diagnostic(
                "error",
                "components.skills.path must be a directory",
                raw_path,
                code="SATCHEL_COMPONENT_PATH_TYPE",
                component="skills",
            )
        ]

    diagnostics: list[Diagnostic] = []
    skill_dirs = sorted(path for path in skills_root.iterdir() if path.is_dir())
    if not skill_dirs:
        diagnostics.append(
            Diagnostic(
                "warning",
                "no skill directories found",
                raw_path,
                code="SATCHEL_SKILLS_EMPTY",
                component="skills",
            )
        )

    for skill_dir in skill_dirs:
        skill_md = skill_dir / "SKILL.md"
        display_path = rel_json_path(root, skill_md)
        if not skill_md.exists():
            diagnostics.append(
                Diagnostic(
                    "error",
                    "missing SKILL.md",
                    display_path,
                    code="SATCHEL_SKILL_FILE_MISSING",
                    component="skills",
                )
            )
            continue
        metadata = _read_skill_frontmatter(skill_md)
        if not isinstance(metadata.get("name"), str) or not metadata["name"].strip():
            diagnostics.append(
                Diagnostic(
                    "error",
                    "skill frontmatter missing name",
                    display_path,
                    code="SATCHEL_SKILL_FRONTMATTER_MISSING",
                    component="skills",
                )
            )
        if not isinstance(metadata.get("description"), str) or not metadata["description"].strip():
            diagnostics.append(
                Diagnostic(
                    "error",
                    "skill frontmatter missing description",
                    display_path,
                    code="SATCHEL_SKILL_FRONTMATTER_MISSING",
                    component="skills",
                )
            )
        if metadata.get("name") and metadata.get("name") != skill_dir.name:
            diagnostics.append(
                Diagnostic(
                    "warning",
                    f"skill name {metadata.get('name')!r} differs from folder {skill_dir.name!r}",
                    display_path,
                    code="SATCHEL_SKILL_NAME_MISMATCH",
                    component="skills",
                )
            )
    return diagnostics


def _read_skill_frontmatter(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    end = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = index
            break
    if end is None:
        return {}

    block = "\n".join(lines[1:end])
    parsed = yaml.safe_load(block) or {}
    if isinstance(parsed, dict):
        return parsed
    return {}
