"""Industrial Diagnosis ownership of its read-only tool catalog."""

from industrial_ops_agent.tools.registry import ToolRegistry, diagnosis_readonly_tool_definitions


def diagnosis_tool_registry(*, enterprise_tools_enabled: bool = True) -> ToolRegistry:
    return ToolRegistry(
        list(diagnosis_readonly_tool_definitions()) if enterprise_tools_enabled else []
    )
