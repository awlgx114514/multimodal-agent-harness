"""SQLite rehearsal for the forward Batch 3A deletion migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import (
    CheckConstraint,
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
MIGRATION = ROOT / "alembic" / "versions" / "0089_remove_peripheral_fulfillment.py"


def _load_migration() -> object:
    spec = importlib.util.spec_from_file_location("migration_0089", MIGRATION)
    if spec is None or spec.loader is None:
        raise RuntimeError("migration module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _table(
    metadata: MetaData,
    name: str,
    *,
    parent: str | None = None,
    foreign_key_name: str | None = None,
) -> Table:
    columns = [Column(f"{name}_id", String(128), primary_key=True)]
    constraints = []
    if parent is not None:
        constraints.append(
            ForeignKeyConstraint(
                [f"{name}_id"],
                [f"{parent}.{parent}_id"],
                name=foreign_key_name,
            )
        )
    table = Table(name, metadata, *columns, *constraints)
    for index_name in {
        "supplier_collaboration_events": ("ix_supplier_collaboration_event_time",),
        "supplier_collaborations": (
            "ix_supplier_collaboration_incident",
            "ix_supplier_collaboration_status",
        ),
        "customer_notification_receipts": (
            "ix_customer_notification_receipts_tenant_id",
            "ix_customer_notification_receipts_delivery",
        ),
        "customer_notification_deliveries": (
            "ix_customer_notification_deliveries_tenant_id",
            "ix_customer_notification_deliveries_incident",
        ),
        "purchase_fulfillment_receipts": (
            "ix_purchase_fulfillment_receipts_tenant_id",
            "ix_purchase_fulfillment_receipts_fulfillment",
        ),
        "purchase_fulfillments": (
            "ix_purchase_fulfillments_tenant_id",
            "ix_purchase_fulfillments_request",
        ),
        "purchase_request_receipts": (
            "ix_purchase_request_receipts_tenant_id",
            "ix_purchase_request_receipts_request",
        ),
        "purchase_requests": (
            "ix_purchase_requests_tenant_id",
            "ix_purchase_requests_incident",
            "ix_purchase_requests_status",
        ),
        "refund_request_receipts": (
            "ix_refund_request_receipts_tenant_id",
            "ix_refund_request_receipts_request",
        ),
        "refund_requests": (
            "ix_refund_requests_tenant_id",
            "ix_refund_requests_incident",
            "ix_refund_requests_status",
        ),
        "service_quotation_decisions": (
            "ix_service_quotation_decisions_tenant_id",
            "ix_service_quotation_decisions_incident",
        ),
        "service_quotations": (
            "ix_service_quotations_tenant_id",
            "ix_service_quotations_incident",
        ),
    }.get(name, ()):
        # The migration only needs the historical index names to exist.
        from sqlalchemy import Index

        Index(index_name, table.c[f"{name}_id"])
    return table


def main() -> None:
    engine = create_engine("sqlite+pysqlite://")
    metadata = MetaData()
    work_orders = Table(
        "work_orders",
        metadata,
        Column("work_order_id", String(128), primary_key=True),
        Column("creation_mode", String(64), nullable=False),
        Column("reservation_id", String(128)),
        Column("diagnosis_run_id", String(128)),
        Column("diagnosis_version", Integer),
        Column("authorization_type", String(64)),
        Column("service_quotation_id", String(128)),
        ForeignKeyConstraint(
            ["service_quotation_id"],
            ["service_quotations.service_quotations_id"],
            name="fk_work_orders_service_quotation",
        ),
        CheckConstraint(
            "(creation_mode = 'PARTS_RESERVATION' AND reservation_id IS NOT NULL) OR "
            "(creation_mode = 'SERVICE_AUTHORIZATION' AND service_quotation_id IS NOT NULL)",
            name="ck_work_order_creation_binding",
        ),
    )
    service_quotations = _table(metadata, "service_quotations")
    _table(metadata, "service_quotation_decisions", parent="service_quotations")
    supplier = _table(metadata, "supplier_collaborations")
    _table(metadata, "supplier_collaboration_events", parent="supplier_collaborations")
    notification = _table(metadata, "customer_notification_deliveries")
    _table(metadata, "customer_notification_receipts", parent="customer_notification_deliveries")
    purchase = _table(metadata, "purchase_requests")
    fulfillment = _table(metadata, "purchase_fulfillments", parent="purchase_requests")
    _table(metadata, "purchase_fulfillment_receipts", parent="purchase_fulfillments")
    _table(metadata, "purchase_request_receipts", parent="purchase_requests")
    refund = _table(metadata, "refund_requests")
    _table(metadata, "refund_request_receipts", parent="refund_requests")
    metadata.create_all(engine)
    del supplier, notification, purchase, fulfillment, refund, work_orders, service_quotations

    with engine.begin() as connection:
        module = _load_migration()
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        remaining = set(inspect(connection).get_table_names())
        deleted = {
            "supplier_collaborations",
            "supplier_collaboration_events",
            "customer_notification_deliveries",
            "customer_notification_receipts",
            "purchase_requests",
            "purchase_request_receipts",
            "purchase_fulfillments",
            "purchase_fulfillment_receipts",
            "refund_requests",
            "refund_request_receipts",
            "service_quotations",
            "service_quotation_decisions",
        }
        assert not remaining.intersection(deleted)
        columns = {item["name"] for item in inspect(connection).get_columns("work_orders")}
        assert "service_quotation_id" not in columns
        foreign_keys = inspect(connection).get_foreign_keys("work_orders")
        assert all(item["name"] != "fk_work_orders_service_quotation" for item in foreign_keys)
    print("DEINDUSTRIALIZATION_BATCH3A_SQLITE_MIGRATION_PASS")


if __name__ == "__main__":
    main()
