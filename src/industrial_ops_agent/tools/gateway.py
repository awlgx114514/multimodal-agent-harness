"""Tool governance and the read-only Diagnosis tool boundary."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from threading import Lock
from time import monotonic
from typing import Any
from uuid import uuid4

from jsonschema.exceptions import ValidationError
from sqlalchemy import select

from industrial_ops_agent.auth.identity import IdentityContext
from industrial_ops_agent.auth.policy import Action, Authorizer, ResourceContext
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    AssetSiteLinkRecord,
    ToolCallRecord,
)
from industrial_ops_agent.tools.authority import validate_attested_tool_fact
from industrial_ops_agent.tools.contracts import (
    EnterpriseToolError,
    ReadonlyToolAdapter,
    ToolRateLimiter,
    ToolTransportBinding,
    ToolTransportBindingProvider,
)
from industrial_ops_agent.tools.registry import ToolDefinition, ToolRegistry


@dataclass(frozen=True, slots=True)
class ToolInvocationResult:
    status: str
    tool_call_id: str
    data: dict[str, Any] | None = None
    handoff: dict[str, Any] | None = None


class ToolRateLimitExceeded(RuntimeError):
    pass


class ProcessToolRateLimiter:
    """Bounded in-process limiter; distributed deployments replace it with Redis."""

    def __init__(self) -> None:
        self._calls: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def require(self, tenant_id: str, tool_id: str, limit: int) -> None:
        now = monotonic()
        key = (tenant_id, tool_id)
        with self._lock:
            calls = self._calls[key]
            while calls and calls[0] <= now - 60:
                calls.popleft()
            if len(calls) >= limit:
                raise ToolRateLimitExceeded("tool_rate_limit_exceeded")
            calls.append(now)


class ToolGateway:
    """Governed invocation for the domain-owned read-only tool catalog."""

    def __init__(
        self,
        database: Database,
        authorizer: Authorizer,
        registry: ToolRegistry,
        readonly: ReadonlyToolAdapter | None = None,
        rate_limiter: ToolRateLimiter | None = None,
    ) -> None:
        self._database = database
        self._authorizer = authorizer
        self._registry = registry
        if readonly is None and registry.definitions():
            raise ValueError("registered read-only tools require an adapter")
        self._readonly = readonly
        self._rate_limiter = rate_limiter or ProcessToolRateLimiter()

    def definitions(self) -> tuple[ToolDefinition, ...]:
        return self._registry.definitions()

    def transport_bindings(self) -> tuple[ToolTransportBinding, ...]:
        if not isinstance(self._readonly, ToolTransportBindingProvider):
            return ()
        bindings: list[ToolTransportBinding] = []
        for definition in self._registry.definitions():
            if definition.risk_tier not in {"T0", "T1"}:
                continue
            try:
                bindings.append(self._readonly.transport_binding(definition.tool_id))
            except EnterpriseToolError:
                continue
        return tuple(bindings)

    def mcp_server_versions(self) -> dict[str, str]:
        versions: dict[str, str] = {}
        for binding in self.transport_bindings():
            if (
                binding.transport == "MCP_STREAMABLE_HTTP"
                and binding.server_id is not None
                and binding.server_version is not None
            ):
                existing = versions.setdefault(binding.server_id, binding.server_version)
                if existing != binding.server_version:
                    raise RuntimeError("MCP server has conflicting configured versions")
        return dict(sorted(versions.items()))

    def invoke(
        self,
        identity: IdentityContext,
        *,
        tool_id: str,
        version: str,
        parameters: dict[str, Any],
        request_id: str,
        agent_run_id: str | None = None,
    ) -> ToolInvocationResult:
        """Validate, authorize, invoke, attest and audit one read-only tool."""

        try:
            definition = self._registry.get(tool_id, version)
        except ValueError:
            self._authorizer.record_guard_decision(
                identity,
                action="tool.registry.resolve",
                decision="deny",
                reason_code="tool_not_registered",
                request_id=request_id,
                resource_id=tool_id,
            )
            raise
        try:
            definition.validate(parameters)
        except ValidationError:
            self._authorizer.record_guard_decision(
                identity,
                action="tool.schema.validate",
                decision="deny",
                reason_code="tool_parameters_invalid",
                request_id=request_id,
                resource_id=tool_id,
            )
            raise
        self._rate_limiter.require(identity.tenant_id, tool_id, definition.rate_limit_per_minute)
        tool_call_id = f"tool-call-{uuid4().hex}"
        now = datetime.now(UTC)
        self._authorizer.require(
            identity,
            Action(definition.required_action),
            self._readonly_resource_context(identity, tool_id, parameters),
            request_id=request_id,
        )
        try:
            if self._readonly is None:
                raise EnterpriseToolError("readonly_adapter_unavailable")
            data = self._readonly.invoke(tool_id, parameters)
            validate_attested_tool_fact(tool_id, data)
        except EnterpriseToolError as exc:
            self._record_tool_call(
                identity,
                tool_call_id=tool_call_id,
                agent_run_id=agent_run_id,
                tool_id=tool_id,
                version=version,
                risk_tier=definition.risk_tier,
                status="FAILED",
                parameters=parameters,
                output_metadata={"reason": exc.reason, **self._transport_metadata(tool_id)},
                now=now,
            )
            raise
        self._record_tool_call(
            identity,
            tool_call_id=tool_call_id,
            agent_run_id=agent_run_id,
            tool_id=tool_id,
            version=version,
            risk_tier=definition.risk_tier,
            status="SUCCEEDED",
            parameters=parameters,
            output_metadata={
                **{key: data[key] for key in ("source", "source_record_id", "as_of")},
                "authority": data["authority"],
                **self._transport_metadata(tool_id),
            },
            now=now,
        )
        return ToolInvocationResult("SUCCEEDED", tool_call_id, data=data)

    def _transport_metadata(self, tool_id: str) -> dict[str, Any]:
        if not isinstance(self._readonly, ToolTransportBindingProvider):
            return {"transport": "IN_PROCESS_ADAPTER"}
        try:
            binding = self._readonly.transport_binding(tool_id)
        except EnterpriseToolError:
            return {"transport": "UNKNOWN"}
        return {
            "transport": binding.transport,
            "remote_tool_name": binding.remote_tool_name,
            "server_id": binding.server_id,
            "server_version": binding.server_version,
            "required_scopes": list(binding.required_scopes),
            "input_schema_digest": binding.input_schema_digest,
        }

    def _readonly_resource_context(
        self,
        identity: IdentityContext,
        tool_id: str,
        parameters: dict[str, Any],
    ) -> ResourceContext:
        asset_id = str(parameters["asset_id"])
        if asset_id in identity.asset_ids:
            return ResourceContext(identity.tenant_id, resource_id=tool_id, asset_id=asset_id)
        if identity.site_ids:
            with self._database.transaction(identity.tenant_context) as session:
                site_id = session.scalar(
                    select(AssetSiteLinkRecord.site_id).where(
                        AssetSiteLinkRecord.tenant_id == identity.tenant_id,
                        AssetSiteLinkRecord.asset_id == asset_id,
                    )
                )
            if site_id in identity.site_ids:
                return ResourceContext(identity.tenant_id, resource_id=tool_id, site_id=site_id)
        return ResourceContext(identity.tenant_id, resource_id=tool_id, asset_id=asset_id)

    def _record_tool_call(
        self,
        identity: IdentityContext,
        *,
        tool_call_id: str,
        agent_run_id: str | None,
        tool_id: str,
        version: str,
        risk_tier: str,
        status: str,
        parameters: dict[str, Any],
        output_metadata: dict[str, Any],
        now: datetime,
    ) -> None:
        with self._database.transaction(identity.tenant_context) as session:
            session.add(
                ToolCallRecord(
                    tool_call_id=tool_call_id,
                    tenant_id=identity.tenant_id,
                    agent_run_id=agent_run_id,
                    tool_id=tool_id,
                    tool_version=version,
                    risk_tier=risk_tier,
                    status=status,
                    input_digest=_digest(parameters),
                    output_metadata=output_metadata,
                    created_at=now,
                    updated_at=now,
                )
            )


def _digest(value: dict[str, Any]) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
