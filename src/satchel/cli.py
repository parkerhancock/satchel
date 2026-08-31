from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from satchel import __version__
from satchel.core import Diagnostic, ManifestData, SatchelError
from satchel.generate import build_outputs, portability_report, stale_outputs, write_outputs
from satchel.manifest import NAME_RE, load_manifest, raise_for_errors, validate_manifest
from satchel.standards import check_standards, standards_exit_code, standards_summary
from satchel.targets import adapter_for_target, adapter_names
from satchel.validate import host_diagnostics, marketplace_diagnostics, structural_diagnostics


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        return args.func(args)
    except SatchelError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="satchel")
    parser.add_argument("--version", action="version", version=f"satchel {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="create a minimal Satchel package")
    init.add_argument("path", help="package directory to create or update")
    init.add_argument("--name", help="plugin name; defaults to the directory name")
    init.add_argument("--force", action="store_true", help="overwrite Satchel-owned starter files")
    init.set_defaults(func=_cmd_init)

    generate = subparsers.add_parser("generate", help="generate host manifests")
    generate.add_argument("path", nargs="?", default=".", help="package directory")
    generate.set_defaults(func=_cmd_generate)

    check = subparsers.add_parser("check", help="validate source and generated manifests")
    check.add_argument("path", nargs="?", default=".", help="package directory")
    check.add_argument(
        "--host",
        action="store_true",
        help="run non-mutating host validators when available",
    )
    check.add_argument(
        "--host-timeout",
        type=int,
        default=30,
        help="seconds to wait for each host validator",
    )
    check.add_argument(
        "--json",
        action="store_true",
        help="write machine-readable diagnostics to stdout",
    )
    check.add_argument(
        "--release",
        action="store_true",
        help="require release-ready package-relative or remote marketplace sources",
    )
    check.set_defaults(func=_cmd_check)

    smoke = subparsers.add_parser("smoke", help="regenerate and validate a clean package copy")
    smoke.add_argument("path", nargs="?", default=".", help="package directory")
    smoke.add_argument(
        "--target",
        choices=adapter_names(),
        help="validate only one enabled target",
    )
    smoke.add_argument(
        "--host",
        action="store_true",
        help="run non-mutating host validators when available",
    )
    smoke.add_argument(
        "--host-timeout",
        type=int,
        default=30,
        help="seconds to wait for each host validator",
    )
    smoke.set_defaults(func=_cmd_smoke)

    pack = subparsers.add_parser("pack", help="build a target-specific package archive")
    pack.add_argument("path", nargs="?", default=".", help="package directory")
    pack.add_argument(
        "--target",
        required=True,
        choices=adapter_names(),
        help="target archive to build",
    )
    pack.add_argument(
        "--output-dir",
        default="dist",
        help="directory for the archive; relative paths resolve under the package root",
    )
    pack.add_argument(
        "--release",
        action="store_true",
        help="require release-ready package-relative or remote marketplace sources before packing",
    )
    pack.add_argument(
        "--host",
        action="store_true",
        help="run non-mutating host validators when available",
    )
    pack.add_argument(
        "--host-timeout",
        type=int,
        default=30,
        help="seconds to wait for each host validator",
    )
    pack.set_defaults(func=_cmd_pack)

    report = subparsers.add_parser("report", help="show a portability report")
    report.add_argument("path", nargs="?", default=".", help="package directory")
    report.set_defaults(func=_cmd_report)

    standards = subparsers.add_parser("standards", help="watch upstream host standards")
    standards_subparsers = standards.add_subparsers(dest="standards_command", required=True)
    standards_check = standards_subparsers.add_parser(
        "check",
        help="compare configured upstream standards sources with saved snapshots",
    )
    standards_check.add_argument("path", nargs="?", default=".", help="package directory")
    standards_check.add_argument(
        "--sources",
        help="standards source registry; defaults to standards/sources.yaml",
    )
    standards_check.add_argument(
        "--snapshots",
        help="snapshot directory; defaults to standards/snapshots",
    )
    standards_check.add_argument(
        "--update",
        action="store_true",
        help="write new snapshots when sources are new or changed",
    )
    standards_check.add_argument(
        "--include-commands",
        action="store_true",
        help="also run configured local command probes",
    )
    standards_check.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="seconds to wait for each source",
    )
    standards_check.add_argument(
        "--json",
        action="store_true",
        help="write machine-readable standards results to stdout",
    )
    standards_check.set_defaults(func=_cmd_standards_check)
    return parser


def _cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.path).expanduser()
    name = args.name or _default_name(root.name)
    if not NAME_RE.fullmatch(name):
        raise SatchelError("plugin name must be kebab-case lowercase ASCII")
    display_name = " ".join(part.capitalize() for part in name.split("-") if part)
    root.mkdir(parents=True, exist_ok=True)

    _write_starter_file(
        root / "satchel.yaml",
        _starter_manifest(name, display_name),
        force=args.force,
    )
    _write_starter_file(
        root / "skills" / "example" / "SKILL.md",
        _starter_skill(),
        force=args.force,
    )
    print(f"created Satchel package at {root}")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    root, data = load_manifest(args.path)
    diagnostics = validate_manifest(root, data)
    _print_diagnostics(diagnostics)
    raise_for_errors(diagnostics)

    outputs = build_outputs(root, data)
    write_outputs(outputs)
    for output in outputs:
        print(f"generated {output.target}: {output.path.relative_to(root)}")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    root, data = load_manifest(args.path)
    diagnostics = validate_manifest(root, data)
    if not _has_errors(diagnostics):
        diagnostics.extend(stale_outputs(build_outputs(root, data)))
        diagnostics.extend(structural_diagnostics(root, data))
        diagnostics.extend(marketplace_diagnostics(root, data, release=args.release))
        if args.host and not _has_errors(diagnostics):
            diagnostics.extend(host_diagnostics(root, data, timeout=args.host_timeout))
    if args.json:
        _print_check_json(root, diagnostics)
    else:
        _print_diagnostics(diagnostics)
    if _has_errors(diagnostics):
        return 1
    if not args.json:
        print("satchel check passed")
    return 0


def _cmd_smoke(args: argparse.Namespace) -> int:
    source_root, source_data = load_manifest(args.path)
    target = _resolve_enabled_target(args.target, source_data)
    with tempfile.TemporaryDirectory(prefix="satchel-smoke-") as tempdir:
        smoke_root = Path(tempdir) / source_root.name
        _copy_package(source_root, smoke_root)

        root, data = load_manifest(smoke_root)
        diagnostics = _generate_and_validate_copy(
            root,
            data,
            target=target,
            release=False,
            host=args.host,
            host_timeout=args.host_timeout,
        )

        _print_diagnostics(diagnostics)
        if _has_errors(diagnostics):
            return 1

    print("satchel smoke passed")
    return 0


def _cmd_pack(args: argparse.Namespace) -> int:
    source_root, source_data = load_manifest(args.path)
    target = _resolve_enabled_target(args.target, source_data)
    with tempfile.TemporaryDirectory(prefix="satchel-pack-") as tempdir:
        pack_root = Path(tempdir) / source_root.name
        _copy_package(source_root, pack_root)

        root, data = load_manifest(pack_root)
        target = _resolve_enabled_target(args.target, data)
        diagnostics = _generate_and_validate_copy(
            root,
            data,
            target=target,
            release=args.release,
            host=args.host,
            host_timeout=args.host_timeout,
        )
        _print_diagnostics(diagnostics)
        if _has_errors(diagnostics):
            return 1

        archive_path = _write_archive(source_root, pack_root, data, target, args.output_dir)

    print(f"packed {target}: {archive_path}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    root, data = load_manifest(args.path)
    diagnostics = validate_manifest(root, data)
    _print_diagnostics(diagnostics)
    raise_for_errors(diagnostics)
    print("\n".join(portability_report(root, data)))
    return 0


def _cmd_standards_check(args: argparse.Namespace) -> int:
    root = Path(args.path).expanduser()
    sources = Path(args.sources).expanduser() if args.sources else None
    snapshots = Path(args.snapshots).expanduser() if args.snapshots else None
    results = check_standards(
        root,
        sources_path=sources,
        snapshots_dir=snapshots,
        update=args.update,
        include_commands=args.include_commands,
        timeout=args.timeout,
    )
    summary = standards_summary(results)
    if args.json:
        print(
            json.dumps(
                {
                    "ok": summary["errors"] == 0
                    and summary["new"] == 0
                    and summary["changed"] == 0,
                    "path": str(root),
                    "summary": summary,
                    "results": [result.to_json() for result in results],
                },
                indent=2,
                ensure_ascii=True,
            )
        )
    else:
        for result in results:
            line = f"{result.status}: {result.id} ({result.source})"
            if result.message:
                line = f"{line}: {result.message}"
            print(line)
        print(
            "standards summary: "
            f"{summary['unchanged']} unchanged, "
            f"{summary['changed']} changed, "
            f"{summary['new']} new, "
            f"{summary['skipped']} skipped, "
            f"{summary['unavailable']} unavailable"
        )
    return standards_exit_code(results)


def _print_diagnostics(diagnostics: list[Diagnostic]) -> None:
    for diagnostic in diagnostics:
        print(diagnostic.format(), file=sys.stderr)


def _print_check_json(root: Path, diagnostics: list[Diagnostic]) -> None:
    errors = sum(1 for diagnostic in diagnostics if diagnostic.severity == "error")
    warnings = sum(1 for diagnostic in diagnostics if diagnostic.severity == "warning")
    print(
        json.dumps(
            {
                "ok": errors == 0,
                "path": str(root),
                "summary": {
                    "errors": errors,
                    "warnings": warnings,
                },
                "diagnostics": [diagnostic.to_json() for diagnostic in diagnostics],
            },
            indent=2,
            ensure_ascii=True,
        )
    )


def _has_errors(diagnostics: list[Diagnostic]) -> bool:
    return any(diagnostic.severity == "error" for diagnostic in diagnostics)


def _copy_package(source: Path, destination: Path) -> None:
    git_files = _git_package_files(source)
    if git_files is not None:
        destination.mkdir(parents=True, exist_ok=True)
        for relative_path in git_files:
            if _builtin_ignored(relative_path):
                continue
            source_file = source / relative_path
            destination_file = destination / relative_path
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, destination_file)
        return

    shutil.copytree(source, destination, symlinks=False, ignore=_copytree_ignore)


def _git_package_files(source: Path) -> list[Path] | None:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            ".",
        ],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        return None

    names = result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    return [Path(name) for name in names if name]


def _copytree_ignore(directory: str, names: list[str]) -> set[str]:
    base = Path(directory)
    ignored: set[str] = set()
    for name in names:
        if _builtin_ignored(Path(base.name) / name):
            ignored.add(name)
    return ignored


def _builtin_ignored(relative_path: Path) -> bool:
    ignored_names = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".release-smoke",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
    }
    if any(part in ignored_names for part in relative_path.parts):
        return True
    return any(part.endswith(".egg-info") for part in relative_path.parts) or (
        relative_path.name.endswith(".pyc")
    )


def _generate_and_validate_copy(
    root: Path,
    data: ManifestData,
    *,
    target: str | None,
    release: bool,
    host: bool,
    host_timeout: int,
) -> list[Diagnostic]:
    diagnostics = validate_manifest(root, data)
    if _has_errors(diagnostics):
        return diagnostics

    _remove_generated_outputs(root, data)
    outputs = build_outputs(root, data, target=target)
    write_outputs(outputs)
    diagnostics.extend(stale_outputs(outputs))
    diagnostics.extend(structural_diagnostics(root, data, target=target))
    diagnostics.extend(marketplace_diagnostics(root, data, release=release, target=target))
    if host and not _has_errors(diagnostics):
        diagnostics.extend(host_diagnostics(root, data, timeout=host_timeout, target=target))
    return diagnostics


def _remove_generated_outputs(root: Path, data: ManifestData) -> None:
    generated = build_outputs(root, data)
    parents: set[Path] = set()
    for output in generated:
        if output.preserve_existing:
            continue
        parents.add(output.path.parent)
        if output.path.exists() and output.path.is_file():
            output.path.unlink()

    for parent in sorted(parents, key=lambda path: len(path.parts), reverse=True):
        while parent != root and parent.exists():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent


def _resolve_enabled_target(target: str | None, data: ManifestData) -> str | None:
    if target is None:
        return None
    adapter = adapter_for_target(target)
    if adapter is None:
        raise SatchelError(f"unknown target: {target}")
    if not adapter.enabled(data):
        raise SatchelError(f"target is disabled: {target}")
    return target


def _write_archive(
    source_root: Path,
    pack_root: Path,
    data: ManifestData,
    target: str,
    raw_output_dir: str,
) -> Path:
    output_dir = Path(raw_output_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = source_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    archive_path = output_dir / _archive_name(data, target)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(pack_root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(pack_root).as_posix())
    return archive_path


def _archive_name(data: ManifestData, target: str) -> str:
    name = _safe_archive_part(str(data.get("name", "plugin")))
    version = _safe_archive_part(str(data.get("version", "0.0.0")))
    return f"{name}-{version}-{target}.zip"


def _safe_archive_part(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return normalized or "package"


def _write_starter_file(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise SatchelError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _default_name(path_name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", path_name.lower()).strip("-")
    return normalized or "my-plugin"


def _starter_manifest(name: str, display_name: str) -> str:
    return f"""schema: satchel/v0
name: {name}
version: 0.1.0
description: Product-agnostic agent extension.
author:
  name: Your Team
keywords:
  - agents
  - skills

components:
  skills:
    path: ./skills

targets:
  codex:
    enabled: true
    manifest: ./.codex-plugin/plugin.json
    interface:
      displayName: {display_name}
      shortDescription: Product-agnostic agent extension.
      category: Productivity
      capabilities:
        - Read

  claude:
    enabled: true
    manifest: ./.claude-plugin/plugin.json
    displayName: {display_name}

  copilot:
    enabled: true
    manifest: ./.github/plugin/plugin.json
    marketplace:
      path: ./.github/plugin/marketplace.json
      name: {name}-marketplace

  antigravity:
    enabled: false
    experimental: true
    output: ./.agents/plugins/{name}
"""


def _starter_skill() -> str:
    return """---
name: example
description: Use this skill as a minimal portable Satchel example.
---

# Example

Describe what this shared skill does. Keep host-specific behavior in generated
manifests or host-specific directories.
"""


if __name__ == "__main__":
    raise SystemExit(main())
