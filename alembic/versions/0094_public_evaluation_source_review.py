"""Add independent governance for public evaluation sources."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0094_public_evaluation_source_review"
down_revision: str | None = "0093_remove_field_realtime_shell"
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "public_evaluation_sources",
        sa.Column("source_id", sa.String(length=128), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("contract_version", sa.String(length=128), nullable=False),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.Column("manifest_key", sa.String(length=1024), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("submitted_by_subject_id", sa.String(length=128), nullable=False),
        sa.Column("reviewed_by_subject_id", sa.String(length=128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.UniqueConstraint(
            "tenant_id", "manifest_hash", name="uq_public_evaluation_source_manifest"
        ),
        sa.CheckConstraint(
            "status IN ('PENDING_REVIEW', 'APPROVED', 'REJECTED')",
            name="ck_public_evaluation_source_status",
        ),
    )
    op.create_index(
        "ix_public_evaluation_sources_tenant_id",
        "public_evaluation_sources",
        ["tenant_id"],
    )
    op.create_table(
        "public_evaluation_source_approvals",
        sa.Column("approval_id", sa.String(length=128), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decided_by_subject_id", sa.String(length=128), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["source_id"], ["public_evaluation_sources.source_id"]
        ),
        sa.UniqueConstraint(
            "tenant_id", "source_id", name="uq_public_evaluation_source_decision"
        ),
        sa.CheckConstraint(
            "decision IN ('APPROVE', 'REJECT')",
            name="ck_public_evaluation_source_decision",
        ),
    )
    op.create_index(
        "ix_public_evaluation_source_approvals_tenant_id",
        "public_evaluation_source_approvals",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_public_evaluation_source_approvals_tenant_id",
        table_name="public_evaluation_source_approvals",
    )
    op.drop_table("public_evaluation_source_approvals")
    op.drop_index(
        "ix_public_evaluation_sources_tenant_id",
        table_name="public_evaluation_sources",
    )
    op.drop_table("public_evaluation_sources")
