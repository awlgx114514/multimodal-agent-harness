"""RED/GREEN smoke for the production Diagnosis composition boundary."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from industrial_ops_agent.agent.diagnosis_runtime import DiagnosisRuntime
from industrial_ops_agent.auth.identity import IdentityContext, Role
from industrial_ops_agent.auth.policy import Authorizer
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import Base, ToolCallRecord
from industrial_ops_agent.tools.diagnosis_composition import (
    build_diagnosis_tool_gateway,
)
from industrial_ops_agent.tools.gateway import ToolGateway
from industrial_ops_agent.tools.synthetic_readonly import SyntheticReadonlyAdapter

TENANT_ID = "tenant-batch2c"
SUBJECT_ID = "subject-batch2c"


class _AuditSink:
    def record(self, **_: object) -> None:
        return None


def _identity() -> IdentityContext:
    now = datetime.now(UTC)
    return IdentityContext(
        subject_id=SUBJECT_ID,
        oidc_subject=SUBJECT_ID,
        tenant_id=TENANT_ID,
        roles=frozenset({Role.AFTER_SALES_ENGINEER}),
        asset_ids=frozenset({"asset-batch2c"}),
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
    database = _database()
    try:
        diagnosis_readonly = SyntheticReadonlyAdapter()
        gateway = build_diagnosis_tool_gateway(
            database,
            Authorizer(_AuditSink()),
            readonly=diagnosis_readonly,
        )
        assert gateway.__class__ is ToolGateway
        command = SimpleNamespace(
            diagnosis_run_id="diagnosis-batch2c",
            agent_run_id="agent-batch2c",
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            roles=(Role.AFTER_SALES_ENGINEER.value,),
            asset_ids=("asset-batch2c",),
            site_ids=(),
            oidc_subject=SUBJECT_ID,
            issued_at=datetime.now(UTC).isoformat(),
            expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            request_id="request-batch2c-runtime",
        )
        runtime = DiagnosisRuntime(
            database,
            cast(Any, command),
            {
                "manifest": {
                    "agent_graph_version": "diagnosis-graph-v2",
                    "prompt_bundle": "industrial-diagnosis-agent-v2",
                }
            },
            model_gateway=cast(Any, object()),
            tool_gateway=gateway,
            model_alias="industrial-diagnosis",
            timeout_seconds=5.0,
            memory_reader=cast(Any, object()),
        )
        assert runtime.tools is gateway
        assert {item.tool_id for item in gateway._registry.definitions()} == {
            "asset.get",
            "warranty.get",
            "parts.availability",
            "schedule.availability",
            "work_orders.history",
        }
        assert not hasattr(gateway, "_procurement")
        assert not hasattr(gateway, "_refunds")
        assert not hasattr(gateway, "_fsm_assignments")
        assert not hasattr(gateway, "_quotations")
        state = {
            "tool_calls": 0,
            "budget": {"max_tool_calls": 1},
            "tool_facts": [],
            "tool_failures": [],
            "manifest": {
                "tool_versions": {"parts.availability": "1.0.0"},
            },
            "decision": {"tool_id": "parts.availability"},
            "deadline": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            "asset_id": "asset-batch2c",
            "trace_id": "request-batch2c",
        }
        runtime_state = asyncio.run(runtime.tool(state))
        assert runtime_state["tool_calls"] == 1
        assert runtime_state["tool_facts"][0]["tool_id"] == "parts.availability"
        try:
            gateway.invoke(
                _identity(),
                tool_id="parts.availability",
                version="1.0.0",
                parameters={},
                request_id="request-batch2c-invalid",
            )
        except Exception as exc:
            assert exc.__class__.__name__ == "ValidationError"
        else:
            raise AssertionError("Diagnosis gateway accepted invalid read-only parameters")
        try:
            gateway.invoke(
                _identity(),
                tool_id="parts.reserve",
                version="1.0.0",
                parameters={},
                request_id="request-batch2c-mutation",
            )
        except ValueError as exc:
            assert str(exc) == "tool_not_registered"
        else:
            raise AssertionError("Diagnosis gateway exposed a mutation tool")
        print("DEINDUSTRIALIZATION_BATCH2C_RUNTIME_ISOLATION_PASS")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
