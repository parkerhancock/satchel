from __future__ import annotations

from satchel.core import ManifestData
from satchel.targets.anthropic import AnthropicAdapter
from satchel.targets.antigravity import AntigravityAdapter
from satchel.targets.base import TargetAdapter
from satchel.targets.chatgpt import ChatGPTAdapter
from satchel.targets.claude import ClaudeAdapter
from satchel.targets.codex import CodexAdapter
from satchel.targets.copilot import CopilotAdapter
from satchel.targets.cowork import CoworkAdapter

_ADAPTERS: tuple[TargetAdapter, ...] = (
    CodexAdapter(),
    ClaudeAdapter(),
    CopilotAdapter(),
    AntigravityAdapter(),
    ChatGPTAdapter(),
    AnthropicAdapter(),
    CoworkAdapter(),
)


def all_adapters() -> tuple[TargetAdapter, ...]:
    return _ADAPTERS


def adapter_names() -> tuple[str, ...]:
    return tuple(adapter.name for adapter in _ADAPTERS)


def adapter_for_target(name: str) -> TargetAdapter | None:
    for adapter in _ADAPTERS:
        if adapter.name == name:
            return adapter
    return None


def enabled_adapters(data: ManifestData, target: str | None = None) -> list[TargetAdapter]:
    adapters = [adapter for adapter in _ADAPTERS if adapter.enabled(data)]
    if target is None:
        return adapters
    return [adapter for adapter in adapters if adapter.name == target]
