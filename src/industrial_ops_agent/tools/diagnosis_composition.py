"""Composition helpers for the read-only Industrial Diagnosis tool boundary."""

from __future__ import annotations

from industrial_ops_agent.agent.tool_catalog import diagnosis_tool_registry
from industrial_ops_agent.auth.policy import Authorizer
from industrial_ops_agent.config import Settings
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.secrets import SecretProvider
from industrial_ops_agent.tools.contracts import ReadonlyToolAdapter
from industrial_ops_agent.tools.factory import build_enterprise_adapters
from industrial_ops_agent.tools.gateway import ToolGateway


def build_diagnosis_tool_gateway(
    database: Database,
    authorizer: Authorizer,
    *,
    readonly: ReadonlyToolAdapter | None,
    enterprise_tools_enabled: bool = True,
) -> ToolGateway:
    """Build a Diagnosis gateway with only the domain-owned read catalog."""

    return ToolGateway(
        database,
        authorizer,
        diagnosis_tool_registry(enterprise_tools_enabled=enterprise_tools_enabled),
        readonly=readonly,
    )


def build_diagnosis_readonly_adapter(
    settings: Settings,
    secret_provider: SecretProvider,
) -> ReadonlyToolAdapter | None:
    """Select a Diagnosis read adapter without constructing mutation adapters."""

    registry = diagnosis_tool_registry(enterprise_tools_enabled=settings.enterprise_tools_enabled)
    return build_enterprise_adapters(settings, secret_provider, registry).readonly
