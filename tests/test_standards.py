from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from satchel.cli import main
from satchel.standards import check_standards, standards_exit_code


def test_standards_check_updates_and_detects_changes(tmp_path: Path) -> None:
    sources_path = tmp_path / "sources.yaml"
    snapshots = tmp_path / "snapshots"
    _write_sources(sources_path, "hello")

    first = check_standards(
        tmp_path,
        sources_path=sources_path,
        snapshots_dir=snapshots,
        update=True,
        include_commands=True,
    )

    assert first[0].status == "new"
    assert standards_exit_code(first) == 2
    assert (snapshots / "local-command.json").exists()

    second = check_standards(
        tmp_path,
        sources_path=sources_path,
        snapshots_dir=snapshots,
        include_commands=True,
    )

    assert second[0].status == "unchanged"
    assert standards_exit_code(second) == 0

    _write_sources(sources_path, "goodbye")
    third = check_standards(
        tmp_path,
        sources_path=sources_path,
        snapshots_dir=snapshots,
        include_commands=True,
    )

    assert third[0].status == "changed"
    assert third[0].previous_sha256 == second[0].sha256


def test_standards_cli_json(tmp_path: Path, capsys) -> None:
    sources_path = tmp_path / "sources.yaml"
    snapshots = tmp_path / "snapshots"
    _write_sources(sources_path, "hello")

    code = main(
        [
            "standards",
            "check",
            str(tmp_path),
            "--sources",
            str(sources_path),
            "--snapshots",
            str(snapshots),
            "--include-commands",
            "--update",
            "--json",
        ]
    )

    assert code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
    assert result["summary"]["new"] == 1
    assert result["results"][0]["id"] == "local-command"


def _write_sources(path: Path, text: str) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "schema": "satchel-standards/v0",
                "sources": [
                    {
                        "id": "local-command",
                        "target": "test",
                        "title": "Local command",
                        "type": "command",
                        "command": [sys.executable, "-c", f"print({text!r})"],
                        "required": True,
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
