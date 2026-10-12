"""Remove peripheral fulfillment domains from the active schema.

Historical revisions remain immutable.  This forward-only revision removes
the deleted supplier, notification, procurement, refund, and quotation
ledgers after their dependent receipt/decision tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0089_remove_peripheral_fulfillment"
down_revision: str | None = "0088_knowledge_generic_applicability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_indexes(table: str, names: tuple[str, ...]) -> None:
    for name in names:
        op.drop_index(name, table_name=table)


def upgrade() -> None:
    # WorkOrder is a surviving domain, so detach its quotation FK/column and
    # tighten its creation binding before deleting the quotation tables.
    bind = op.get_bind()
    work_order_check = (
        "(creation_mode = 'PARTS_RESERVATION' AND reservation_id IS NOT NULL "
        "AND authorization_type IS NULL) OR "
        "(creation_mode = 'SERVICE_AUTHORIZATION' AND reservation_id IS NULL "
        "AND diagnosis_run_id IS NOT NULL AND diagnosis_version IS NOT NULL "
        "AND authorization_type = 'COVERED_SERVICE')"
    )
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("work_orders") as batch:
            batch.drop_constraint("fk_work_orders_service_quotation", type_="foreignkey")
            batch.drop_constraint("ck_work_order_creation_binding", type_="check")
            batch.drop_column("service_quotation_id")
            batch.create_check_constraint(
                "ck_work_order_creation_binding",
                work_order_check,
            )
    else:
        op.drop_constraint(
            "fk_work_orders_service_quotation",
            "work_orders",
            type_="foreignkey",
        )
        op.drop_constraint("ck_work_order_creation_binding", "work_orders", type_="check")
        op.drop_column("work_orders", "service_quotation_id")
        op.create_check_constraint(
            "ck_work_order_creation_binding",
            "work_orders",
            work_order_check,
        )

    # Supplier collaboration: events reference collaborations.
    _drop_indexes(
        "supplier_collaboration_events",
        ("ix_supplier_collaboration_event_time",),
    )
    op.drop_table("supplier_collaboration_events")
    _drop_indexes(
        "supplier_collaborations",
        ("ix_supplier_collaboration_incident", "ix_supplier_collaboration_status"),
    )
    op.drop_table("supplier_collaborations")

    # Customer notification: receipts reference deliveries.
    _drop_indexes(
        "customer_notification_receipts",
        ("ix_customer_notification_receipts_tenant_id", "ix_customer_notification_receipts_delivery"),
    )
    op.drop_table("customer_notification_receipts")
    _drop_indexes(
        "customer_notification_deliveries",
        ("ix_customer_notification_deliveries_tenant_id", "ix_customer_notification_deliveries_incident"),
    )
    op.drop_table("customer_notification_deliveries")

    # Procurement: both receipt ledgers and fulfillment reference requests.
    _drop_indexes(
        "purchase_fulfillment_receipts",
        ("ix_purchase_fulfillment_receipts_tenant_id", "ix_purchase_fulfillment_receipts_fulfillment"),
    )
    op.drop_table("purchase_fulfillment_receipts")
    _drop_indexes(
        "purchase_fulfillments",
        ("ix_purchase_fulfillments_tenant_id", "ix_purchase_fulfillments_request"),
    )
    op.drop_table("purchase_fulfillments")
    _drop_indexes(
        "purchase_request_receipts",
        ("ix_purchase_request_receipts_tenant_id", "ix_purchase_request_receipts_request"),
    )
    op.drop_table("purchase_request_receipts")
    _drop_indexes(
        "purchase_requests",
        ("ix_purchase_requests_tenant_id", "ix_purchase_requests_incident", "ix_purchase_requests_status"),
    )
    op.drop_table("purchase_requests")

    # Refund: receipt rows reference refund requests.
    _drop_indexes(
        "refund_request_receipts",
        ("ix_refund_request_receipts_tenant_id", "ix_refund_request_receipts_request"),
    )
    op.drop_table("refund_request_receipts")
    _drop_indexes(
        "refund_requests",
        ("ix_refund_requests_tenant_id", "ix_refund_requests_incident", "ix_refund_requests_status"),
    )
    op.drop_table("refund_requests")

    # Quotation: decisions reference quotations.
    _drop_indexes(
        "service_quotation_decisions",
        ("ix_service_quotation_decisions_tenant_id", "ix_service_quotation_decisions_incident"),
    )
    op.drop_table("service_quotation_decisions")
    _drop_indexes(
        "service_quotations",
        ("ix_service_quotations_tenant_id", "ix_service_quotations_incident"),
    )
    op.drop_table("service_quotations")


def downgrade() -> None:
    raise RuntimeError("0089_remove_peripheral_fulfillment is intentionally irreversible")
