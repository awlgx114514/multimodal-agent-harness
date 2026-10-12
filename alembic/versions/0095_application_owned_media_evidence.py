"""Allow tenant media and evidence to belong to a reference application context."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0095_application_owned_media_evidence"
down_revision: str | None = "0094_public_evaluation_source_review"
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("media_objects", sa.Column("application_id", sa.String(128), nullable=True))
    op.add_column(
        "media_objects", sa.Column("application_context_id", sa.String(255), nullable=True)
    )
    op.alter_column("media_objects", "draft_id", existing_type=sa.String(128), nullable=True)
    op.create_check_constraint(
        "ck_media_object_owner_binding",
        "media_objects",
        "(draft_id IS NOT NULL AND application_id IS NULL AND application_context_id IS NULL) OR "
        "(draft_id IS NULL AND application_id IS NOT NULL AND application_context_id IS NOT NULL)",
    )

    op.add_column(
        "evidence_bundles", sa.Column("application_id", sa.String(128), nullable=True)
    )
    op.add_column(
        "evidence_bundles",
        sa.Column("application_context_id", sa.String(255), nullable=True),
    )
    op.alter_column("evidence_bundles", "draft_id", existing_type=sa.String(128), nullable=True)
    op.alter_column("evidence_bundles", "asset_id", existing_type=sa.String(128), nullable=True)
    op.drop_constraint("ck_evidence_bundle_context_kind", "evidence_bundles", type_="check")
    op.create_check_constraint(
        "ck_evidence_bundle_context_kind",
        "evidence_bundles",
        "context_kind IN ('INCIDENT_DRAFT', 'APPLICATION')",
    )
    op.create_check_constraint(
        "ck_evidence_bundle_owner_binding",
        "evidence_bundles",
        "(context_kind = 'INCIDENT_DRAFT' AND draft_id IS NOT NULL AND asset_id IS NOT NULL "
        "AND application_id IS NULL AND application_context_id IS NULL) OR "
        "(context_kind = 'APPLICATION' AND draft_id IS NULL AND asset_id IS NULL "
        "AND application_id IS NOT NULL AND application_context_id IS NOT NULL)",
    )
    op.create_index(
        "uq_evidence_application_context_media",
        "evidence_bundles",
        ["tenant_id", "application_id", "application_context_id", "media_id"],
        unique=True,
        postgresql_where=sa.text("context_kind = 'APPLICATION'"),
    )


def downgrade() -> None:
    raise NotImplementedError("0095_application_owned_media_evidence is forward-only")
