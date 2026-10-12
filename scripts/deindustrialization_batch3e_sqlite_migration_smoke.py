"""SQLite rehearsal for the Batch 3E GraphRAG and field-shell migrations."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import (
    Column,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    inspect,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    ROOT / "alembic" / "versions" / "0092_remove_graphrag_neo4j.py",
    ROOT / "alembic" / "versions" / "0093_remove_field_realtime_shell.py",
)


def _load_migration(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"migration module could not be loaded: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    engine = create_engine("sqlite+pysqlite://")
    metadata = MetaData()
    Table("diagnosis_runs", metadata, Column("diagnosis_run_id", String(128), primary_key=True))
    Table(
        "knowledge_index_activations",
        metadata,
        Column("activation_id", String(128), primary_key=True),
        Column("revoked_graph_release_ids", String(128), nullable=True),
    )
    for table_name in (
        "knowledge_graph_extraction_jobs",
        "knowledge_graph_evaluations",
        "knowledge_graph_edges",
        "knowledge_graph_nodes",
        "knowledge_graph_releases",
    ):
        Table(table_name, metadata, Column("id", String(128), primary_key=True))
    Table(
        "realtime_media_sessions",
        metadata,
        Column("session_id", String(128), primary_key=True),
    )
    Table(
        "realtime_transcript_segments",
        metadata,
        Column("segment_id", String(128), primary_key=True),
        Column("tenant_id", String(128), nullable=False),
        Column("session_id", String(128), nullable=False),
        Column("sequence", Integer, nullable=False),
        Column("text", String(4000), nullable=False),
        ForeignKeyConstraint(
            ["session_id"],
            ["realtime_media_sessions.session_id"],
            name="realtime_transcript_segments_session_id_fkey",
        ),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        for index, path in enumerate(MIGRATIONS, start=92):
            module = _load_migration(path, f"migration_{index}")
            module.op = Operations(MigrationContext.configure(connection))
            module.upgrade()

        tables = set(inspect(connection).get_table_names())
        assert not tables.intersection(
            {
                "knowledge_graph_extraction_jobs",
                "knowledge_graph_evaluations",
                "knowledge_graph_edges",
                "knowledge_graph_nodes",
                "knowledge_graph_releases",
                "realtime_media_sessions",
            }
        )
        assert {
            "diagnosis_runs",
            "knowledge_index_activations",
            "realtime_transcript_segments",
        } <= tables
        columns = {
            column["name"]
            for column in inspect(connection).get_columns("realtime_transcript_segments")
        }
        assert "diagnosis_run_id" in columns
        assert "revoked_graph_release_ids" not in {
            column["name"]
            for column in inspect(connection).get_columns("knowledge_index_activations")
        }
        foreign_keys = inspect(connection).get_foreign_keys("realtime_transcript_segments")
        assert any(
            key["referred_table"] == "diagnosis_runs"
            and key["constrained_columns"] == ["diagnosis_run_id"]
            for key in foreign_keys
        )
        assert not any(key["referred_table"] == "realtime_media_sessions" for key in foreign_keys)

    print("DEINDUSTRIALIZATION_BATCH3E_SQLITE_MIGRATION_PASS")


if __name__ == "__main__":
    main()
