from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from satchel.generate import build_outputs, portability_report, stale_outputs, write_outputs
from satchel.manifest import load_manifest, validate_manifest


def test_generates_codex_and_claude_manifests(tmp_path: Path) -> None:
    _write_package(tmp_path)
    root, data = load_manifest(tmp_path)

    diagnostics = validate_manifest(root, data)
    assert [d for d in diagnostics if d.severity == "error"] == []

    outputs = build_outputs(root, data)
    write_outputs(outputs)

    codex = json.loads((tmp_path / ".codex-plugin/plugin.json").read_text())
    claude = json.loads((tmp_path / ".claude-plugin/plugin.json").read_text())

    assert codex["name"] == "demo-plugin"
    assert codex["skills"] == "./skills/"
    assert codex["mcpServers"] == "./.mcp.json"
    assert codex["interface"]["displayName"] == "Demo Plugin"
    assert claude["displayName"] == "Demo Plugin"
    assert claude["skills"] == "./skills/"


def test_codex_component_paths_are_relative_to_nested_plugin_root(tmp_path: Path) -> None:
    _write_package(tmp_path)
    plugin_root = tmp_path / "plugins/demo-plugin"
    plugin_root.mkdir(parents=True)
    (tmp_path / ".mcp.json").replace(plugin_root / ".mcp.json")
    (tmp_path / "skills").replace(plugin_root / "skills")

    manifest_path = tmp_path / "satchel.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    data["components"]["mcp"]["path"] = "./plugins/demo-plugin/.mcp.json"
    data["components"]["skills"]["path"] = "./plugins/demo-plugin/skills"
    data["targets"]["codex"]["manifest"] = "./plugins/demo-plugin/.codex-plugin/plugin.json"
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    root, manifest = load_manifest(tmp_path)
    write_outputs(build_outputs(root, manifest))

    codex = json.loads((plugin_root / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    assert codex["mcpServers"] == "./.mcp.json"
    assert codex["skills"] == "./skills/"


def test_stale_output_detection(tmp_path: Path) -> None:
    _write_package(tmp_path)
    root, data = load_manifest(tmp_path)
    outputs = build_outputs(root, data)

    missing = stale_outputs(outputs)
    assert len(missing) == 2

    write_outputs(outputs)
    assert stale_outputs(outputs) == []

    (tmp_path / ".codex-plugin/plugin.json").write_text("{}\n", encoding="utf-8")
    stale = stale_outputs(outputs)
    assert len(stale) == 1
    assert "stale" in stale[0].message


def test_rejects_paths_that_escape_package_root(tmp_path: Path) -> None:
    _write_package(tmp_path)
    manifest_path = tmp_path / "satchel.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    data["targets"]["codex"]["manifest"] = "../plugin.json"
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    root, manifest = load_manifest(tmp_path)
    diagnostics = validate_manifest(root, manifest)

    assert any("escapes package root" in diagnostic.message for diagnostic in diagnostics)


def test_generates_marketplaces_when_declared(tmp_path: Path) -> None:
    _write_package(tmp_path, include_marketplaces=True)
    root, data = load_manifest(tmp_path)

    diagnostics = validate_manifest(root, data)
    assert [d for d in diagnostics if d.severity == "error"] == []

    outputs = build_outputs(root, data)
    write_outputs(outputs)

    codex = json.loads((tmp_path / ".agents/plugins/marketplace.json").read_text())
    claude = json.loads((tmp_path / ".claude-plugin/marketplace.json").read_text())

    assert codex["name"] == "demo-marketplace"
    assert codex["plugins"][0]["source"]["source"] == "url"
    assert codex["plugins"][0]["policy"]["installation"] == "AVAILABLE"
    assert claude["name"] == "demo-marketplace"
    assert claude["plugins"][0]["source"]["source"] == "github"
    assert claude["plugins"][0]["skills"] == ["./skills/example"]


def test_marketplaces_accept_string_author_as_owner(tmp_path: Path) -> None:
    _write_package(tmp_path, include_marketplaces=True, include_copilot=True)
    manifest_path = tmp_path / "satchel.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    data["author"] = "Example Team"
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    root, data = load_manifest(tmp_path)
    write_outputs(build_outputs(root, data))

    claude = json.loads((tmp_path / ".claude-plugin/marketplace.json").read_text())
    copilot = json.loads((tmp_path / ".github/plugin/marketplace.json").read_text())
    codex_manifest = json.loads((tmp_path / ".codex-plugin/plugin.json").read_text())
    claude_manifest = json.loads((tmp_path / ".claude-plugin/plugin.json").read_text())
    copilot_manifest = json.loads((tmp_path / ".github/plugin/plugin.json").read_text())
    assert claude["owner"] == {"name": "Example Team"}
    assert copilot["owner"] == {"name": "Example Team"}
    assert codex_manifest["author"] == {"name": "Example Team"}
    assert claude_manifest["author"] == {"name": "Example Team"}
    assert copilot_manifest["author"] == {"name": "Example Team"}


def test_claude_and_copilot_marketplaces_require_owner(tmp_path: Path) -> None:
    from satchel.validate import marketplace_diagnostics

    _write_package(tmp_path, include_marketplaces=True, include_copilot=True)
    manifest_path = tmp_path / "satchel.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    data.pop("author")
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    root, data = load_manifest(tmp_path)
    diagnostics = marketplace_diagnostics(root, data)
    missing_owner = {
        diagnostic.target
        for diagnostic in diagnostics
        if diagnostic.code == "SATCHEL_MARKETPLACE_OWNER_MISSING"
    }
    assert missing_owner == {"claude", "copilot"}

    data["author"] = {"url": "https://example.com"}
    diagnostics = marketplace_diagnostics(root, data)
    assert {
        diagnostic.target
        for diagnostic in diagnostics
        if diagnostic.code == "SATCHEL_MARKETPLACE_OWNER_MISSING"
    } == {"claude", "copilot"}


def test_patch_marketplaces_accept_preserved_owner(tmp_path: Path) -> None:
    from satchel.validate import marketplace_diagnostics

    _write_package(tmp_path, include_marketplaces=True, include_copilot=True)
    manifest_path = tmp_path / "satchel.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    data.pop("author")
    for target_name in ("claude", "copilot"):
        data["targets"][target_name]["marketplace"]["patch"] = True
        marketplace_path = tmp_path / data["targets"][target_name]["marketplace"]["path"]
        marketplace_path.parent.mkdir(parents=True, exist_ok=True)
        marketplace_path.write_text(
            json.dumps({"owner": {"name": "Host Owner"}}, indent=2) + "\n",
            encoding="utf-8",
        )
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    root, data = load_manifest(tmp_path)
    diagnostics = marketplace_diagnostics(root, data, release=True)
    assert not any(
        diagnostic.code == "SATCHEL_MARKETPLACE_OWNER_MISSING"
        for diagnostic in diagnostics
    )

    write_outputs(build_outputs(root, data))
    for target_name in ("claude", "copilot"):
        marketplace_path = tmp_path / data["targets"][target_name]["marketplace"]["path"]
        assert json.loads(marketplace_path.read_text())["owner"] == {"name": "Host Owner"}

    report = portability_report(root, data)
    assert "  claude: remote-ready" in report
    assert "  copilot: remote-ready" in report


def test_marketplace_report_marks_missing_owner_incomplete(tmp_path: Path) -> None:
    _write_package(tmp_path, include_marketplaces=True, include_copilot=True)
    manifest_path = tmp_path / "satchel.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    data.pop("author")
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    root, data = load_manifest(tmp_path)
    report = portability_report(root, data)
    assert "  claude: incomplete (owner missing)" in report
    assert "  copilot: incomplete (owner missing)" in report


def test_claude_manifest_maps_custom_component_paths(tmp_path: Path) -> None:
    _write_package(tmp_path)
    for path, content in (
        ("commands/check.md", "Check the project.\n"),
        ("agents/reviewer.md", "Review the project.\n"),
        ("hooks/custom.json", "{}\n"),
        ("config/lsp.json", "{}\n"),
    ):
        component_path = tmp_path / path
        component_path.parent.mkdir(parents=True, exist_ok=True)
        component_path.write_text(content, encoding="utf-8")

    manifest_path = tmp_path / "satchel.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    data["components"].update(
        {
            "commands": {"path": "./commands"},
            "agents": {"path": "./agents"},
            "hooks": {"path": "./hooks/custom.json"},
            "lsp": {"path": "./config/lsp.json"},
        }
    )
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    root, data = load_manifest(tmp_path)
    write_outputs(build_outputs(root, data))
    claude = json.loads((tmp_path / ".claude-plugin/plugin.json").read_text())

    assert claude["skills"] == "./skills/"
    assert claude["commands"] == "./commands/"
    assert claude["agents"] == "./agents/"
    assert claude["hooks"] == "./hooks/custom.json"
    assert claude["mcpServers"] == "./.mcp.json"
    assert claude["lspServers"] == "./config/lsp.json"


def test_patches_marketplace_when_enabled(tmp_path: Path) -> None:
    _write_package(tmp_path, include_marketplaces=True)
    manifest_path = tmp_path / "satchel.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    data["targets"]["codex"]["marketplace"]["patch"] = True
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    marketplace_path = tmp_path / ".agents/plugins/marketplace.json"
    marketplace_path.parent.mkdir(parents=True)
    marketplace_path.write_text(
        json.dumps(
            {
                "name": "host-marketplace",
                "interface": {
                    "displayName": "Host Name",
                    "subtitle": "Keep this",
                },
                "plugins": [
                    {
                        "name": "other-plugin",
                        "source": "./other",
                    },
                    {
                        "name": "demo-plugin",
                        "source": "./stale",
                        "policy": {
                            "installation": "BLOCKED",
                            "x-host": "keep",
                        },
                        "x-plugin": "keep",
                    },
                ],
                "x-marketplace": "keep",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    root, data = load_manifest(tmp_path)
    write_outputs(build_outputs(root, data))
    patched = json.loads(marketplace_path.read_text())
    demo_plugin = patched["plugins"][1]

    assert patched["name"] == "demo-marketplace"
    assert patched["x-marketplace"] == "keep"
    assert patched["interface"]["displayName"] == "Demo Plugin"
    assert patched["interface"]["subtitle"] == "Keep this"
    assert patched["plugins"][0]["name"] == "other-plugin"
    assert demo_plugin["source"]["url"] == "https://github.com/example/demo-plugin.git"
    assert demo_plugin["policy"]["installation"] == "AVAILABLE"
    assert demo_plugin["policy"]["authentication"] == "ON_INSTALL"
    assert demo_plugin["policy"]["x-host"] == "keep"
    assert demo_plugin["x-plugin"] == "keep"
    assert stale_outputs(build_outputs(root, data)) == []

    demo_plugin["source"] = "./stale"
    marketplace_path.write_text(json.dumps(patched, indent=2) + "\n", encoding="utf-8")
    stale = stale_outputs(build_outputs(root, data))

    assert len(stale) == 1
    assert stale[0].target == "codex-marketplace"


def test_generates_copilot_manifest_and_marketplace_when_declared(tmp_path: Path) -> None:
    _write_package(tmp_path, include_copilot=True)
    root, data = load_manifest(tmp_path)

    diagnostics = validate_manifest(root, data)
    assert [d for d in diagnostics if d.severity == "error"] == []

    write_outputs(build_outputs(root, data))

    manifest = json.loads((tmp_path / ".github/plugin/plugin.json").read_text())
    marketplace = json.loads((tmp_path / ".github/plugin/marketplace.json").read_text())

    assert manifest["name"] == "demo-plugin"
    assert manifest["skills"] == "./skills/"
    assert manifest["mcpServers"] == "./.mcp.json"
    assert marketplace["name"] == "demo-marketplace"
    assert marketplace["plugins"][0]["source"]["source"] == "github"


def test_normalizes_legacy_copilot_marketplace_source(tmp_path: Path) -> None:
    _write_package(tmp_path, include_copilot=True)
    manifest_path = tmp_path / "satchel.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    source = data["targets"]["copilot"]["marketplace"]["source"]
    source["type"] = source.pop("source")
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    root, data = load_manifest(tmp_path)
    diagnostics = validate_manifest(root, data)
    assert any(
        diagnostic.code == "SATCHEL_COPILOT_MARKETPLACE_SOURCE_LEGACY"
        for diagnostic in diagnostics
    )

    write_outputs(build_outputs(root, data))
    marketplace = json.loads((tmp_path / ".github/plugin/marketplace.json").read_text())
    source = marketplace["plugins"][0]["source"]
    assert source["source"] == "github"
    assert "type" not in source


def test_generates_antigravity_package_when_declared(tmp_path: Path) -> None:
    _write_package(tmp_path, include_antigravity=True)
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks/hooks.json").write_text('{"format": {"Stop": []}}\n', encoding="utf-8")
    (tmp_path / "agents/reviewer").mkdir(parents=True)
    (tmp_path / "agents/reviewer/AGENT.md").write_text("Review code.\n", encoding="utf-8")
    root, data = load_manifest(tmp_path)

    diagnostics = validate_manifest(root, data)
    assert [d for d in diagnostics if d.severity == "error"] == []

    write_outputs(build_outputs(root, data))

    output_root = tmp_path / ".agents/plugins/demo-plugin"
    manifest = json.loads((output_root / "plugin.json").read_text())
    mcp = json.loads((output_root / "mcp_config.json").read_text())
    hooks = json.loads((output_root / "hooks.json").read_text())

    assert manifest == {
        "$schema": "https://antigravity.google/schemas/v1/plugin.json",
        "name": "demo-plugin",
        "description": "Demo product-agnostic plugin.",
    }
    assert mcp == {"mcpServers": {}}
    assert hooks == {"format": {"Stop": []}}
    assert (output_root / "skills/example/SKILL.md").exists()
    assert (output_root / "agents/reviewer/AGENT.md").exists()


def test_generates_chatgpt_app_artifacts_when_declared(tmp_path: Path) -> None:
    _write_package(tmp_path, include_chatgpt=True)
    root, data = load_manifest(tmp_path)

    diagnostics = validate_manifest(root, data)
    assert [d for d in diagnostics if d.severity == "error"] == []

    write_outputs(build_outputs(root, data))

    manifest = json.loads((tmp_path / "chatgpt/app.json").read_text())
    submission = (tmp_path / "chatgpt/app-submission.md").read_text()

    assert manifest["format"] == "satchel-chatgpt-app/v0"
    assert manifest["name"] == "demo-plugin"
    assert manifest["app"]["displayName"] == "Demo ChatGPT App"
    assert manifest["app"]["mcpUrl"] == "https://example.com/mcp"
    assert manifest["app"]["privacyUrl"] == "https://example.com/privacy"
    assert manifest["app"]["safety"]["noClinicalAdvice"] is True
    assert manifest["compatibility"]["requireReadOnlyHints"] is True
    assert manifest["compatibility"]["requireSearchFetch"] is True
    assert "# ChatGPT App Submission: Demo ChatGPT App" in submission
    assert "MCP URL: https://example.com/mcp" in submission


def test_chatgpt_release_requires_policy_urls(tmp_path: Path) -> None:
    _write_package(tmp_path, include_chatgpt=True)
    manifest_path = tmp_path / "satchel.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    del data["targets"]["chatgpt"]["app"]["privacyUrl"]
    del data["targets"]["chatgpt"]["app"]["termsUrl"]
    del data["targets"]["chatgpt"]["app"]["supportUrl"]
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    root, data = load_manifest(tmp_path)
    write_outputs(build_outputs(root, data))

    from satchel.validate import marketplace_diagnostics

    diagnostics = marketplace_diagnostics(root, data, release=True, target="chatgpt")

    assert {diagnostic.component for diagnostic in diagnostics} == {
        "privacyUrl",
        "termsUrl",
        "supportUrl",
    }


def test_generates_anthropic_connector_artifacts_when_declared(tmp_path: Path) -> None:
    _write_package(tmp_path, include_anthropic=True)
    root, data = load_manifest(tmp_path)

    diagnostics = validate_manifest(root, data)
    assert [d for d in diagnostics if d.severity == "error"] == []

    write_outputs(build_outputs(root, data))

    manifest = json.loads((tmp_path / "anthropic/connector.json").read_text())
    submission = (tmp_path / "anthropic/connector-submission.md").read_text()
    form = (tmp_path / "anthropic/mcp-directory-form-questions.md").read_text()

    assert manifest["format"] == "satchel-anthropic-connector/v0"
    assert manifest["name"] == "demo-plugin"
    assert manifest["connector"]["displayName"] == "Demo Connector"
    assert manifest["connector"]["mcpUrl"] == "https://example.com/mcp"
    assert manifest["connector"]["privacyUrl"] == "https://example.com/privacy"
    assert manifest["connector"]["safety"]["noClinicalAdvice"] is True
    assert manifest["compatibility"]["requireReadOnlyHints"] is True
    assert manifest["compatibility"]["oauth"] is True
    assert manifest["compatibility"]["highRisk"] is True
    assert "# Anthropic Connectors Directory Submission: Demo Connector" in submission
    assert "MCP URL: https://example.com/mcp" in submission
    assert "claude.com/connectors" in submission
    # A source-linked preparation reference is emitted alongside the submission doc.
    assert "MCP Directory Submission Reference" in form
    assert "Submission Requirements Checklist" in form


def test_anthropic_release_requires_policy_urls(tmp_path: Path) -> None:
    _write_package(tmp_path, include_anthropic=True)
    manifest_path = tmp_path / "satchel.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    del data["targets"]["anthropic"]["connector"]["privacyUrl"]
    del data["targets"]["anthropic"]["connector"]["termsUrl"]
    del data["targets"]["anthropic"]["connector"]["supportUrl"]
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    root, data = load_manifest(tmp_path)
    write_outputs(build_outputs(root, data))

    from satchel.validate import marketplace_diagnostics

    diagnostics = marketplace_diagnostics(root, data, release=True, target="anthropic")

    assert {diagnostic.component for diagnostic in diagnostics} == {
        "privacyUrl",
        "termsUrl",
        "supportUrl",
    }


def test_generates_cowork_manifest_with_remote_connector(tmp_path: Path) -> None:
    _write_package(tmp_path, include_cowork=True)
    root, data = load_manifest(tmp_path)

    diagnostics = validate_manifest(root, data)
    assert [d for d in diagnostics if d.severity == "error"] == []

    write_outputs(build_outputs(root, data))

    manifest = json.loads((tmp_path / "cowork/manifest.json").read_text())

    assert manifest["manifestVersion"] == "1.28"
    assert manifest["name"]["short"] == "Demo Plugin"
    assert manifest["agentSkills"] == [{"folder": "./skills"}]
    connector = manifest["agentConnectors"][0]
    assert connector["displayName"] == "Demo Connector"
    assert connector["toolSource"]["remoteMcpServer"]["mcpServerUrl"] == "https://example.com/mcp"
    # authType "None" (the MCP-connector default, public/no-auth) shouldn't add an
    # authorization block -- only non-default auth types do.
    assert "authorization" not in connector["toolSource"]["remoteMcpServer"]


def test_cowork_flags_local_stdio_mcp_server(tmp_path: Path) -> None:
    """The one thing Cowork's agentConnectors can't absorb: a local/stdio MCP
    server declared via ``command``/``args`` instead of a remote ``url``.
    Cowork has no transport for it, so validation must flag it rather than
    silently drop it or guess at a URL.
    """
    _write_package(tmp_path, include_cowork=True)
    (tmp_path / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "local-example": {
                        "command": "uvx",
                        "args": [
                            "--from",
                            "example-mcp[mcp]==1.2.3",
                            "example-mcp-server",
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "satchel.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    del data["targets"]["cowork"]["connector"]
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    root, data = load_manifest(tmp_path)
    diagnostics = validate_manifest(root, data)

    errors = [d for d in diagnostics if d.severity == "error" and d.target == "cowork"]
    assert len(errors) == 1
    assert errors[0].code == "SATCHEL_COWORK_MCP_NOT_REMOTE"
    assert errors[0].component == "local-example"

    from satchel.core import SatchelError
    from satchel.manifest import raise_for_errors

    try:
        raise_for_errors(diagnostics)
    except SatchelError as exc:
        assert "local command (stdio)" in str(exc)
    else:
        raise AssertionError("raise_for_errors should have raised for the stdio mcp server")


def test_cowork_does_not_flag_remote_mcp_server(tmp_path: Path) -> None:
    _write_package(tmp_path, include_cowork=True)
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"hosted": {"url": "https://mcp.example.com/"}}}),
        encoding="utf-8",
    )

    root, data = load_manifest(tmp_path)
    diagnostics = validate_manifest(root, data)

    assert [d for d in diagnostics if d.code == "SATCHEL_COWORK_MCP_NOT_REMOTE"] == []


def test_cowork_requires_https_connector_url(tmp_path: Path) -> None:
    _write_package(tmp_path, include_cowork=True)
    manifest_path = tmp_path / "satchel.yaml"
    data = yaml.safe_load(manifest_path.read_text())
    data["targets"]["cowork"]["connector"]["mcpServerUrl"] = "http://example.com/mcp"
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    root, data = load_manifest(tmp_path)
    write_outputs(build_outputs(root, data))

    from satchel.validate import structural_diagnostics

    diagnostics = structural_diagnostics(root, data, target="cowork")
    codes = {d.code for d in diagnostics}
    assert "SATCHEL_COWORK_MCP_NOT_HTTPS" in codes


def test_satchel_package_generated_outputs_are_fresh() -> None:
    package_root = Path(__file__).resolve().parents[1]
    root, data = load_manifest(package_root)

    diagnostics = validate_manifest(root, data)
    assert [d for d in diagnostics if d.severity == "error"] == []
    assert stale_outputs(build_outputs(root, data)) == []


def test_committed_examples_generated_outputs_are_fresh() -> None:
    examples_root = Path(__file__).resolve().parents[1] / "examples"
    package_root = examples_root / "release-auditor"

    root, data = load_manifest(package_root)
    diagnostics = validate_manifest(root, data)
    assert [d for d in diagnostics if d.severity == "error"] == []
    assert stale_outputs(build_outputs(root, data)) == []


def test_json_schema_is_valid_json() -> None:
    package_root = Path(__file__).resolve().parents[1]
    schema = json.loads((package_root / "schemas/satchel.schema.json").read_text())

    assert schema["title"] == "Satchel Manifest"
    assert schema["properties"]["schema"]["const"] == "satchel/v0"


def test_generated_schema_reference_is_fresh() -> None:
    package_root = Path(__file__).resolve().parents[1]
    script = package_root / "scripts/generate_schema_docs.py"

    result = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=package_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def _write_package(
    root: Path,
    *,
    include_marketplaces: bool = False,
    include_copilot: bool = False,
    include_antigravity: bool = False,
    include_chatgpt: bool = False,
    include_anthropic: bool = False,
    include_cowork: bool = False,
) -> None:
    (root / "skills/example").mkdir(parents=True)
    (root / "skills/example/SKILL.md").write_text(
        """---
name: example
description: Example portable skill.
---

# Example
""",
        encoding="utf-8",
    )
    (root / ".mcp.json").write_text('{"mcpServers": {}}\n', encoding="utf-8")
    marketplace_yaml = (
        """
    marketplace:
      path: ./.agents/plugins/marketplace.json
      name: demo-marketplace
      source:
        source: url
        url: https://github.com/example/demo-plugin.git
      category: Productivity
      installation: AVAILABLE
      authentication: ON_INSTALL"""
        if include_marketplaces
        else ""
    )
    claude_marketplace_yaml = (
        """
    marketplace:
      path: ./.claude-plugin/marketplace.json
      name: demo-marketplace
      source:
        source: github
        repo: example/demo-plugin
      category: Productivity"""
        if include_marketplaces
        else ""
    )
    copilot_yaml = (
        """
  copilot:
    enabled: true
    manifest: ./.github/plugin/plugin.json
    marketplace:
      path: ./.github/plugin/marketplace.json
      name: demo-marketplace
      source:
        source: github
        repo: example/demo-plugin"""
        if include_copilot
        else ""
    )
    antigravity_components_yaml = (
        """
  hooks:
    path: ./hooks/hooks.json
  agents:
    path: ./agents"""
        if include_antigravity
        else ""
    )
    antigravity_target_yaml = (
        """
  antigravity:
    enabled: true
    experimental: true
    output: ./.agents/plugins/demo-plugin"""
        if include_antigravity
        else ""
    )
    chatgpt_yaml = (
        """
  chatgpt:
    enabled: true
    manifest: ./chatgpt/app.json
    app:
      displayName: Demo ChatGPT App
      shortDescription: Public data research app.
      mcpUrl: https://example.com/mcp
      privacyUrl: https://example.com/privacy
      termsUrl: https://example.com/terms
      supportUrl: https://example.com/support
      icon: ./assets/icon.png
      category: Research
      safety:
        noClinicalAdvice: true
        noPhi: true
    compatibility:
      requireReadOnlyHints: true
      requireSearchFetch: true"""
        if include_chatgpt
        else ""
    )
    anthropic_yaml = (
        """
  anthropic:
    enabled: true
    manifest: ./anthropic/connector.json
    connector:
      displayName: Demo Connector
      shortDescription: Public data research connector.
      mcpUrl: https://example.com/mcp
      privacyUrl: https://example.com/privacy
      termsUrl: https://example.com/terms
      supportUrl: https://example.com/support
      icon: ./assets/icon.png
      category: Research
      safety:
        noClinicalAdvice: true
        noPhi: true
    compatibility:
      requireReadOnlyHints: true
      oauth: true
      highRisk: true"""
        if include_anthropic
        else ""
    )
    cowork_yaml = (
        """
  cowork:
    enabled: true
    manifest: ./cowork/manifest.json
    connector:
      displayName: Demo Connector
      description: Public data research connector.
      mcpServerUrl: https://example.com/mcp
      authType: None"""
        if include_cowork
        else ""
    )
    (root / "satchel.yaml").write_text(
        f"""schema: satchel/v0
name: demo-plugin
version: 0.1.0
description: Demo product-agnostic plugin.
author:
  name: Example Team
keywords:
  - agents
  - skills
components:
  skills:
    path: ./skills
  mcp:
    path: ./.mcp.json
{antigravity_components_yaml}
targets:
  codex:
    enabled: true
    manifest: ./.codex-plugin/plugin.json
{marketplace_yaml}
    interface:
      displayName: Demo Plugin
      shortDescription: Demo product-agnostic plugin.
      category: Productivity
      capabilities:
        - Read
  claude:
    enabled: true
    manifest: ./.claude-plugin/plugin.json
{claude_marketplace_yaml}
    displayName: Demo Plugin
{copilot_yaml}
{antigravity_target_yaml}
{chatgpt_yaml}
{anthropic_yaml}
{cowork_yaml}
""",
        encoding="utf-8",
    )
