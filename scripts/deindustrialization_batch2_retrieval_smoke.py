"""Structural contract smoke for the Batch 2 retrieval boundary."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "industrial_ops_agent"


def _names(path: Path) -> set[str]:
    return {
        node.name
        for node in ast.parse(path.read_text(encoding="utf-8")).body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }


def main() -> None:
    applicability = SRC / "knowledge" / "applicability.py"
    if not applicability.exists() or "ApplicabilityFilter" not in _names(applicability):
        raise AssertionError("generic applicability contract is missing")
    retrieval = (SRC / "knowledge" / "retrieval.py").read_text(encoding="utf-8")
    if "query.device_model" in retrieval or "query.device_family" in retrieval:
        raise AssertionError("HybridRetriever still reads device semantics")
    print("DEINDUSTRIALIZATION_BATCH2_RETRIEVAL_PASS")


if __name__ == "__main__":
    main()
