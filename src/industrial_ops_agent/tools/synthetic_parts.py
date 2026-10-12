"""Deterministic synthetic inventory facts for the read-only tool contract."""

from __future__ import annotations

from datetime import UTC, datetime

from industrial_ops_agent.tools.authority import attest_tool_fact, authoritative_source


class SyntheticPartsAvailabilityReader:
    """Provide stable availability facts without any inventory mutation state."""

    def check_availability(self, *, part_number: str, quantity: int) -> dict[str, object]:
        return attest_tool_fact(
            "parts.availability",
            {
                "part_number": part_number,
                "requested_quantity": quantity,
                "available_quantity": 8,
                "available": quantity <= 8,
                "source": authoritative_source("parts.availability", "synthetic"),
                "source_record_id": f"stock-{part_number}",
                "as_of": datetime.now(UTC),
            },
            profile="synthetic",
        )
