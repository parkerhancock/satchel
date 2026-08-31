from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from satchel.core import SatchelError

SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
USER_AGENT = (
    "Mozilla/5.0 "
    "(compatible; Satchel Standards Watch/0; +https://github.com/parkerhancock/satchel)"
)


@dataclass(frozen=True)
class StandardsResult:
    id: str
    target: str | None
    title: str
    source_type: str
    source: str
    status: str
    required: bool
    sha256: str | None = None
    previous_sha256: str | None = None
    byte_count: int | None = None
    observed_at: str | None = None
    message: str | None = None

    def to_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "target": self.target,
            "title": self.title,
            "type": self.source_type,
            "source": self.source,
            "status": self.status,
            "required": self.required,
        }
        optional_fields = {
            "sha256": self.sha256,
            "previous_sha256": self.previous_sha256,
            "byte_count": self.byte_count,
            "observed_at": self.observed_at,
            "message": self.message,
        }
        for key, value in optional_fields.items():
            if value is not None:
                data[key] = value
        return data


def check_standards(
    root: Path,
    *,
    sources_path: Path | None = None,
    snapshots_dir: Path | None = None,
    update: bool = False,
    include_commands: bool = False,
    timeout: int = 30,
) -> list[StandardsResult]:
    sources_path = sources_path or root / "standards" / "sources.yaml"
    snapshots_dir = snapshots_dir or root / "standards" / "snapshots"
    sources = load_standard_sources(sources_path)

    results: list[StandardsResult] = []
    for source in sources:
        result = _check_source(
            source,
            snapshots_dir=snapshots_dir,
            update=update,
            include_commands=include_commands,
            timeout=timeout,
        )
        results.append(result)
    return results


def load_standard_sources(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SatchelError(f"standards source registry not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SatchelError("standards source registry must be a YAML object")
    if raw.get("schema") != "satchel-standards/v0":
        raise SatchelError("standards source registry schema must be satchel-standards/v0")

    sources = raw.get("sources")
    if not isinstance(sources, list) or not sources:
        raise SatchelError("standards source registry must contain a non-empty sources list")

    seen: set[str] = set()
    normalized_sources: list[dict[str, Any]] = []
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise SatchelError(f"standards source #{index + 1} must be an object")
        source_id = source.get("id")
        if not isinstance(source_id, str) or not SOURCE_ID_RE.fullmatch(source_id):
            raise SatchelError(f"standards source #{index + 1} has invalid id: {source_id!r}")
        if source_id in seen:
            raise SatchelError(f"duplicate standards source id: {source_id}")
        seen.add(source_id)

        source_type = source.get("type")
        if source_type not in {"url", "command"}:
            raise SatchelError(f"{source_id}: type must be url or command")
        if source_type == "url":
            url = source.get("url")
            if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                raise SatchelError(f"{source_id}: url source requires an http(s) url")
        if source_type == "command":
            command = source.get("command")
            if (
                not isinstance(command, list)
                or not command
                or not all(isinstance(part, str) and part for part in command)
            ):
                raise SatchelError(f"{source_id}: command source requires a string list")

        normalized_sources.append(source)
    return normalized_sources


def standards_summary(results: list[StandardsResult]) -> dict[str, int]:
    counts = {
        "new": 0,
        "changed": 0,
        "unchanged": 0,
        "skipped": 0,
        "unavailable": 0,
        "errors": 0,
    }
    for result in results:
        if result.status in counts:
            counts[result.status] += 1
        if result.status == "unavailable" and result.required:
            counts["errors"] += 1
    return counts


def standards_exit_code(results: list[StandardsResult]) -> int:
    summary = standards_summary(results)
    if summary["errors"]:
        return 1
    if summary["new"] or summary["changed"]:
        return 2
    return 0


def _check_source(
    source: dict[str, Any],
    *,
    snapshots_dir: Path,
    update: bool,
    include_commands: bool,
    timeout: int,
) -> StandardsResult:
    source_id = str(source["id"])
    source_type = str(source["type"])
    required = bool(source.get("required", source_type == "url"))
    title = str(source.get("title") or source_id)
    target = source.get("target")
    target = str(target) if target is not None else None
    source_ref = _source_ref(source)

    if source_type == "command" and not include_commands:
        return StandardsResult(
            id=source_id,
            target=target,
            title=title,
            source_type=source_type,
            source=source_ref,
            status="skipped",
            required=required,
            message="command source skipped; rerun with --include-commands",
        )

    try:
        payload = _collect_payload(source, timeout=timeout)
    except (OSError, subprocess.SubprocessError, urllib.error.URLError) as exc:
        return StandardsResult(
            id=source_id,
            target=target,
            title=title,
            source_type=source_type,
            source=source_ref,
            status="unavailable",
            required=required,
            message=str(exc),
        )

    observed_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    digest = hashlib.sha256(payload).hexdigest()
    snapshot_path = snapshots_dir / f"{source_id}.json"
    previous = _read_snapshot(snapshot_path)
    previous_digest = previous.get("sha256") if previous else None
    status = "unchanged"
    if previous_digest is None:
        status = "new"
    elif previous_digest != digest:
        status = "changed"

    result = StandardsResult(
        id=source_id,
        target=target,
        title=title,
        source_type=source_type,
        source=source_ref,
        status=status,
        required=required,
        sha256=digest,
        previous_sha256=previous_digest,
        byte_count=len(payload),
        observed_at=observed_at,
    )

    if update and status in {"new", "changed"}:
        _write_snapshot(snapshot_path, source, result)
    return result


def _collect_payload(source: dict[str, Any], *, timeout: int) -> bytes:
    source_type = str(source["type"])
    if source_type == "url":
        request = urllib.request.Request(
            str(source["url"]),
            headers={"User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
        return _normalize_payload(raw, str(source.get("normalize", "html")))

    completed = subprocess.run(
        source["command"],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    payload = (
        f"exit={completed.returncode}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    return _normalize_text(payload).encode("utf-8")


def _normalize_payload(raw: bytes, mode: str) -> bytes:
    if mode == "raw":
        return raw
    text = raw.decode("utf-8", errors="replace")
    if mode == "html":
        text = re.sub(r"(?is)<(script|style|svg)[^>]*>.*?</\1>", " ", text)
        text = re.sub(r"(?s)<!--.*?-->", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = html.unescape(text)
    elif mode != "text":
        raise SatchelError(f"unsupported standards normalization mode: {mode}")
    return _normalize_text(text).encode("utf-8")


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def _read_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SatchelError(f"standards snapshot must be a JSON object: {path}")
    return raw


def _write_snapshot(path: Path, source: dict[str, Any], result: StandardsResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "schema": "satchel-standards-snapshot/v0",
        "id": result.id,
        "target": result.target,
        "title": result.title,
        "type": result.source_type,
        "source": _snapshot_source(source),
        "normalize": source.get("normalize", "html" if result.source_type == "url" else "text"),
        "sha256": result.sha256,
        "byte_count": result.byte_count,
        "observed_at": result.observed_at,
    }
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_ref(source: dict[str, Any]) -> str:
    if source["type"] == "url":
        return str(source["url"])
    return " ".join(source["command"])


def _snapshot_source(source: dict[str, Any]) -> str | list[str]:
    if source["type"] == "url":
        return str(source["url"])
    return list(source["command"])
