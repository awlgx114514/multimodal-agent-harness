"""RED/GREEN structural smoke for Batch 3A peripheral-domain deletion."""

from __future__ import annotations

from pathlib import Path

from industrial_ops_agent.tools.registry import default_tool_registry

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "src/industrial_ops_agent"
WEB = ROOT / "web"

DELETED_PATHS = (
    PRODUCTION / "collaboration",
    PRODUCTION / "supplier_sandbox",
    PRODUCTION / "simulation/supplier_a2a_lab.py",
    PRODUCTION / "simulation/supplier_a2a_lab_cli.py",
    PRODUCTION / "api/routes/collaborations.py",
    PRODUCTION / "api/routes/refunds.py",
    PRODUCTION / "api/routes/procurement.py",
    PRODUCTION / "api/routes/customer_notifications.py",
    PRODUCTION / "tools/refunds.py",
    PRODUCTION / "tools/procurement.py",
    PRODUCTION / "tools/quotations.py",
    PRODUCTION / "tools/customer_notifications.py",
    WEB / "app/collaboration/page.tsx",
    WEB / "components/m2/RefundRequestPanel.tsx",
    WEB / "components/m2/PurchaseRequestPanel.tsx",
    WEB / "components/m2/ServiceQuotationPanel.tsx",
    WEB / "components/m2/CustomerNotificationProposalPanel.tsx",
)

DELETED_TOOL_IDS = {
    "customer.notify",
    "purchase.request",
    "refund.request",
    "service.quote.publish",
}

DIAGNOSIS_TOOL_IDS = {
    "asset.get",
    "warranty.get",
    "parts.availability",
    "schedule.availability",
    "work_orders.history",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def main() -> None:
    present = [str(path.relative_to(ROOT)) for path in DELETED_PATHS if path.exists()]
    assert not present, f"deleted paths still present: {present}"

    definitions = default_tool_registry().definitions()
    tool_ids = {item.tool_id for item in definitions}
    assert not DELETED_TOOL_IDS & tool_ids
    assert tool_ids >= DIAGNOSIS_TOOL_IDS

    app_source = _read(PRODUCTION / "api/app.py")
    runtime_source = _read(PRODUCTION / "runtime.py")
    factory_source = _read(PRODUCTION / "tools/factory.py")
    model_source = _read(PRODUCTION / "persistence/models.py")
    gateway_source = _read(PRODUCTION / "tools/gateway.py")
    config_source = _read(PRODUCTION / "config.py")
    secrets_source = _read(PRODUCTION / "secrets.py")
    approvals_source = _read(PRODUCTION / "api/routes/approvals.py")
    portal_source = _read(PRODUCTION / "api/routes/portal.py")
    workorders_source = _read(PRODUCTION / "api/routes/workorders.py") + _read(
        PRODUCTION / "../industrial_ops_agent/workorders/service.py"
    )
    client_source = _read(WEB / "lib/api/client.ts")

    for source_name, source in {
        "api/app.py": app_source,
        "runtime.py": runtime_source,
        "tools/factory.py": factory_source,
        "persistence/models.py": model_source,
        "tools/gateway.py": gateway_source,
        "config.py": config_source,
        "secrets.py": secrets_source,
        "api/routes/approvals.py": approvals_source,
        "api/routes/portal.py": portal_source,
        "workorders": workorders_source,
        "web/lib/api/client.ts": client_source,
    }.items():
        for marker in (
            "supplier_a2a",
            "SupplierCollaboration",
            "customer_notification",
            "CustomerNotification",
            "purchase_request",
            "PurchaseRequest",
            "procurement",
            "refund_request",
            "RefundRequest",
            "service_quotation",
            "ServiceQuotation",
            "service-quotation",
            "ACCEPTED_QUOTATION",
        ):
            assert marker not in source, f"stale {marker} in {source_name}"

    migration = ROOT / "alembic/versions/0089_remove_peripheral_fulfillment.py"
    assert migration.exists()
    migration_source = _read(migration)
    for table in (
        "supplier_collaborations",
        "supplier_collaboration_events",
        "refund_requests",
        "refund_request_receipts",
        "purchase_requests",
        "purchase_request_receipts",
        "purchase_fulfillments",
        "purchase_fulfillment_receipts",
        "service_quotations",
        "service_quotation_decisions",
        "customer_notification_deliveries",
        "customer_notification_receipts",
    ):
        assert table in migration_source
    print("DEINDUSTRIALIZATION_BATCH3A_DELETION_PASS")


if __name__ == "__main__":
    main()
