"""Mechanical guard for the reusable applicability boundary."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REUSABLE_FILES = (
    ROOT / "src" / "industrial_ops_agent" / "knowledge" / "applicability.py",
    ROOT / "src" / "industrial_ops_agent" / "knowledge" / "models.py",
    ROOT / "src" / "industrial_ops_agent" / "knowledge" / "retrieval.py",
    ROOT / "src" / "industrial_ops_agent" / "search_profiles" / "store.py",
)
FORBIDDEN = (
    "maintenance_planning",
    "industrial_recognition",
    "device_family",
    "device_model",
    "device_families",
    "device_models",
)


def main() -> None:
    violations: list[str] = []
    for path in REUSABLE_FILES:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        imports = [
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        for item in imports:
            if any(token in item for token in FORBIDDEN[:2]):
                violations.append(f"{path}: forbidden import {item}")
        for token in FORBIDDEN[2:]:
            if token in source:
                violations.append(f"{path}: forbidden runtime token {token}")
    assert not violations, "\n".join(violations)
    print("DEINDUSTRIALIZATION_BATCH2B_DEPENDENCY_SCAN_PASS")


if __name__ == "__main__":
    main()
