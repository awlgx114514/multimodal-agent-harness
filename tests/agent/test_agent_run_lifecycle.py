from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest import TestCase

from sqlalchemy import select
from sqlalchemy.orm import Session

from industrial_ops_agent.agent.contracts import (
    DIAGNOSIS_AGENT_PROMPT_ID,
    DIAGNOSIS_GRAPH_VERSION,
)
from industrial_ops_agent.agent.diagnosis_runtime import DiagnosisRuntime
from industrial_ops_agent.agent.events import AgentEventStore, AgentRunWriteStopped
from industrial_ops_agent.application.diagnoses import DiagnosisWorkflowInput
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    AgentEventRecord,
    AgentRunRecord,
    Base,
    TenantRecord,
)


class AgentRunLifecycleTests(TestCase):
    def setUp(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.pool import StaticPool

        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.database = Database.from_engine(self.engine)
        self.now = datetime(2026, 10, 3, tzinfo=UTC)
        with Session(self.engine) as session:
            session.add(TenantRecord(id="tenant-lifecycle", status="active"))
            session.add(
                AgentRunRecord(
                    tenant_id="tenant-lifecycle",
                    agent_run_id="agent-lifecycle",
                    status="QUEUED",
                    budget={"max_steps": 4},
                    last_sequence=0,
                    version=1,
                    created_at=self.now,
                    updated_at=self.now,
                )
            )
            session.commit()

    def tearDown(self) -> None:
        self.database.dispose()

    def test_execution_start_transitions_queued_to_running_once_across_retry(self) -> None:
        runtime = self._runtime()

        asyncio.run(runtime.load())
        self.assertEqual(self._status(), "RUNNING")

        asyncio.run(runtime.load())
        self.assertEqual(self._status(), "RUNNING")
        with Session(self.engine) as session:
            starts = session.scalars(
                select(AgentEventRecord).where(
                    AgentEventRecord.tenant_id == "tenant-lifecycle",
                    AgentEventRecord.agent_run_id == "agent-lifecycle",
                    AgentEventRecord.event_type == "diagnosis.graph_started",
                )
            ).all()
        self.assertEqual(len(starts), 1)

    def test_execution_start_does_not_reopen_terminal_run(self) -> None:
        for status in (
            "COMPLETED",
            "FAILED",
            "CANCELLED",
            "NEEDS_INFORMATION",
            "WAITING_EXPERT",
            "ESCALATED",
            "CANCEL_REQUESTED",
        ):
            with self.subTest(status=status):
                self._set_status(status)
                with self.assertRaises(AgentRunWriteStopped):
                    asyncio.run(self._runtime().load())
                self.assertEqual(self._status(), status)

    def test_existing_terminal_outcomes_remain_persistable(self) -> None:
        store = AgentEventStore(self.database)
        for status in ("COMPLETED", "FAILED", "CANCELLED", "NEEDS_INFORMATION"):
            with self.subTest(status=status):
                self._set_status("RUNNING")
                store.append(
                    self._context(),
                    "agent-lifecycle",
                    event_type=f"diagnosis.{status.lower()}",
                    payload={},
                    agent_status=status,
                )
                self.assertEqual(self._status(), status)

    def _runtime(self) -> DiagnosisRuntime:
        command = DiagnosisWorkflowInput(
            tenant_id="tenant-lifecycle",
            subject_id="subject-lifecycle",
            roles=("field_engineer",),
            asset_ids=(),
            site_ids=(),
            incident_id="incident-lifecycle",
            diagnosis_run_id="diagnosis-lifecycle",
            agent_run_id="agent-lifecycle",
            workflow_id="workflow-lifecycle",
            request_id="request-lifecycle",
        )
        initial = {
            "query_text": "test diagnosis",
            "manifest": {
                "agent_graph_version": DIAGNOSIS_GRAPH_VERSION,
                "prompt_bundle": DIAGNOSIS_AGENT_PROMPT_ID,
                "budget": {
                    "max_steps": 4,
                    "max_tool_calls": 1,
                    "max_tokens": 1000,
                    "timeout_seconds": 60,
                },
            },
        }
        return DiagnosisRuntime(
            self.database,
            command,
            initial,
            model_gateway=None,  # type: ignore[arg-type]
            tool_gateway=None,
            model_alias="test-model",
            timeout_seconds=1,
            memory_reader=None,  # type: ignore[arg-type]
        )

    def _status(self) -> str:
        with Session(self.engine) as session:
            run = session.get(AgentRunRecord, "agent-lifecycle")
            self.assertIsNotNone(run)
            return run.status  # type: ignore[union-attr]

    def _set_status(self, status: str) -> None:
        with Session(self.engine) as session:
            run = session.get(AgentRunRecord, "agent-lifecycle")
            self.assertIsNotNone(run)
            run.status = status  # type: ignore[union-attr]
            session.commit()

    def _context(self):
        from industrial_ops_agent.persistence.tenant import TenantContext

        return TenantContext("tenant-lifecycle", "subject-lifecycle")
