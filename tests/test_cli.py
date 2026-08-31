from __future__ import annotations

import json
import subprocess
import tomllib
import zipfile
from pathlib import Path

import pytest
import yaml

from satchel import __version__
from satchel.cli import main


def test_init_generate_check_roundtrip(tmp_path: Path) -> None:
    package = tmp_path / "my-plugin"

    assert main(["init", str(package)]) == 0
    assert (package / "satchel.yaml").exists()
    assert (package / "skills/example/SKILL.md").exists()

    assert main(["generate", str(package)]) == 0
    assert main(["check", str(package)]) == 0

    (package / ".claude-plugin/plugin.json").write_text("{}\n", encoding="utf-8")
    assert main(["check", str(package)]) == 1


def test_check_json_reports_stale_outputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    package = tmp_path / "my-plugin"

    assert main(["init", str(package)]) == 0
    assert main(["generate", str(package)]) == 0
    (package / ".claude-plugin/plugin.json").write_text("{}\n", encoding="utf-8")
    capsys.readouterr()

    assert main(["check", str(package), "--json"]) == 1
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert captured.err == ""
    assert result["ok"] is False
    assert result["summary"]["errors"] == 1
    assert result["diagnostics"][0]["code"] == "SATCHEL_GENERATED_STALE"
    assert result["diagnostics"][0]["target"] == "claude"


def test_check_warns_on_explicit_local_marketplace_source(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    package = tmp_path / "my-plugin"

    assert main(["init", str(package)]) == 0
    manifest_path = package / "satchel.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    data["targets"]["claude"]["marketplace"] = {
        "path": "./.claude-plugin/marketplace.json",
        "source": "./",
    }
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    assert main(["generate", str(package)]) == 0
    capsys.readouterr()

    assert main(["check", str(package), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["ok"] is True
    assert result["summary"]["warnings"] == 1
    assert result["diagnostics"][0]["code"] == "SATCHEL_MARKETPLACE_LOCAL_SOURCE"
    assert result["diagnostics"][0]["target"] == "claude"


def test_release_check_requires_remote_marketplace_sources(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    package = tmp_path / "my-plugin"

    assert main(["init", str(package)]) == 0
    assert main(["generate", str(package)]) == 0
    capsys.readouterr()

    assert main(["check", str(package), "--release", "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    codes = {diagnostic["code"] for diagnostic in result["diagnostics"]}

    assert result["ok"] is False
    assert result["summary"]["errors"] == 3
    assert "SATCHEL_MARKETPLACE_MISSING" in codes
    assert "SATCHEL_MARKETPLACE_SOURCE_MISSING" in codes


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"satchel {__version__}"


def test_release_versions_match() -> None:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = yaml.safe_load((root / "satchel.yaml").read_text(encoding="utf-8"))
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")

    project_version = project["project"]["version"]
    assert __version__ == project_version
    assert manifest["version"] == project_version
    assert f"## {project_version} -" in changelog


def test_smoke_regenerates_and_validates_clean_copy(tmp_path: Path) -> None:
    package = tmp_path / "my-plugin"

    assert main(["init", str(package)]) == 0
    assert main(["smoke", str(package)]) == 0

    assert not (package / ".codex-plugin/plugin.json").exists()
    assert not (package / ".claude-plugin/plugin.json").exists()


def test_smoke_target_rejects_disabled_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    package = tmp_path / "my-plugin"

    assert main(["init", str(package)]) == 0
    capsys.readouterr()

    assert main(["smoke", str(package), "--target", "antigravity"]) == 1
    assert "target is disabled: antigravity" in capsys.readouterr().err


def test_pack_target_writes_target_archive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    package = tmp_path / "my-plugin"

    assert main(["init", str(package)]) == 0
    capsys.readouterr()

    assert main(["pack", str(package), "--target", "codex"]) == 0
    output = capsys.readouterr()
    archive_path = package / "dist/my-plugin-0.1.0-codex.zip"

    assert f"packed codex: {archive_path}" in output.out
    assert archive_path.exists()
    assert not (package / ".codex-plugin/plugin.json").exists()
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())

    assert "satchel.yaml" in names
    assert "skills/example/SKILL.md" in names
    assert ".codex-plugin/plugin.json" in names
    assert ".claude-plugin/plugin.json" not in names


def test_pack_skips_gitignored_local_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    package = tmp_path / "my-plugin"

    assert main(["init", str(package)]) == 0
    (package / ".gitignore").write_text(".release-smoke/\n*.ignored\n", encoding="utf-8")
    (package / ".release-smoke/bin").mkdir(parents=True)
    (package / ".release-smoke/bin/python").write_text("local runtime\n", encoding="utf-8")
    (package / "scratch.ignored").write_text("local artifact\n", encoding="utf-8")
    (package / "README.md").write_text("include me\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=package, check=True, capture_output=True)
    capsys.readouterr()

    assert main(["pack", str(package), "--target", "codex"]) == 0
    with zipfile.ZipFile(package / "dist/my-plugin-0.1.0-codex.zip") as archive:
        names = set(archive.namelist())

    assert "satchel.yaml" in names
    assert "README.md" in names
    assert ".release-smoke/bin/python" not in names
    assert "scratch.ignored" not in names


def test_pack_release_requires_selected_target_marketplace(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    package = tmp_path / "my-plugin"

    assert main(["init", str(package)]) == 0
    capsys.readouterr()

    assert main(["pack", str(package), "--target", "codex", "--release"]) == 1
    output = capsys.readouterr()

    assert "SATCHEL_MARKETPLACE_MISSING" in output.err
    assert not (package / "dist/my-plugin-0.1.0-codex.zip").exists()


def test_pack_preserves_patched_marketplace_metadata(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    package = tmp_path / "my-plugin"

    assert main(["init", str(package)]) == 0
    manifest_path = package / "satchel.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    data["targets"]["codex"]["marketplace"] = {
        "path": "./.agents/plugins/marketplace.json",
        "patch": True,
        "source": {
            "source": "url",
            "url": "https://github.com/example/my-plugin.git",
        },
    }
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    marketplace_path = package / ".agents/plugins/marketplace.json"
    marketplace_path.parent.mkdir(parents=True)
    marketplace_path.write_text(
        json.dumps(
            {
                "name": "my-plugin-marketplace",
                "plugins": [
                    {
                        "name": "my-plugin",
                        "source": "./stale",
                        "x-host": "keep",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    capsys.readouterr()

    assert main(["pack", str(package), "--target", "codex", "--release"]) == 0
    with zipfile.ZipFile(package / "dist/my-plugin-0.1.0-codex.zip") as archive:
        marketplace = json.loads(archive.read(".agents/plugins/marketplace.json"))

    plugin = marketplace["plugins"][0]
    assert plugin["source"]["url"] == "https://github.com/example/my-plugin.git"
    assert plugin["x-host"] == "keep"
    assert marketplace_path.exists()


def test_fixtures_smoke() -> None:
    fixtures_root = Path(__file__).resolve().parents[1] / "fixtures"

    for fixture in sorted(path for path in fixtures_root.iterdir() if path.is_dir()):
        assert main(["smoke", str(fixture)]) == 0, fixture.name
