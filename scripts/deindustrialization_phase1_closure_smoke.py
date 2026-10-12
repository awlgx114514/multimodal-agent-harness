"""Mechanical final-acceptance checks for the Phase 1 Closure Batch."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "industrial_ops_agent"

STALE_REPAIR_PATHS = frozenset(
    {
        "/api/v1/incidents/{incident_id}/repair-work-order-options",
        "/api/v1/incidents/{incident_id}/repair-work-order-proposals",
    }
)
STALE_REPAIR_SCHEMAS = frozenset(
    {
        "RepairWorkOrderOptionResponse",
        "RepairWorkOrderOptionsEnvelope",
        "RepairWorkOrderOptionsResponse",
        "RepairWorkOrderProposalBody",
    }
)
STALE_AUTHORIZATION_VALUES = frozenset(
    {
        "work_order.execute",
        "agent_collaboration.read",
        "agent_collaboration.create",
        "agent_collaboration.dispatch",
        "agent_collaboration.review",
        "alert_candidate.decide",
        "alert_candidate.refer",
        "predictive_outcome.record",
    }
)
CORE_MODULES = (
    SRC / "model_gateway" / "governance.py",
    SRC / "orchestration" / "runner.py",
    SRC / "orchestration" / "workflows.py",
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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_no_stale_generated_contract() -> None:
    contract = json.loads(_read(ROOT / "contracts" / "openapi.json"))
    paths = set(contract["paths"])
    schemas = set(contract["components"]["schemas"])
    assert not (STALE_REPAIR_PATHS & paths), "stale Repair Work Order OpenAPI path remains"
    assert not (STALE_REPAIR_SCHEMAS & schemas), "stale Repair Work Order schema remains"

    generated = _read(ROOT / "web" / "generated" / "api" / "schema.d.ts")
    for value in (*STALE_REPAIR_PATHS, *STALE_REPAIR_SCHEMAS):
        assert value not in generated, f"stale generated TypeScript reference remains: {value}"


def _assert_no_stale_authorization() -> None:
    policy = _read(SRC / "auth" / "policy.py")
    rego = _read(ROOT / "infra" / "opa" / "policy.rego")
    active_authorization = f"{policy}\n{rego}"
    for value in STALE_AUTHORIZATION_VALUES:
        assert value not in active_authorization, f"stale authorization remains: {value}"

    workorders = _read(SRC / "workorders" / "service.py")
    assert "Action.EXECUTE_WORK_ORDER" not in workorders
    assert workorders.count("Action.READ_WORK_ORDER") >= 2


def _assert_generic_core_is_domain_free() -> None:
    for path in CORE_MODULES:
        forbidden = {
            name
            for name in _imports(path)
            if name.startswith("industrial_ops_agent.maintenance_planning")
        }
        assert not forbidden, (
            f"{path.relative_to(ROOT)} imports Maintenance Planning: {sorted(forbidden)}"
        )

    governance = _read(SRC / "model_gateway" / "governance.py")
    assert "MaintenancePlanning" not in governance
    assert "record_disclosure" not in governance

    maintenance_reader = SRC / "maintenance_planning" / "model_inference_reader.py"
    assert maintenance_reader.is_file(), "Maintenance Planning inference reader is missing"
    reader_source = _read(maintenance_reader)
    assert "record_disclosure" in reader_source
    assert "MaintenancePlanningCouncilRecord" in reader_source

    temporal = SRC / "maintenance_planning" / "temporal.py"
    assert temporal.is_file(), "Maintenance Planning Temporal owner is missing"
    temporal_source = _read(temporal)
    for retained_symbol in (
        "maintenance_planning_council_activity",
        "maintenance_planning_council_workflow",
        "LazyTemporalMaintenancePlanningDispatcher",
    ):
        assert retained_symbol in temporal_source, retained_symbol

    entrypoint = SRC / "orchestration" / "entrypoint.py"
    assert entrypoint.is_file(), "worker composition entrypoint is missing"
    entrypoint_imports = _imports(entrypoint)
    assert "industrial_ops_agent.orchestration.runner" in entrypoint_imports
    assert any(
        name.startswith("industrial_ops_agent.maintenance_planning") for name in entrypoint_imports
    ), "worker composition entrypoint does not own the domain registration"


def _assert_worker_deployment_uses_composition_root() -> None:
    for relative in (
        "compose.lite.yaml",
        "docker/ai-worker.Dockerfile",
        "infra/helm/industrial-ops-application/templates/deployments.yaml",
    ):
        source = _read(ROOT / relative)
        assert "industrial_ops_agent.orchestration.entrypoint" in source, relative
        assert "industrial_ops_agent.orchestration.runner" not in source, relative


def _assert_maintenance_registration_behavior() -> None:
    from industrial_ops_agent.config import Settings
    from industrial_ops_agent.maintenance_planning.temporal import (
        build_maintenance_planning_worker_registration,
    )
    from industrial_ops_agent.model_gateway.service import ModelGateway
    from industrial_ops_agent.orchestration.worker_extensions import TemporalWorkerRuntime
    from industrial_ops_agent.persistence.database import Database

    disabled = TemporalWorkerRuntime(
        cast(Settings, SimpleNamespace(multi_agent_planning_enabled=False)),
        cast(Database, object()),
        cast(ModelGateway, object()),
    )
    assert build_maintenance_planning_worker_registration(disabled) is None

    enabled = TemporalWorkerRuntime(
        cast(
            Settings,
            SimpleNamespace(
                multi_agent_planning_enabled=True,
                maintenance_planning_timeout_seconds=30.0,
            ),
        ),
        cast(Database, object()),
        cast(ModelGateway, object()),
    )
    registration = build_maintenance_planning_worker_registration(enabled)
    assert registration is not None
    assert [workflow.__name__ for workflow in registration.workflows] == [
        "MaintenancePlanningWorkflow"
    ]
    assert len(registration.activities) == 1


def main() -> None:
    _assert_no_stale_generated_contract()
    _assert_no_stale_authorization()
    _assert_generic_core_is_domain_free()
    _assert_worker_deployment_uses_composition_root()
    _assert_maintenance_registration_behavior()
    print("DEINDUSTRIALIZATION_PHASE1_CLOSURE_PASS")


if __name__ == "__main__":
    main()
