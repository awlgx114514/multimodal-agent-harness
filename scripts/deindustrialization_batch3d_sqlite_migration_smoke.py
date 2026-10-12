"""SQLite rehearsal for the Batch 3D predictive-table deletion migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, ForeignKey, MetaData, String, Table, create_engine, inspect

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / "0091_remove_predictive_maintenance.py"
PREDICTIVE_TABLES = {
    "telemetry_events",
    "telemetry_stream_states",
    "telemetry_windows",
    "alert_candidates",
    "alert_candidate_decisions",
    "predictive_maintenance_referrals",
    "predictive_outcomes",
    "rul_forecast_candidates",
    "rul_forecast_calibrations",
}


def _load_migration() -> Any:
    spec = importlib.util.spec_from_file_location("migration_0091", MIGRATION)
    if spec is None or spec.loader is None:
        raise RuntimeError("migration module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parent(metadata: MetaData, name: str, key: str) -> None:
    Table(name, metadata, Column(key, String(128), primary_key=True))


def main() -> None:
    engine = create_engine("sqlite+pysqlite://")
    metadata = MetaData()
    for name, key in (
        ("tenants", "id"),
        ("assets", "asset_id"),
        ("incidents", "incident_id"),
        ("work_orders", "work_order_id"),
        ("incident_drafts", "draft_id"),
        ("model_releases", "release_id"),
        ("dataset_snapshots", "snapshot_id"),
        ("training_experiments", "experiment_id"),
    ):
        _parent(metadata, name, key)
    Table(
        "telemetry_events",
        metadata,
        Column("event_id", String(128), primary_key=True),
        Column("asset_id", ForeignKey("assets.asset_id")),
    )
    Table(
        "telemetry_stream_states",
        metadata,
        Column("stream_id", String(128), primary_key=True),
        Column("asset_id", ForeignKey("assets.asset_id")),
    )
    Table(
        "telemetry_windows",
        metadata,
        Column("window_id", String(128), primary_key=True),
        Column("asset_id", ForeignKey("assets.asset_id")),
        Column("supersedes_window_id", ForeignKey("telemetry_windows.window_id")),
    )
    Table(
        "alert_candidates",
        metadata,
        Column("alert_candidate_id", String(128), primary_key=True),
        Column("window_id", ForeignKey("telemetry_windows.window_id")),
    )
    Table(
        "alert_candidate_decisions",
        metadata,
        Column("decision_id", String(128), primary_key=True),
        Column("alert_candidate_id", ForeignKey("alert_candidates.alert_candidate_id")),
    )
    Table(
        "predictive_maintenance_referrals",
        metadata,
        Column("referral_id", String(128), primary_key=True),
        Column("alert_candidate_id", ForeignKey("alert_candidates.alert_candidate_id")),
        Column("incident_draft_id", ForeignKey("incident_drafts.draft_id")),
    )
    Table(
        "predictive_outcomes",
        metadata,
        Column("outcome_id", String(128), primary_key=True),
        Column("alert_candidate_id", ForeignKey("alert_candidates.alert_candidate_id")),
        Column("work_order_id", ForeignKey("work_orders.work_order_id")),
    )
    Table(
        "rul_forecast_candidates",
        metadata,
        Column("rul_forecast_id", String(128), primary_key=True),
        Column("alert_candidate_id", ForeignKey("alert_candidates.alert_candidate_id")),
        Column("window_id", ForeignKey("telemetry_windows.window_id")),
    )
    Table(
        "rul_forecast_calibrations",
        metadata,
        Column("calibration_id", String(128), primary_key=True),
        Column("rul_forecast_id", ForeignKey("rul_forecast_candidates.rul_forecast_id")),
        Column("outcome_id", ForeignKey("predictive_outcomes.outcome_id")),
        Column("alert_candidate_id", ForeignKey("alert_candidates.alert_candidate_id")),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        module = _load_migration()
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        remaining = set(inspect(connection).get_table_names())
        assert not remaining.intersection(PREDICTIVE_TABLES)
        assert {
            "assets",
            "incidents",
            "work_orders",
            "dataset_snapshots",
            "training_experiments",
            "model_releases",
        } <= remaining
    print("DEINDUSTRIALIZATION_BATCH3D_SQLITE_MIGRATION_PASS")


if __name__ == "__main__":
    main()
