"""Focused regression for Batch 1 reusable-boundary requirements."""

from __future__ import annotations

import ast
import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from jsonschema.exceptions import ValidationError
from sqlalchemy import create_engine

from industrial_ops_agent.agent.checkpoints import AgentCheckpointStore
from industrial_ops_agent.agent.events import AgentEventStore
from industrial_ops_agent.agent.graph import AgentGraph, AgentGraphDefinition
from industrial_ops_agent.auth.identity import IdentityContext, Role
from industrial_ops_agent.auth.policy import Authorizer
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    AgentCheckpointRecord,
    AgentEventRecord,
    AgentRunRecord,
    Base,
    ToolCallRecord,
)
from industrial_ops_agent.persistence.tenant import TenantContext
from industrial_ops_agent.tools.gateway import ToolGateway
from industrial_ops_agent.tools.registry import default_tool_registry
from industrial_ops_agent.tools.synthetic_readonly import SyntheticReadonlyAdapter

TENANT_ID = "tenant-boundary"
SUBJECT_ID = "subject-boundary"
AGENT_RUN_ID = "agent-run-boundary"


class _AuditSink:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(self, **_: Any) -> None:
        self.records.append(_)


@dataclass
class _Runtime:
    decisions: list[dict[str, Any]] = field(
        default_factory=lambda: [{"action": "FINAL", "report": {"status": "COMPLETED"}}]
    )

    async def load(self) -> dict[str, Any]:
        return {
            "next_node": "prepare",
            "deadline": (datetime.now(UTC) + timedelta(seconds=5)).isoformat(),
            "budget": {"max_steps": 2, "max_tool_calls": 1},
            "tool_calls": 0,
        }

    async def enter(self, state: dict[str, Any], node: str) -> dict[str, Any]:
        del node
        return dict(state)

    async def commit(
        self, before: dict[str, Any], state: dict[str, Any], node: str
    ) -> dict[str, Any]:
        del before, node
        return state

    async def prepare(self, state: dict[str, Any]) -> dict[str, Any]:
        return state

    async def retrieve(self, state: dict[str, Any]) -> dict[str, Any]:
        return state

    async def decide(self, state: dict[str, Any]) -> dict[str, Any]:
        state["decision"] = self.decisions.pop(0)
        return state

    async def tool(self, state: dict[str, Any]) -> dict[str, Any]:
        return state

    async def finish(self, state: dict[str, Any]) -> dict[str, Any]:
        state["report"] = state["decision"]["report"]
        return state


def _definition() -> AgentGraphDefinition:
    def apply_action(state: dict[str, Any], action: str) -> None:
        if action == "RETRIEVE":
            state["retrieval_query"] = state["decision"]["query"]

    return AgentGraphDefinition(
        graph_version="boundary-smoke-v1",
        action_routes={
            "RETRIEVE": "retrieve",
            "CALL_TOOL": "tool",
            "FINAL": "finish",
            "NEEDS_INFORMATION": "finish",
        },
        tool_action="CALL_TOOL",
        timeout_report=lambda reason: {"status": "NEEDS_INFORMATION", "stop_reason": reason},
        timeout_reason="boundary_timeout",
        tool_budget_reason="boundary_tool_budget",
        apply_action=apply_action,
    )


def _identity() -> IdentityContext:
    now = datetime.now(UTC)
    return IdentityContext(
        subject_id=SUBJECT_ID,
        oidc_subject=SUBJECT_ID,
        tenant_id=TENANT_ID,
        roles=frozenset({Role.AFTER_SALES_ENGINEER}),
        asset_ids=frozenset({"asset-boundary"}),
        site_ids=frozenset({"site-boundary"}),
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
    )


def _database() -> Database:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            AgentRunRecord.__table__,
            AgentEventRecord.__table__,
            AgentCheckpointRecord.__table__,
            ToolCallRecord.__table__,
        ],
    )
    return Database.from_engine(engine)


def _verify_graph_boundary() -> None:
    source = Path(__file__).parents[1] / "src" / "industrial_ops_agent" / "agent" / "graph.py"
    imports = ast.parse(source.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(imports)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "industrial_ops_agent.agent.contracts" not in imported_modules

    graph = AgentGraph(_Runtime(), _definition())
    state = asyncio.run(graph.run())
    assert graph.version == "boundary-smoke-v1"
    assert state["report"] == {"status": "COMPLETED"}


def _verify_independent_agent_persistence(database: Database) -> TenantContext:
    assert "diagnosis_run_id" not in AgentRunRecord.__table__.c
    context = TenantContext(tenant_id=TENANT_ID, subject_id=SUBJECT_ID)
    with database.transaction(context) as session:
        session.add(
            AgentRunRecord(
                agent_run_id=AGENT_RUN_ID,
                tenant_id=TENANT_ID,
                status="RUNNING",
                budget={"max_steps": 2, "max_tool_calls": 1},
                last_sequence=0,
                version=1,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
    event_store = AgentEventStore(database)
    checkpoint_store = AgentCheckpointStore(database)
    event = event_store.append(
        context,
        AGENT_RUN_ID,
        event_type="agent.boundary.smoke",
        payload={"phase": 1},
    )
    checkpoint_store.save(
        context,
        AGENT_RUN_ID,
        sequence=event.sequence,
        graph_version="boundary-smoke-v1",
        state={"checkpoint_sequence": event.sequence},
    )
    assert checkpoint_store.load_graph(
        context, AGENT_RUN_ID, graph_version="boundary-smoke-v1"
    ) == {"checkpoint_sequence": event.sequence}
    return context


def _verify_gateway_without_fulfillment_adapters(database: Database) -> None:
    audit = _AuditSink()
    gateway = ToolGateway(
        database,
        Authorizer(audit),
        default_tool_registry(),
        readonly=SyntheticReadonlyAdapter(),
    )
    result = gateway.invoke(
        _identity(),
        tool_id="parts.availability",
        version="1.0.0",
        parameters={"asset_id": "asset-boundary"},
        request_id="request-boundary",
    )
    assert result.status == "SUCCEEDED"
    assert result.data is not None
    assert result.data["available_quantity"] == 8
    try:
        gateway.invoke(
            _identity(),
            tool_id="parts.availability",
            version="1.0.0",
            parameters={},
            request_id="request-boundary-invalid",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("read-only tool schema validation did not reject invalid input")
    try:
        gateway.invoke(
            _identity(),
            tool_id="parts.reserve",
            version="1.0.0",
            parameters={
                "incident_id": "incident-boundary",
                "asset_id": "asset-boundary",
                "part_number": "FILTER-X100",
                "quantity": 1,
            },
            request_id="request-boundary-deleted-mutation",
        )
    except ValueError as exc:
        assert str(exc) == "tool_not_registered"
    else:
        raise AssertionError("Parts mutation tool is still exposed")
    assert {record["action"] for record in audit.records} >= {
        "asset.read",
        "tool.schema.validate",
    }


def main() -> int:
    _verify_graph_boundary()
    database = _database()
    try:
        _verify_independent_agent_persistence(database)
        _verify_gateway_without_fulfillment_adapters(database)
    finally:
        database.dispose()
    print("DEINDUSTRIALIZATION_BATCH1_BOUNDARY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
