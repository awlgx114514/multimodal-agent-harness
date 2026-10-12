"""Mechanical checks for the Batch 2C Diagnosis composition boundary."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "src/industrial_ops_agent/orchestration/runner.py"
COMPOSITION = ROOT / "src/industrial_ops_agent/tools/diagnosis_composition.py"
FACTORY = ROOT / "src/industrial_ops_agent/tools/factory.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def main() -> None:
    runner_imports = _imports(RUNNER)
    composition_source = COMPOSITION.read_text(encoding="utf-8")
    composition_imports = _imports(COMPOSITION)
    factory_source = FACTORY.read_text(encoding="utf-8")
    factory_imports = _imports(FACTORY)

    assert "industrial_ops_agent.tools.factory" not in runner_imports
    assert "industrial_ops_agent.tools.registry" not in runner_imports
    assert "industrial_ops_agent.tools.diagnosis_composition" in runner_imports
    assert "industrial_ops_agent.tools.gateway" in composition_imports
    assert "industrial_ops_agent.tools.factory" in composition_imports
    assert "industrial_ops_agent.tools.synthetic_readonly" not in factory_imports
    for forbidden in (
        "PartsAdapter",
        "Procurement",
        "Refund",
        "Fsm",
        "Quotation",
        "work_order.draft",
        "equipment.control",
    ):
        assert forbidden not in composition_source, forbidden
        assert forbidden not in factory_source, forbidden
    print("DEINDUSTRIALIZATION_BATCH2C_DEPENDENCY_SCAN_PASS")


if __name__ == "__main__":
    main()
