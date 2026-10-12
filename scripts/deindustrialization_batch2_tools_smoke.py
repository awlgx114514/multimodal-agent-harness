"""Structural contract smoke for the Batch 2 Diagnosis tool catalog."""

from __future__ import annotations

from industrial_ops_agent.agent.tool_catalog import diagnosis_tool_registry


EXPECTED = {
    "asset.get",
    "warranty.get",
    "parts.availability",
    "schedule.availability",
    "work_orders.history",
}


def main() -> None:
    registry = diagnosis_tool_registry()
    actual = {item.tool_id for item in registry.definitions()}
    if actual != EXPECTED:
        raise AssertionError(f"diagnosis catalog mismatch: {sorted(actual)}")
    print("DEINDUSTRIALIZATION_BATCH2_TOOLS_PASS")


if __name__ == "__main__":
    main()
