"""Select enterprise adapters without leaking credentials into typed settings."""

from __future__ import annotations

from dataclasses import dataclass

from industrial_ops_agent.config import EnterpriseToolsMode, Environment, Settings
from industrial_ops_agent.secrets import SecretName, SecretProvider
from industrial_ops_agent.tools.contracts import ReadonlyToolAdapter
from industrial_ops_agent.tools.enterprise_http import EnterpriseHttpAdapter
from industrial_ops_agent.tools.mcp import (
    ClientCredentialsMcpTokenProvider,
    McpReadonlyAdapter,
    SdkMcpInvocationTransport,
)
from industrial_ops_agent.tools.registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class EnterpriseAdapters:
    readonly: ReadonlyToolAdapter | None


def build_enterprise_adapters(
    settings: Settings,
    secret_provider: SecretProvider,
    registry: ToolRegistry,
) -> EnterpriseAdapters:
    if not settings.enterprise_tools_enabled:
        return EnterpriseAdapters(readonly=None)
    if settings.enterprise_tools_mode is EnterpriseToolsMode.SYNTHETIC:
        raise ValueError("Synthetic enterprise tools are forbidden in runtime composition")
    if not settings.enterprise_tool_gateway_url.strip():
        raise ValueError("Enterprise tool gateway URL is required when enabled")
    allow_plain_http = settings.environment in {Environment.LOCAL, Environment.TEST}
    http_adapter: EnterpriseHttpAdapter | None = None
    if settings.use_http_enterprise_tools or settings.use_mcp_enterprise_tools:
        http_adapter = EnterpriseHttpAdapter(
            settings.enterprise_tool_gateway_url,
            secret_provider.get(SecretName.ENTERPRISE_TOOL_GATEWAY_TOKEN),
            timeout_seconds=settings.enterprise_tool_timeout_seconds,
            allow_plain_http=allow_plain_http,
        )
    if settings.use_mcp_enterprise_tools:
        token_provider = ClientCredentialsMcpTokenProvider(
            token_url=settings.enterprise_mcp_token_url,
            client_id=settings.enterprise_mcp_client_id,
            client_secret=secret_provider.get(SecretName.ENTERPRISE_MCP_CLIENT_SECRET),
            resource=settings.enterprise_mcp_resource,
            allowed_scopes=settings.enterprise_mcp_allowed_scopes,
            timeout_seconds=settings.enterprise_mcp_timeout_seconds,
            allow_plain_http=allow_plain_http,
        )
        readonly = McpReadonlyAdapter(
            server_id=settings.enterprise_mcp_server_id,
            server_version=settings.enterprise_mcp_server_version,
            definitions=registry.definitions(),
            token_provider=token_provider,
            transport=SdkMcpInvocationTransport(
                settings.enterprise_mcp_server_url,
                timeout_seconds=settings.enterprise_mcp_timeout_seconds,
                allow_plain_http=allow_plain_http,
            ),
            allowed_scopes=settings.enterprise_mcp_allowed_scopes,
        )
        return EnterpriseAdapters(
            readonly=readonly,
        )
    if settings.use_http_enterprise_tools:
        if http_adapter is None:
            raise ValueError("HTTP mode requires the enterprise HTTP adapter")
        return EnterpriseAdapters(
            readonly=http_adapter,
        )
    raise ValueError("Enterprise tool mode has no configured adapter")
