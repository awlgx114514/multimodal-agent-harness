"""Remove WebRTC field-session persistence while retaining generic transcripts."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0093_remove_field_realtime_shell"
down_revision: str | None = "0092_remove_graphrag_neo4j"
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("realtime_transcript_segments", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "realtime_transcript_segments_session_id_fkey",
            type_="foreignkey",
        )
        batch_op.add_column(
            sa.Column("diagnosis_run_id", sa.String(length=128), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_realtime_transcript_diagnosis_run",
            "diagnosis_runs",
            ["diagnosis_run_id"],
            ["diagnosis_run_id"],
        )
    op.drop_table("realtime_media_sessions")


def downgrade() -> None:
    raise NotImplementedError("0093_remove_field_realtime_shell is forward-only")
