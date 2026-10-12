from __future__ import annotations

import os
from pathlib import Path
from unittest import TestCase
from uuid import uuid4

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from industrial_ops_agent.persistence.models import TenantRecord

ROOT = Path(__file__).resolve().parents[2]


class PostgreSQLMigrationTests(TestCase):
    def test_upgrade_preserves_retained_data_and_respects_real_foreign_keys(self) -> None:
        source = make_url(os.environ["IOAP_DEMO_DATABASE_URL"])
        if source.get_backend_name() != "postgresql" or source.database != "ioap_demo":
            raise ValueError("IOAP_DEMO_DATABASE_URL must identify disposable ioap_demo")

        database_name = f"ioap_demo_migration_{uuid4().hex}"
        with psycopg.connect(
            host=source.host,
            port=source.port,
            user=source.username,
            password=source.password,
            dbname=source.database,
            autocommit=True,
        ) as connection:
            connection.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
            )

        url = source.set(drivername="postgresql+psycopg", database=database_name)
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
        engine: Engine | None = None
        try:
            engine = create_engine(url)
            command.upgrade(config, "0089_remove_peripheral_fulfillment")
            foreign_keys = inspect(engine).get_foreign_keys("work_order_assignments")
            self.assertTrue(
                any(
                    item["name"] == "fk_work_order_assignment_fsm_delivery"
                    and item["referred_table"] == "fsm_assignment_deliveries"
                    for item in foreign_keys
                )
            )
            with Session(engine) as session:
                session.add(TenantRecord(id="tenant-demo-migration", status="active"))
                session.commit()

            command.upgrade(config, "head")

            tables = set(inspect(engine).get_table_names())
            self.assertTrue(
                {"agent_runs", "agent_events", "agent_checkpoints", "evidence_bundles"}
                <= tables
            )
            self.assertTrue(
                {
                    "public_evaluation_sources",
                    "public_evaluation_source_approvals",
                    "evaluation_governance_approvals",
                }
                <= tables
            )
            media_columns = {
                column["name"]: column for column in inspect(engine).get_columns("media_objects")
            }
            evidence_columns = {
                column["name"]: column
                for column in inspect(engine).get_columns("evidence_bundles")
            }
            self.assertTrue(
                {"application_id", "application_context_id"} <= set(media_columns)
            )
            self.assertTrue(media_columns["draft_id"]["nullable"])
            self.assertTrue(
                {"application_id", "application_context_id"} <= set(evidence_columns)
            )
            self.assertTrue(evidence_columns["draft_id"]["nullable"])
            self.assertTrue(evidence_columns["asset_id"]["nullable"])
            self.assertTrue(
                {"work_order_assignments", "fsm_assignment_deliveries"}.isdisjoint(tables)
            )
            with engine.connect() as connection:
                self.assertEqual(
                    connection.scalar(text("SELECT version_num FROM alembic_version")),
                    "0096_evaluation_suite_policy_approval",
                )
                self.assertEqual(
                    connection.scalar(
                        select(TenantRecord.status).where(
                            TenantRecord.id == "tenant-demo-migration"
                        )
                    ),
                    "active",
                )
            command.upgrade(config, "head")
        finally:
            if engine is not None:
                engine.dispose()
            with psycopg.connect(
                host=source.host,
                port=source.port,
                user=source.username,
                password=source.password,
                dbname=source.database,
                autocommit=True,
            ) as connection:
                connection.execute(
                    sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name))
                )
