"""Focused structural smoke for Deindustrialization Batch 1.5."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "industrial_ops_agent"
GENERIC_BOUNDARY = SRC / "governance" / "review_boundary.py"
MAINTENANCE_BOUNDARY = SRC / "maintenance_planning" / "review_boundary.py"
REUSABLE_CALLERS = (
    SRC / "media" / "service.py",
    SRC / "memory_governance" / "service.py",
    SRC / "api" / "errors.py",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _defined_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _assert_no_maintenance_import(path: Path) -> None:
    forbidden = {
        name
        for name in _imports(path)
        if name.startswith("industrial_ops_agent.maintenance_planning")
    }
    if forbidden:
        relative_path = path.relative_to(ROOT)
        raise AssertionError(f"{relative_path} imports Maintenance Planning: {sorted(forbidden)}")


def main() -> None:
    if not GENERIC_BOUNDARY.exists():
        raise AssertionError("generic ReviewBoundary module is missing")
    if not MAINTENANCE_BOUNDARY.exists():
        raise AssertionError("MaintenanceReviewBoundary implementation is missing")

    generic_names = _defined_names(GENERIC_BOUNDARY)
    required_generic = {
        "DisclosureRequest",
        "ReviewBoundary",
        "ReviewBoundaryConflict",
        "lock_subject",
    }
    missing_generic = required_generic - generic_names
    if missing_generic:
        raise AssertionError(f"generic ReviewBoundary symbols missing: {sorted(missing_generic)}")
    _assert_no_maintenance_import(GENERIC_BOUNDARY)

    forbidden_terms = {
        "MaintenancePlanning",
        "REVIEW_POLICY_VERSION",
        "assignment",
        "council",
        "evaluation",
        "blind_review",
    }
    text = GENERIC_BOUNDARY.read_text(encoding="utf-8").casefold()
    present = sorted(term for term in forbidden_terms if term.casefold() in text)
    if present:
        raise AssertionError(f"generic ReviewBoundary contains policy semantics: {present}")

    if "MaintenanceReviewBoundary" not in _defined_names(MAINTENANCE_BOUNDARY):
        raise AssertionError("MaintenanceReviewBoundary is not owned by Maintenance Planning")
    from industrial_ops_agent.governance.review_boundary import ReviewBoundaryConflict
    from industrial_ops_agent.maintenance_planning.review_boundary import (
        MaintenanceReviewBoundary,
    )

    try:
        MaintenanceReviewBoundary().deny("smoke")
    except ReviewBoundaryConflict as exc:
        if exc.reason != "maintenance_review_smoke":
            message = "Maintenance boundary did not preserve its policy conflict"
            raise AssertionError(message) from exc
    else:
        raise AssertionError("Maintenance boundary did not deny an invalid source")

    for caller in REUSABLE_CALLERS:
        _assert_no_maintenance_import(caller)
        if "industrial_ops_agent.governance.review_boundary" not in _imports(caller):
            raise AssertionError(f"{caller.relative_to(ROOT)} does not use ReviewBoundary")

    app_text = (SRC / "api" / "app.py").read_text(encoding="utf-8")
    dependencies_text = (SRC / "api" / "dependencies.py").read_text(encoding="utf-8")
    if "review_boundary" not in app_text or "get_review_boundary" not in dependencies_text:
        raise AssertionError("API composition root does not provide ReviewBoundary")

    print("DEINDUSTRIALIZATION_BATCH15_REVIEW_BOUNDARY_PASS")


if __name__ == "__main__":
    main()
