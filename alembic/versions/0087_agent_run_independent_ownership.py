"""Make Industrial Diagnosis own its AgentRun association.

Revision ID: 0087_agent_run_independent_ownership
Revises: 0086_maintenance_review_exposure
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0087_agent_run_independent_ownership"
down_revision: str | None = "0086_maintenance_review_exposure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("agent_runs", recreate="always") as batch:
            batch.drop_column("diagnosis_run_id")
        with op.batch_alter_table("diagnosis_runs", recreate="always") as batch:
            batch.create_foreign_key(
                "fk_diagnosis_runs_agent_run_id",
                "agent_runs",
                ["agent_run_id"],
                ["agent_run_id"],
            )
        return

    foreign_keys: list[dict[str, Any]] = sa.inspect(bind).get_foreign_keys("agent_runs")
    diagnosis_foreign_key = next(
        (
            item
            for item in foreign_keys
            if item["constrained_columns"] == ["diagnosis_run_id"]
            and item["referred_table"] == "diagnosis_runs"
        ),
        None,
    )
    if diagnosis_foreign_key is None or diagnosis_foreign_key["name"] is None:
        raise RuntimeError("agent_runs diagnosis ownership foreign key is missing")
    op.drop_constraint(
        diagnosis_foreign_key["name"],
        "agent_runs",
        type_="foreignkey",
    )
    op.drop_column("agent_runs", "diagnosis_run_id")
    op.create_foreign_key(
        "fk_diagnosis_runs_agent_run_id",
        "diagnosis_runs",
        "agent_runs",
        ["agent_run_id"],
        ["agent_run_id"],
    )


def downgrade() -> None:
    # Generic AgentRuns may exist after this revision. Reintroducing a mandatory
    # Diagnosis foreign key would either discard them or fabricate ownership.
    pass
