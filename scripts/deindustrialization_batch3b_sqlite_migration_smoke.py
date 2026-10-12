"""SQLite rehearsal for the Batch 3B forward deletion migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    inspect,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / "0090_remove_workorder_field_fulfillment.py"


def _load_migration() -> Any:
    spec = importlib.util.spec_from_file_location("migration_0090", MIGRATION)
    if spec is None or spec.loader is None:
        raise RuntimeError("migration module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parent(metadata: MetaData, name: str, key: str) -> Table:
    return Table(name, metadata, Column(key, String(128), primary_key=True))


def _drop_target_tables(metadata: MetaData) -> None:
    # Only the names and FK topology are relevant to this rehearsal.
    targets = {
        "equipment_control_handoffs": ("incidents", "incident_id"),
        "fsm_assignment_deliveries": ("work_orders", "work_order_id"),
        "fsm_assignment_receipts": ("fsm_assignment_deliveries", "delivery_id"),
        "work_order_field_evidence_uploads": ("work_orders", "work_order_id"),
        "work_order_assignments": ("work_orders", "work_order_id"),
        "work_order_offline_packs": ("work_order_assignments", "assignment_id"),
        "work_order_edge_diagnosis_packs": (
            "work_order_offline_packs",
            "pack_id",
        ),
        "work_order_edge_diagnosis_candidates": (
            "work_order_edge_diagnosis_packs",
            "pack_id",
        ),
        "work_order_expert_collaborations": ("work_orders", "work_order_id"),
        "work_order_expert_collaboration_events": (
            "work_order_expert_collaborations",
            "collaboration_id",
        ),
        "work_order_expert_collaboration_recommendations": (
            "work_order_expert_collaborations",
            "collaboration_id",
        ),
    }
    for name, (parent, parent_key) in targets.items():
        key = {
            "equipment_control_handoffs": "handoff_id",
            "fsm_assignment_deliveries": "delivery_id",
            "fsm_assignment_receipts": "receipt_id",
            "work_order_field_evidence_uploads": "evidence_upload_id",
            "work_order_assignments": "assignment_id",
            "work_order_offline_packs": "pack_id",
            "work_order_edge_diagnosis_packs": "pack_id",
            "work_order_edge_diagnosis_candidates": "candidate_id",
            "work_order_expert_collaborations": "collaboration_id",
            "work_order_expert_collaboration_events": "event_id",
            "work_order_expert_collaboration_recommendations": "recommendation_id",
        }[name]
        columns = [
            Column(key, String(128), primary_key=True),
            Column("tenant_id", String(64), nullable=False),
        ]
        if parent_key != key:
            columns.append(Column(parent_key, String(128)))
        table = Table(
            name,
            metadata,
            *columns,
            ForeignKeyConstraint([parent_key], [f"{parent}.{parent_key}"]),
        )
        Index(f"ix_{name}_tenant_id", table.c.tenant_id)


def main() -> None:
    engine = create_engine("sqlite+pysqlite://")
    metadata = MetaData()
    _parent(metadata, "tenants", "id")
    _parent(metadata, "incidents", "incident_id")
    _parent(metadata, "assets", "asset_id")
    _parent(metadata, "tool_calls", "tool_call_id")
    _parent(metadata, "action_proposals", "proposal_id")
    _parent(metadata, "approval_requests", "approval_id")
    _parent(metadata, "diagnosis_runs", "diagnosis_run_id")
    _parent(metadata, "media_objects", "media_id")

    _work_orders = Table(
        "work_orders",
        metadata,
        Column("work_order_id", String(128), primary_key=True),
        Column("tenant_id", String(64), nullable=False),
        Column("pending_assignment_operation_id", String(128)),
        CheckConstraint("1 = 1", name="ck_work_order_creation_binding"),
        UniqueConstraint(
            "tenant_id",
            "pending_assignment_operation_id",
            name="uq_work_order_pending_assignment_operation",
        ),
    )
    recognition_runs = Table(
        "recognition_runs",
        metadata,
        Column("recognition_run_id", String(128), primary_key=True),
        Column("tenant_id", String(64), nullable=False),
        Column("context_kind", String(32), nullable=False),
        Column("work_order_id", String(128)),
        Column("field_evidence_upload_id", String(128)),
        Column("work_order_version", Integer),
        Column("requested_by_subject_id", String(128)),
        ForeignKeyConstraint(
            ["work_order_id"],
            ["work_orders.work_order_id"],
            name="fk_recognition_runs_work_order",
        ),
        ForeignKeyConstraint(
            ["field_evidence_upload_id"],
            ["work_order_field_evidence_uploads.evidence_upload_id"],
            name="fk_recognition_runs_field_evidence_upload",
        ),
        CheckConstraint("1 = 1", name="ck_recognition_run_context_binding"),
        CheckConstraint(
            "context_kind IN ('INCIDENT_DRAFT', 'FIELD_EVIDENCE')",
            name="ck_recognition_run_context_kind",
        ),
        UniqueConstraint(
            "tenant_id",
            "context_kind",
            "field_evidence_upload_id",
            "requested_by_subject_id",
            "work_order_version",
            name="uq_recognition_field_evidence_binding",
        ),
    )
    Index(
        "ix_recognition_runs_field_context",
        recognition_runs.c.tenant_id,
        recognition_runs.c.work_order_id,
    )
    evidence_bundles = Table(
        "evidence_bundles",
        metadata,
        Column("bundle_id", String(128), primary_key=True),
        Column("tenant_id", String(64), nullable=False),
        Column("draft_id", String(128), nullable=False),
        Column("media_id", String(128), nullable=False),
        Column("context_kind", String(32), nullable=False),
        Column("work_order_id", String(128)),
        Column("field_evidence_upload_id", String(128)),
        ForeignKeyConstraint(
            ["work_order_id"],
            ["work_orders.work_order_id"],
            name="fk_evidence_bundles_work_order",
        ),
        ForeignKeyConstraint(
            ["field_evidence_upload_id"],
            ["work_order_field_evidence_uploads.evidence_upload_id"],
            name="fk_evidence_bundles_field_evidence_upload",
        ),
        CheckConstraint("1 = 1", name="ck_evidence_bundle_context_binding"),
        CheckConstraint(
            "context_kind IN ('INCIDENT_DRAFT', 'FIELD_EVIDENCE')",
            name="ck_evidence_bundle_context_kind",
        ),
    )
    Index("uq_evidence_incident_draft_media", evidence_bundles.c.tenant_id, unique=True)
    Index(
        "ix_evidence_bundles_field_context",
        evidence_bundles.c.tenant_id,
        evidence_bundles.c.work_order_id,
    )
    realtime_sessions = Table(
        "realtime_media_sessions",
        metadata,
        Column("session_id", String(128), primary_key=True),
        Column("tenant_id", String(64), nullable=False),
        Column("work_order_id", String(128)),
        Column("work_order_version", Integer),
        Column("expert_collaboration_id", String(128)),
        ForeignKeyConstraint(
            ["work_order_id"],
            ["work_orders.work_order_id"],
            name="fk_realtime_media_sessions_work_order",
        ),
        ForeignKeyConstraint(
            ["expert_collaboration_id"],
            ["work_order_expert_collaborations.collaboration_id"],
            name="fk_realtime_media_sessions_expert_collaboration",
        ),
        CheckConstraint("1 = 1", name="ck_realtime_media_sessions_work_order_binding"),
    )
    Index("ix_realtime_media_sessions_field_binding", realtime_sessions.c.tenant_id)
    Index("ix_realtime_media_sessions_expert_participant", realtime_sessions.c.tenant_id)
    _drop_target_tables(metadata)
    metadata.create_all(engine)

    with engine.begin() as connection:
        module = _load_migration()
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        inspector = inspect(connection)
        remaining = set(inspector.get_table_names())
        deleted = {
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
        assert not remaining.intersection(deleted)
        for table, removed in {
            "recognition_runs": {
                "work_order_id",
                "field_evidence_upload_id",
                "work_order_version",
            },
            "evidence_bundles": {"work_order_id", "field_evidence_upload_id"},
            "realtime_media_sessions": {
                "work_order_id",
                "work_order_version",
                "expert_collaboration_id",
            },
            "work_orders": {"pending_assignment_operation_id"},
        }.items():
            columns = {item["name"] for item in inspector.get_columns(table)}
            assert not columns.intersection(removed), (table, columns.intersection(removed))
        assert {"work_orders", "recognition_runs", "evidence_bundles"}.issubset(remaining)
    print("DEINDUSTRIALIZATION_BATCH3B_SQLITE_MIGRATION_PASS")


if __name__ == "__main__":
    main()
