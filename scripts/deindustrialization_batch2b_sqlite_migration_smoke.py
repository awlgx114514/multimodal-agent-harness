"""SQLite rehearsal for the forward generic applicability migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import JSON, Column, MetaData, String, Table, create_engine, inspect, select

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / "0088_knowledge_generic_applicability.py"


def _load_migration() -> object:
    spec = importlib.util.spec_from_file_location("migration_0088", MIGRATION)
    if spec is None or spec.loader is None:
        raise RuntimeError("migration module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    engine = create_engine("sqlite+pysqlite://")
    metadata = MetaData()
    versions = Table(
        "knowledge_document_versions",
        metadata,
        Column("document_version_id", String(128), primary_key=True),
        Column("device_families", JSON, nullable=False),
        Column("device_models", JSON, nullable=False),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            versions.insert(),
            [
                {"document_version_id": "global", "device_families": [], "device_models": []},
                {"document_version_id": "family", "device_families": ["pump"], "device_models": []},
                {
                    "document_version_id": "model",
                    "device_families": ["pump"],
                    "device_models": ["X100"],
                },
            ],
        )
        module = _load_migration()
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        columns = {item["name"] for item in inspect(connection).get_columns(versions.name)}
        assert "applicability" in columns
        migrated = Table(versions.name, MetaData(), autoload_with=connection)
        rows = connection.execute(
            select(
                migrated.c.document_version_id,
                migrated.c.device_families,
                migrated.c.device_models,
                migrated.c.applicability,
            ).order_by(migrated.c.document_version_id)
        ).all()
        by_id = {row.document_version_id: row for row in rows}
        assert by_id["global"].applicability == {}
        assert by_id["family"].applicability == {"equipment.family": ["pump"]}
        assert by_id["model"].applicability == {
            "equipment.family": ["pump"],
            "equipment.model": ["X100"],
        }
        assert by_id["family"].device_families == ["pump"]
        assert by_id["model"].device_models == ["X100"]
    print("DEINDUSTRIALIZATION_BATCH2B_SQLITE_MIGRATION_PASS")


if __name__ == "__main__":
    main()
