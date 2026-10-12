"""Closed versioned registry for model-visible tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    tool_id: str
    version: str
    risk_tier: str
    input_schema: dict[str, Any]
    required_action: str
    approval_required: bool
    idempotent: bool
    timeout_seconds: int
    max_attempts: int
    rate_limit_per_minute: int
    compensation: str

    def validate(self, parameters: dict[str, Any]) -> None:
        Draft202012Validator(self.input_schema).validate(parameters)


class ToolRegistry:
    def __init__(self, definitions: list[ToolDefinition]) -> None:
        self._definitions = {(item.tool_id, item.version): item for item in definitions}

    def get(self, tool_id: str, version: str) -> ToolDefinition:
        try:
            return self._definitions[(tool_id, version)]
        except KeyError as exc:
            raise ValueError("tool_not_registered") from exc

    def definitions(self) -> tuple[ToolDefinition, ...]:
        """Return the immutable registry catalog in a stable presentation order."""

        return tuple(
            sorted(
                self._definitions.values(),
                key=lambda item: (item.risk_tier, item.tool_id, item.version),
            )
        )


def diagnosis_readonly_tool_definitions() -> tuple[ToolDefinition, ...]:
    """Definitions shared by a domain-owned read-only catalog and the full catalog."""
    readonly = {
        "type": "object",
        "properties": {"asset_id": {"type": "string", "minLength": 1}},
        "required": ["asset_id"],
        "additionalProperties": False,
    }
    return tuple(
        ToolDefinition(tool, "1.0.0", "T0", readonly, "asset.read", False, True, 5, 2, 60, "none")
        for tool in (
            "asset.get",
            "warranty.get",
            "parts.availability",
            "schedule.availability",
            "work_orders.history",
        )
    )


def default_tool_registry() -> ToolRegistry:
    return ToolRegistry(list(diagnosis_readonly_tool_definitions()))
