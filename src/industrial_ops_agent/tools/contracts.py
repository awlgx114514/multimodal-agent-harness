"""Stable contracts shared by governed tool adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ToolTransportBinding:
    """Non-secret deployment identity for one governed tool transport."""

    transport: str
    local_tool_id: str
    remote_tool_name: str
    server_id: str | None = None
    server_version: str | None = None
    required_scopes: tuple[str, ...] = ()
    input_schema_digest: str | None = None


class EnterpriseToolError(RuntimeError):
    """Stable external-adapter failure without response bodies or credentials."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class ReadonlyToolAdapter(Protocol):
    def invoke(self, tool_id: str, parameters: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class ToolTransportBindingProvider(Protocol):
    def transport_binding(self, tool_id: str) -> ToolTransportBinding: ...


class ToolRateLimiter(Protocol):
    def require(self, tenant_id: str, tool_id: str, limit: int) -> None: ...
