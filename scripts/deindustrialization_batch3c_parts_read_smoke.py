"""RED/GREEN smoke for the Parts read/mutation boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from industrial_ops_agent.auth.identity import IdentityContext, Role
from industrial_ops_agent.auth.policy import Authorizer
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import Base, ToolCallRecord
from industrial_ops_agent.tools.gateway import ToolGateway
from industrial_ops_agent.tools.registry import default_tool_registry
from industrial_ops_agent.tools.synthetic_readonly import SyntheticReadonlyAdapter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "industrial_ops_agent"
WEB = ROOT / "web"
EXPECTED_DIAGNOSIS_TOOLS = {
    "asset.get",
    "warranty.get",
    "parts.availability",
    "schedule.availability",
    "work_orders.history",
}
MUTATION_MARKERS = (
    "parts.reserve",
    "parts.issue",
    "parts.consume",
    "parts.return",
    "PartIssueResult",
    "PartMovementResult",
    "PartsAdapter",
    "SyntheticPartsAdapter",
)


class _AuditSink:
    def record(self, **_: object) -> None:
        return None


def _identity() -> IdentityContext:
    now = datetime.now(UTC)
    return IdentityContext(
        subject_id="subject-batch3c",
        oidc_subject="subject-batch3c",
        tenant_id="tenant-batch3c",
        roles=frozenset({Role.AFTER_SALES_ENGINEER}),
        asset_ids=frozenset({"asset-batch3c"}),
        site_ids=frozenset(),
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
    )


def _database() -> Database:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[ToolCallRecord.__table__])
    return Database.from_engine(engine)


def main() -> None:
    definitions = default_tool_registry().definitions()
    tool_ids = {item.tool_id for item in definitions}
    assert tool_ids == EXPECTED_DIAGNOSIS_TOOLS, sorted(tool_ids)

    gateway_source = (SRC / "tools" / "gateway.py").read_text(encoding="utf-8")
    factory_source = (SRC / "tools" / "factory.py").read_text(encoding="utf-8")
    synthetic_parts = SRC / "tools" / "synthetic_parts.py"
    for source_name, source in {
        "gateway.py": gateway_source,
        "factory.py": factory_source,
        "synthetic_parts.py": synthetic_parts.read_text(encoding="utf-8")
        if synthetic_parts.exists()
        else "",
    }.items():
        for marker in MUTATION_MARKERS:
            assert marker not in source, f"stale Parts mutation marker in {source_name}: {marker}"

    for path in (
        SRC / "api" / "routes" / "parts.py",
        WEB / "app" / "parts" / "page.tsx",
        WEB / "lib" / "api" / "client.ts",
    ):
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        for marker in MUTATION_MARKERS[:4]:
            assert marker not in source, f"stale Parts mutation marker in {path}: {marker}"

    database = _database()
    try:
        gateway = ToolGateway(
            database,
            Authorizer(_AuditSink()),
            default_tool_registry(),
            readonly=SyntheticReadonlyAdapter(),
        )
        result = gateway.invoke(
            _identity(),
            tool_id="parts.availability",
            version="1.0.0",
            parameters={"asset_id": "asset-batch3c"},
            request_id="request-batch3c-availability",
        )
        assert result.status == "SUCCEEDED"
        assert result.data is not None
        assert result.data["available_quantity"] == 8
        try:
            gateway.invoke(
                _identity(),
                tool_id="parts.reserve",
                version="1.0.0",
                parameters={},
                request_id="request-batch3c-mutation",
            )
        except ValueError as exc:
            assert str(exc) == "tool_not_registered"
        else:
            raise AssertionError("Parts mutation tool is still registered")
    finally:
        database.dispose()

    print("DEINDUSTRIALIZATION_BATCH3C_PARTS_READ_PASS")


if __name__ == "__main__":
    main()
