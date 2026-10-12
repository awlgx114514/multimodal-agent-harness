"""Minimal synthetic regression for the Industrial Diagnosis reference path.

It deliberately uses the production graph, persistence stores, registry, gateway,
authorization boundary, and synthetic read-only adapter.  It does not require a
running model service or external industrial systems.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import create_engine

from industrial_ops_agent.agent.checkpoints import AgentCheckpointStore
from industrial_ops_agent.agent.contracts import DIAGNOSIS_GRAPH_DEFINITION
from industrial_ops_agent.agent.events import AgentEventStore, AgentRunWriteStopped
from industrial_ops_agent.agent.graph import AgentGraph
from industrial_ops_agent.auth.identity import IdentityContext, Role
from industrial_ops_agent.auth.policy import Authorizer
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    AgentCheckpointRecord,
    AgentEventRecord,
    AgentRunRecord,
    Base,
    DiagnosisRunRecord,
    ToolCallRecord,
)
from industrial_ops_agent.persistence.tenant import TenantContext
from industrial_ops_agent.tools.gateway import ToolGateway
from industrial_ops_agent.tools.registry import default_tool_registry
from industrial_ops_agent.tools.synthetic_readonly import SyntheticReadonlyAdapter

TENANT_ID = "tenant-batch1"
SUBJECT_ID = "subject-batch1"
AGENT_RUN_ID = "agent-run-batch1"
DIAGNOSIS_RUN_ID = "diagnosis-run-batch1"


class _AuditSink:
    def record(self, **_: Any) -> None:
        return None


@dataclass
class _Runtime:
    decisions: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {"action": "CALL_TOOL"},
            {
                "action": "FINAL",
                "report": {
                    "status": "COMPLETED",
                    "conclusion": "Synthetic diagnosis completed.",
                    "citations": [{"citation_id": "evidence-1"}],
                    "contradictions": [],
                    "missing_information": [],
                    "next_checks": ["Confirm the synthetic evidence."],
                    "confidence": 0.8,
                    "stop_reason": "final",
                },
            },
        ]
    )
    entered: list[str] = field(default_factory=list)

    async def load(self) -> dict[str, Any]:
        return {
            "next_node": "prepare",
            "deadline": (datetime.now(UTC) + timedelta(seconds=10)).isoformat(),
            "budget": {"max_steps": 5, "max_tool_calls": 2},
            "tool_calls": 0,
        }

    async def enter(self, state: dict[str, Any], node: str) -> dict[str, Any]:
        self.entered.append(node)
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
        state["tool_calls"] += 1
        state["tool_result"] = {"tool_id": "parts.availability", "available_quantity": 8}
        return state

    async def finish(self, state: dict[str, Any]) -> dict[str, Any]:
        state["report"] = state["decision"]["report"]
        return state


def _database() -> Database:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            DiagnosisRunRecord.__table__,
            AgentRunRecord.__table__,
            AgentEventRecord.__table__,
            AgentCheckpointRecord.__table__,
            ToolCallRecord.__table__,
        ],
    )
    return Database.from_engine(engine)


def _identity() -> IdentityContext:
    now = datetime.now(UTC)
    return IdentityContext(
        subject_id=SUBJECT_ID,
        oidc_subject=SUBJECT_ID,
        tenant_id=TENANT_ID,
        roles=frozenset({Role.AFTER_SALES_ENGINEER}),
        asset_ids=frozenset({"asset-batch1"}),
        site_ids=frozenset({"site-batch1"}),
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
    )


def _seed_diagnosis_and_agent_run(database: Database) -> TenantContext:
    context = TenantContext(tenant_id=TENANT_ID, subject_id=SUBJECT_ID)
    with database.transaction(context) as session:
        session.add(
            DiagnosisRunRecord(
                diagnosis_run_id=DIAGNOSIS_RUN_ID,
                tenant_id=TENANT_ID,
                incident_id="incident-batch1",
                evidence_bundle_id="evidence-bundle-batch1",
                agent_run_id=AGENT_RUN_ID,
                workflow_id="workflow-batch1",
                status="RUNNING",
                manifest={},
                report=None,
                stop_reason=None,
                version=1,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        session.flush()
        values: dict[str, Any] = {
            "agent_run_id": AGENT_RUN_ID,
            "tenant_id": TENANT_ID,
            "status": "RUNNING",
            "budget": {"max_steps": 5, "max_tool_calls": 2},
            "last_sequence": 0,
            "version": 1,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        if "diagnosis_run_id" in AgentRunRecord.__table__.c:
            values["diagnosis_run_id"] = DIAGNOSIS_RUN_ID
        session.add(AgentRunRecord(**values))
        session.flush()
        diagnosis = session.get(DiagnosisRunRecord, DIAGNOSIS_RUN_ID)
        assert diagnosis is not None
        assert diagnosis.agent_run_id == AGENT_RUN_ID
    return context


def _verify_persistence(database: Database, context: TenantContext) -> None:
    event_store = AgentEventStore(database)
    checkpoint_store = AgentCheckpointStore(database)
    event = event_store.append(
        context,
        AGENT_RUN_ID,
        event_type="diagnosis.tool.resolved",
        payload={"tool_id": "parts.availability"},
    )
    state = checkpoint_store.advance(
        context,
        AGENT_RUN_ID,
        expected_sequence=0,
        graph_version="diagnosis-graph-v2",
        state={"diagnosis_run_id": DIAGNOSIS_RUN_ID, "citation_ids": ["evidence-1"]},
        event_type="diagnosis.checkpoint",
        payload={"node": "tool"},
    )
    assert event.sequence == 1
    assert state["checkpoint_sequence"] == 2
    assert checkpoint_store.load_graph(
        context, AGENT_RUN_ID, graph_version="diagnosis-graph-v2"
    ) == state
    events, status = event_store.list_after(context, AGENT_RUN_ID, 0)
    assert status == "RUNNING"
    assert [item.sequence for item in events] == [1, 2]
    with database.transaction(context) as session:
        run = session.get(AgentRunRecord, AGENT_RUN_ID)
        assert run is not None
        run.status = "CANCEL_REQUESTED"
    try:
        event_store.append(
            context,
            AGENT_RUN_ID,
            event_type="diagnosis.after_cancel",
            payload={},
        )
    except AgentRunWriteStopped:
        pass
    else:
        raise AssertionError("cancelled AgentRun accepted a new event")


def _verify_readonly_tool(database: Database) -> None:
    identity = _identity()
    gateway = ToolGateway(
        database,
        Authorizer(_AuditSink()),
        default_tool_registry(),
        readonly=SyntheticReadonlyAdapter(),
    )
    result = gateway.invoke(
        identity,
        tool_id="parts.availability",
        version="1.0.0",
        parameters={"asset_id": "asset-batch1"},
        request_id="request-batch1",
        agent_run_id=None,
    )
    assert result.status == "SUCCEEDED"
    assert result.data is not None
    assert result.data["available_quantity"] == 8


def _verify_graph() -> None:
    runtime = _Runtime()
    state = asyncio.run(AgentGraph(runtime, DIAGNOSIS_GRAPH_DEFINITION).run())
    assert runtime.entered == ["prepare", "retrieve", "decide", "tool", "decide", "finish"]
    assert state["report"]["status"] == "COMPLETED"
    assert state["report"]["citations"] == [{"citation_id": "evidence-1"}]


def main() -> int:
    database = _database()
    try:
        context = _seed_diagnosis_and_agent_run(database)
        _verify_persistence(database, context)
        _verify_readonly_tool(database)
        _verify_graph()
    finally:
        database.dispose()
    print("DEINDUSTRIALIZATION_BATCH1_GOLDEN_PATH_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
