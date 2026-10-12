"""Add independent approval lifecycle for evaluation suites and policies."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0096_evaluation_suite_policy_approval"
down_revision: str | None = "0095_application_owned_media_evidence"
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def _install_rls(table_name: str) -> None:
    predicate = "tenant_id = current_setting('app.tenant_id', true)"
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table_name}_tenant_isolation ON {table_name} "
        f"USING ({predicate}) WITH CHECK ({predicate})"
    )


def upgrade() -> None:
    for table_name in ("evaluation_suites", "evaluation_policies"):
        op.add_column(
            table_name, sa.Column("submitted_by_subject_id", sa.String(128), nullable=True)
        )
        op.add_column(table_name, sa.Column("submitted_at", sa.DateTime(timezone=True)))
        op.add_column(table_name, sa.Column("governance_digest", sa.String(64)))
        op.add_column(
            table_name, sa.Column("reviewed_by_subject_id", sa.String(128), nullable=True)
        )
        op.add_column(table_name, sa.Column("reviewed_at", sa.DateTime(timezone=True)))
        op.add_column(table_name, sa.Column("review_reason", sa.Text()))

    op.execute("UPDATE evaluation_suites SET status = 'DRAFT' WHERE status = 'FROZEN'")
    op.execute("UPDATE evaluation_policies SET status = 'DRAFT' WHERE status = 'ACTIVE'")

    op.create_table(
        "evaluation_governance_approvals",
        sa.Column("approval_id", sa.String(128), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("resource_kind", sa.String(16), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=False),
        sa.Column("resource_digest", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("submitted_by_subject_id", sa.String(128), nullable=False),
        sa.Column("decided_by_subject_id", sa.String(128), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.UniqueConstraint(
            "tenant_id", "resource_kind", "resource_id", name="uq_evaluation_governance_decision"
        ),
        sa.CheckConstraint(
            "resource_kind IN ('SUITE', 'POLICY')", name="ck_eval_gov_resource_kind"
        ),
        sa.CheckConstraint("decision IN ('APPROVE', 'REJECT')", name="ck_eval_gov_decision"),
    )
    op.create_index(
        "ix_evaluation_governance_approvals_tenant_id",
        "evaluation_governance_approvals",
        ["tenant_id"],
    )
    _install_rls("evaluation_governance_approvals")


def downgrade() -> None:
    raise NotImplementedError("0096_evaluation_suite_policy_approval is forward-only")
