"""Remove deleted WorkOrder fulfillment and equipment-control persistence.

The WorkOrder history read facts and Parts reservation accounting remain.  This
revision only removes child records and bindings that no retained application
path can create or consume.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0090_remove_workorder_field_fulfillment"
down_revision: str | None = "0089_remove_peripheral_fulfillment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Remove obsolete FIELD_EVIDENCE bindings while retaining the generic
    # INCIDENT_DRAFT recognition/evidence records used by Diagnosis.
    with op.batch_alter_table("recognition_runs") as batch:
        batch.drop_index("ix_recognition_runs_field_context")
        batch.drop_constraint("ck_recognition_run_context_binding", type_="check")
        batch.drop_constraint("uq_recognition_field_evidence_binding", type_="unique")
        batch.drop_constraint("fk_recognition_runs_field_evidence_upload", type_="foreignkey")
        batch.drop_constraint("fk_recognition_runs_work_order", type_="foreignkey")
        batch.drop_column("work_order_version")
        batch.drop_column("field_evidence_upload_id")
        batch.drop_column("work_order_id")

    with op.batch_alter_table("evidence_bundles") as batch:
        batch.drop_index("ix_evidence_bundles_field_context")
        batch.drop_constraint("ck_evidence_bundle_context_binding", type_="check")
        batch.drop_constraint("fk_evidence_bundles_field_evidence_upload", type_="foreignkey")
        batch.drop_constraint("fk_evidence_bundles_work_order", type_="foreignkey")
        batch.drop_column("field_evidence_upload_id")
        batch.drop_column("work_order_id")

    # Realtime remains outside this Batch's architecture work, but its deleted
    # field/expert foreign keys must be detached before those tables disappear.
    with op.batch_alter_table("realtime_media_sessions") as batch:
        batch.drop_index("ix_realtime_media_sessions_expert_participant")
        batch.drop_index("ix_realtime_media_sessions_field_binding")
        batch.drop_constraint("ck_realtime_media_sessions_work_order_binding", type_="check")
        batch.drop_constraint("fk_realtime_media_sessions_expert_collaboration", type_="foreignkey")
        batch.drop_constraint("fk_realtime_media_sessions_work_order", type_="foreignkey")
        batch.drop_column("expert_collaboration_id")
        batch.drop_column("work_order_version")
        batch.drop_column("work_order_id")

    with op.batch_alter_table("work_orders") as batch:
        batch.drop_constraint("uq_work_order_pending_assignment_operation", type_="unique")
        batch.drop_column("pending_assignment_operation_id")

    # Delete child-first.  WorkOrder, WorkOrderEvent, WorkOrderControl,
    # completion/verification/rework, field entries, and Parts ledgers remain
    # available to retained read/accounting paths.
    for table in (
        "work_order_edge_diagnosis_candidates",
        "work_order_edge_diagnosis_packs",
        "work_order_offline_packs",
        "work_order_expert_collaboration_recommendations",
        "work_order_expert_collaboration_events",
        "fsm_assignment_receipts",
        "work_order_expert_collaborations",
        "work_order_assignments",
        "fsm_assignment_deliveries",
        "work_order_field_evidence_uploads",
        "equipment_control_handoffs",
    ):
        op.drop_table(table)


def downgrade() -> None:
    raise RuntimeError("0090_remove_workorder_field_fulfillment is intentionally irreversible")
