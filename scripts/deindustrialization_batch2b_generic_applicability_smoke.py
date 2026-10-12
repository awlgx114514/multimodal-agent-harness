"""RED/GREEN contract smoke for domain-neutral Knowledge applicability."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

from industrial_ops_agent.knowledge.applicability import ApplicabilityFilter
from industrial_ops_agent.knowledge.models import RetrievalQuery

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "src" / "industrial_ops_agent" / "knowledge"


def main() -> None:
    filter_item = ApplicabilityFilter(key="product.version", values=frozenset({"v2"}))
    assert filter_item.matches({"product.version": ["v2"]})
    assert not filter_item.matches({"product.version": ["v1"]})
    query = RetrievalQuery(
        tenant_id="tenant-generic",
        subject_id="subject-generic",
        roles=frozenset(),
        release_id="release-generic",
        applicability=(filter_item,),
        query="pressure alarm",
        as_of=datetime.now(UTC),
    )
    assert query.applicability == (filter_item,)
    source = (KNOWLEDGE / "applicability.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not {
        "device_family",
        "device_model",
        "asset",
        "equipment",
    }.intersection(node.id for node in ast.walk(tree) if isinstance(node, ast.Name))
    print("DEINDUSTRIALIZATION_BATCH2B_GENERIC_APPLICABILITY_PASS")


if __name__ == "__main__":
    main()
