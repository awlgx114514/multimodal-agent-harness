"""RED/GREEN structural smoke for Batch 3B fulfillment deletion."""

from __future__ import annotations

from pathlib import Path

from industrial_ops_agent.persistence.models import Base
from industrial_ops_agent.tools.registry import default_tool_registry

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "src/industrial_ops_agent"
WEB = ROOT / "web"

DELETED_PATHS = (
    PRODUCTION / "api/routes/workorders.py",
    PRODUCTION / "api/routes/fsm_assignments.py",
    PRODUCTION / "api/routes/equipment_control_handoffs.py",
    PRODUCTION / "api/routes/expert_collaborations.py",
    PRODUCTION / "tools/fsm_assignments.py",
    PRODUCTION / "workorders/assignment.py",
    PRODUCTION / "workorders/evidence.py",
    PRODUCTION / "workorders/offline_pack.py",
    PRODUCTION / "workorders/edge_diagnosis.py",
    PRODUCTION / "workorders/expert_collaboration.py",
    PRODUCTION / "workorders/voice_guidance.py",
    WEB / "app/dispatch/page.tsx",
    WEB / "app/field",
    WEB / "app/expert/collaborations/page.tsx",
    WEB / "app/work-orders",
    WEB / "lib/field-offline-queue.ts",
    WEB / "lib/field-offline-pack.ts",
    WEB / "lib/field-evidence-drafts.ts",
    WEB / "lib/field-service-worker-response.ts",
    WEB / "components/m2/RepairWorkOrderAuthorizationPanel.tsx",
    WEB / "components/m2/EquipmentControlHandoffPanel.tsx",
    WEB / "components/m3/RemoteExpertCollaborationPanel.tsx",
    WEB / "components/m3/RemoteExpertAudioPanel.tsx",
    WEB / "components/m3/FieldVoiceGuidancePanel.tsx",
    WEB / "components/m3/FieldPwaProvider.tsx",
    WEB / "public/field-offline.html",
)

DELETED_TOOL_IDS = {
    "work_order.create",
    "work_order.assign",
    "work_order.close",
    "equipment.control.*",
}

DIAGNOSIS_TOOL_IDS = {
    "asset.get",
    "warranty.get",
    "parts.availability",
    "schedule.availability",
    "work_orders.history",
}

DELETED_SCHEMA_TABLES = {
    "equipment_control_handoffs",
    "fsm_assignment_deliveries",
    "fsm_assignment_receipts",
    "work_order_field_evidence_uploads",
    "work_order_assignments",
    "work_order_offline_packs",
    "work_order_edge_diagnosis_packs",
    "work_order_edge_diagnosis_candidates",
    "work_order_expert_collaborations",
    "work_order_expert_collaboration_events",
    "work_order_expert_collaboration_recommendations",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def main() -> None:
    present = [
        str(path.relative_to(ROOT))
        for path in DELETED_PATHS
        if path.is_file() or (path.is_dir() and any(child.is_file() for child in path.rglob("*")))
    ]
    assert not present, f"deleted paths still present: {present}"

    assert not DELETED_SCHEMA_TABLES.intersection(Base.metadata.tables), (
        "deleted persistence tables still mapped",
        DELETED_SCHEMA_TABLES.intersection(Base.metadata.tables),
    )
    assert "pending_assignment_operation_id" not in Base.metadata.tables["work_orders"].c
    assert "work_order_id" not in Base.metadata.tables["recognition_runs"].c
    assert "field_evidence_upload_id" not in Base.metadata.tables["recognition_runs"].c
    assert "work_order_id" not in Base.metadata.tables["evidence_bundles"].c
    assert "field_evidence_upload_id" not in Base.metadata.tables["evidence_bundles"].c

    definitions = default_tool_registry().definitions()
    tool_ids = {item.tool_id for item in definitions}
    assert not DELETED_TOOL_IDS & tool_ids
    assert tool_ids >= DIAGNOSIS_TOOL_IDS
    assert {item.tool_id for item in definitions if item.risk_tier == "T0"} == DIAGNOSIS_TOOL_IDS

    app_source = _read(PRODUCTION / "api/app.py")
    approvals_source = _read(PRODUCTION / "api/routes/approvals.py")
    runtime_source = _read(PRODUCTION / "runtime.py")
    factory_source = _read(PRODUCTION / "tools/factory.py")
    gateway_source = _read(PRODUCTION / "tools/gateway.py")
    config_source = _read(PRODUCTION / "config.py")
    secrets_source = _read(PRODUCTION / "secrets.py")
    client_source = _read(WEB / "lib/api/client.ts")
    generated_source = _read(WEB / "generated/api/schema.d.ts")

    for source_name, source in {
        "api/app.py": app_source,
        "api/routes/approvals.py": approvals_source,
        "runtime.py": runtime_source,
        "tools/factory.py": factory_source,
        "tools/gateway.py": gateway_source,
        "config.py": config_source,
        "secrets.py": secrets_source,
        "web/lib/api/client.ts": client_source,
        "web/generated/api/schema.d.ts": generated_source,
    }.items():
        for marker in (
            "work_order.create",
            "work_order.assign",
            "work_order.close",
            "equipment.control",
            "fsm_assignment",
            "field-offline",
            "/dispatch/work-orders",
            "/field/work-orders",
            "/equipment-control-handoffs",
            "expert-collaboration",
        ):
            assert marker not in source, f"stale {marker} in {source_name}"

    for tool in DIAGNOSIS_TOOL_IDS:
        assert tool in gateway_source or tool in _read(PRODUCTION / "tools/mcp.py")

    print("DEINDUSTRIALIZATION_BATCH3B_DELETION_PASS")


if __name__ == "__main__":
    main()
