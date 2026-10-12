"""Remove the predictive maintenance product tables."""

from __future__ import annotations

from alembic import op

revision: str = "0091_remove_predictive_maintenance"
down_revision: str | None = "0090_remove_workorder_field_fulfillment"
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Drop predictive tables in child-first order."""

    for table_name in (
        "rul_forecast_calibrations",
        "rul_forecast_candidates",
        "predictive_outcomes",
        "predictive_maintenance_referrals",
        "alert_candidate_decisions",
        "alert_candidates",
        "telemetry_windows",
        "telemetry_stream_states",
        "telemetry_events",
    ):
        op.drop_table(table_name)


def downgrade() -> None:
    raise NotImplementedError("0091_remove_predictive_maintenance is forward-only")
