from __future__ import annotations

from datetime import UTC, datetime
from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from industrial_ops_agent.agent.trajectory import TrajectoryProjector
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    AgentCheckpointRecord,
    AgentEventRecord,
    AgentRunRecord,
    Base,
    ModelInferenceRecord,
    TenantRecord,
    ToolCallRecord,
)
from industrial_ops_agent.persistence.tenant import TenantContext


class TrajectoryProjectorTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.database = Database.from_engine(self.engine)
        self.context = TenantContext("trajectory-tenant", "trajectory-subject")
        self.now = datetime(2026, 9, 28, tzinfo=UTC)

    def tearDown(self) -> None:
        self.database.dispose()

    def test_projects_model_retrieval_tool_and_terminal_from_existing_records(self) -> None:
        with Session(self.engine) as session:
            session.add(TenantRecord(id=self.context.tenant_id, status="active"))
            session.add(
                AgentRunRecord(
                    tenant_id=self.context.tenant_id,
                    agent_run_id="agent-trajectory",
                    status="COMPLETED",
                    budget={"max_steps": 8},
                    last_sequence=14,
                    version=14,
                    created_at=self.now,
                    updated_at=self.now,
                )
            )
            session.add_all(
                [
                    _event(1, "diagnosis.graph_started", {"graph_version": "diagnosis-graph-v2"}),
                    _event(2, "diagnosis.graph_node_started", {"node": "decide", "step": 0}),
                    _event(
                        3,
                        "diagnosis.graph_node_completed",
                        {
                            "node": "decide",
                            "step": 0,
                            "next_node": "retrieve",
                            "inference_request_id": "inference-retrieve",
                            "action": "RETRIEVE",
                        },
                    ),
                    _event(4, "diagnosis.graph_node_started", {"node": "retrieve", "step": 1}),
                    _event(
                        5,
                        "diagnosis.graph_node_completed",
                        {
                            "node": "retrieve",
                            "step": 1,
                            "next_node": "decide",
                            "evidence_count": 1,
                            "retrieval_guard": {"release_id": "index-v1"},
                        },
                    ),
                    _event(6, "diagnosis.graph_node_started", {"node": "decide", "step": 2}),
                    _event(
                        7,
                        "diagnosis.graph_node_completed",
                        {
                            "node": "decide",
                            "step": 2,
                            "next_node": "tool",
                            "inference_request_id": "inference-tool",
                            "action": "CALL_TOOL",
                        },
                    ),
                    _event(8, "diagnosis.graph_node_started", {"node": "tool", "step": 3}),
                    _event(
                        9,
                        "diagnosis.graph_node_completed",
                        {
                            "node": "tool",
                            "step": 3,
                            "next_node": "decide",
                            "tool_id": "asset.get",
                            "tool_call_id": "tool-call-1",
                        },
                    ),
                    _event(10, "diagnosis.graph_node_started", {"node": "decide", "step": 4}),
                    _event(
                        11,
                        "diagnosis.graph_node_completed",
                        {
                            "node": "decide",
                            "step": 4,
                            "next_node": "finish",
                            "inference_request_id": "inference-final",
                            "action": "FINAL",
                        },
                    ),
                    _event(12, "diagnosis.graph_node_started", {"node": "finish", "step": 5}),
                    _event(13, "diagnosis.graph_node_completed", {"node": "finish", "step": 5}),
                    _event(
                        14,
                        "diagnosis.completed",
                        {"diagnosis_run_id": "diagnosis-1", "stop_reason": "completed"},
                    ),
                ]
            )
            session.add_all(
                [
                    _checkpoint(1, _state()),
                    _checkpoint(2, _state(pending_request=_request("bearing noise"))),
                    _checkpoint(
                        3, _state(decision={"action": "RETRIEVE", "query": "bearing noise"})
                    ),
                    _checkpoint(
                        4, _state(decision={"action": "RETRIEVE", "query": "bearing noise"})
                    ),
                    _checkpoint(
                        5,
                        _state(
                            decision={"action": "RETRIEVE", "query": "bearing noise"},
                            evidence=[
                                {"citation_id": "knowledge-1", "content": "bearing inspection"}
                            ],
                            retrieval_guard={"release_id": "index-v1"},
                        ),
                    ),
                    _checkpoint(6, _state(pending_request=_request("bearing inspection"))),
                    _checkpoint(
                        7, _state(decision={"action": "CALL_TOOL", "tool_id": "asset.get"})
                    ),
                    _checkpoint(
                        8, _state(decision={"action": "CALL_TOOL", "tool_id": "asset.get"})
                    ),
                    _checkpoint(
                        9,
                        _state(
                            decision={"action": "CALL_TOOL", "tool_id": "asset.get"},
                            tool_facts=[
                                {
                                    "tool_id": "asset.get",
                                    "tool_call_id": "tool-call-1",
                                    "values": {"model_code": "PUMP-X100"},
                                }
                            ],
                        ),
                    ),
                    _checkpoint(10, _state(pending_request=_request("final evidence"))),
                    _checkpoint(
                        11, _state(decision={"action": "FINAL", "report": {"status": "COMPLETED"}})
                    ),
                    _checkpoint(
                        12, _state(decision={"action": "FINAL", "report": {"status": "COMPLETED"}})
                    ),
                    _checkpoint(13, _state(report={"status": "COMPLETED", "citations": []})),
                    _checkpoint(
                        14, _state(report={"status": "COMPLETED", "citations": []}, published=True)
                    ),
                ]
            )
            session.add_all(
                [
                    _inference(
                        "inference-retrieve", {"action": "RETRIEVE", "query": "bearing noise"}
                    ),
                    _inference("inference-tool", {"action": "CALL_TOOL", "tool_id": "asset.get"}),
                    _inference(
                        "inference-final", {"action": "FINAL", "report": {"status": "COMPLETED"}}
                    ),
                    ToolCallRecord(
                        tenant_id="trajectory-tenant",
                        tool_call_id="tool-call-1",
                        agent_run_id="agent-trajectory",
                        tool_id="asset.get",
                        tool_version="v1",
                        risk_tier="T0",
                        status="SUCCEEDED",
                        input_digest="input-sha256",
                        output_metadata={"source": "asset-registry"},
                        created_at=datetime(2026, 9, 28, tzinfo=UTC),
                        updated_at=datetime(2026, 9, 28, tzinfo=UTC),
                    ),
                ]
            )
            session.commit()

        trajectory = TrajectoryProjector(self.database).project(self.context, "agent-trajectory")

        self.assertEqual(
            [step.kind for step in trajectory.steps],
            ["MODEL_DECISION", "RETRIEVAL", "MODEL_DECISION", "TOOL", "MODEL_DECISION"],
        )
        self.assertEqual(trajectory.steps[0].observation["messages"][0]["content"], "bearing noise")
        self.assertEqual(trajectory.steps[0].action["action"], "RETRIEVE")
        self.assertEqual(trajectory.steps[0].model_response_hash, "response-inference-retrieve")
        self.assertEqual(trajectory.steps[1].action["query"], "bearing noise")
        self.assertEqual(trajectory.steps[1].result["evidence"][0]["citation_id"], "knowledge-1")
        self.assertEqual(trajectory.steps[3].action["tool_id"], "asset.get")
        self.assertEqual(
            trajectory.steps[3].result["tool_fact"]["values"]["model_code"], "PUMP-X100"
        )
        self.assertEqual(trajectory.steps[3].tool_call_id, "tool-call-1")
        self.assertEqual(trajectory.terminal_outcome.status, "COMPLETED")
        self.assertEqual(trajectory.terminal_outcome.event_type, "diagnosis.completed")

    def test_marks_a_tool_step_incomplete_when_no_tool_call_record_exists(self) -> None:
        with Session(self.engine) as session:
            session.add(TenantRecord(id=self.context.tenant_id, status="active"))
            session.add(
                AgentRunRecord(
                    tenant_id=self.context.tenant_id,
                    agent_run_id="agent-incomplete-tool",
                    status="NEEDS_INFORMATION",
                    budget={"max_steps": 8},
                    last_sequence=3,
                    version=3,
                    created_at=self.now,
                    updated_at=self.now,
                )
            )
            session.add_all(
                [
                    _event(
                        1,
                        "diagnosis.graph_node_started",
                        {"node": "tool", "step": 0},
                        "agent-incomplete-tool",
                    ),
                    _event(
                        2,
                        "diagnosis.graph_node_completed",
                        {"node": "tool", "step": 0, "tool_id": "asset.get", "tool_call_id": None},
                        "agent-incomplete-tool",
                    ),
                    _event(
                        3,
                        "diagnosis.needs_information",
                        {"diagnosis_run_id": "diagnosis-2", "stop_reason": "tool_failed"},
                        "agent-incomplete-tool",
                    ),
                ]
            )
            session.add_all(
                [
                    _checkpoint(
                        1,
                        _state(decision={"action": "CALL_TOOL", "tool_id": "asset.get"}),
                        "agent-incomplete-tool",
                    ),
                    _checkpoint(
                        2,
                        _state(
                            decision={"action": "CALL_TOOL", "tool_id": "asset.get"},
                            tool_failures=[
                                {"tool_id": "asset.get", "reason": "tool_rate_limit_exceeded"}
                            ],
                        ),
                        "agent-incomplete-tool",
                    ),
                ]
            )
            session.commit()

        trajectory = TrajectoryProjector(self.database).project(
            self.context, "agent-incomplete-tool"
        )

        tool_step = trajectory.steps[0]
        self.assertEqual(tool_step.result["tool_failure"]["reason"], "tool_rate_limit_exceeded")
        self.assertIn("tool_call_record_missing", tool_step.gaps)

    def test_uses_model_started_checkpoint_for_decision_observation(self) -> None:
        agent_run_id = "agent-model-observation"
        with Session(self.engine) as session:
            session.add(TenantRecord(id=self.context.tenant_id, status="active"))
            session.add(
                AgentRunRecord(
                    tenant_id=self.context.tenant_id,
                    agent_run_id=agent_run_id,
                    status="COMPLETED",
                    budget={"max_steps": 1},
                    last_sequence=4,
                    version=4,
                    created_at=self.now,
                    updated_at=self.now,
                )
            )
            session.add_all(
                [
                    _event(
                        1,
                        "diagnosis.graph_node_started",
                        {"node": "decide", "step": 0},
                        agent_run_id,
                    ),
                    _event(
                        2,
                        "diagnosis.model_started",
                        {"inference_request_id": "inference-observation", "node": "decide"},
                        agent_run_id,
                    ),
                    _event(
                        3,
                        "diagnosis.graph_node_completed",
                        {
                            "node": "decide",
                            "inference_request_id": "inference-observation",
                            "action": "FINAL",
                        },
                        agent_run_id,
                    ),
                    _event(4, "diagnosis.completed", {}, agent_run_id),
                ]
            )
            session.add_all(
                [
                    _checkpoint(1, _state(), agent_run_id),
                    _checkpoint(
                        2,
                        _state(pending_request=_request("persisted model request")),
                        agent_run_id,
                    ),
                    _checkpoint(
                        3,
                        _state(decision={"action": "FINAL", "report": {}}),
                        agent_run_id,
                    ),
                ]
            )
            session.add(
                _inference(
                    "inference-observation",
                    {"action": "FINAL", "report": {}},
                    agent_run_id,
                )
            )
            session.commit()

        trajectory = TrajectoryProjector(self.database).project(self.context, agent_run_id)

        self.assertEqual(
            trajectory.steps[0].observation["messages"][0]["content"],
            "persisted model request",
        )
        self.assertEqual(trajectory.steps[0].observation_checkpoint.sequence, 2)


def _event(
    sequence: int,
    event_type: str,
    payload: dict[str, object],
    agent_run_id: str = "agent-trajectory",
) -> AgentEventRecord:
    now = datetime(2026, 9, 28, tzinfo=UTC)
    return AgentEventRecord(
        tenant_id="trajectory-tenant",
        event_id=f"event-{agent_run_id}-{sequence}",
        agent_run_id=agent_run_id,
        sequence=sequence,
        event_type=event_type,
        payload=payload,
        visibility="authorized",
        occurred_at=now,
        created_at=now,
        updated_at=now,
    )


def _checkpoint(
    sequence: int,
    state: dict[str, object],
    agent_run_id: str = "agent-trajectory",
) -> AgentCheckpointRecord:
    now = datetime(2026, 9, 28, tzinfo=UTC)
    return AgentCheckpointRecord(
        tenant_id="trajectory-tenant",
        checkpoint_id=f"checkpoint-{agent_run_id}-{sequence}",
        agent_run_id=agent_run_id,
        sequence=sequence,
        graph_version="diagnosis-graph-v2",
        state=state,
        state_checksum=f"state-{sequence}",
        created_at=now,
        updated_at=now,
    )


def _state(**updates: object) -> dict[str, object]:
    return {"schema": "diagnosis-state/v2", **updates}


def _request(content: str) -> dict[str, object]:
    return {
        "messages": [{"role": "user", "content": content}],
        "context_hash": f"context-{content}",
    }


def _inference(
    inference_request_id: str,
    response: dict[str, object],
    agent_run_id: str = "agent-trajectory",
) -> ModelInferenceRecord:
    now = datetime(2026, 9, 28, tzinfo=UTC)
    return ModelInferenceRecord(
        tenant_id="trajectory-tenant",
        inference_request_id=inference_request_id,
        model_alias="diagnosis-model",
        resolved_release_id="release-1",
        manifest_hash="manifest-1",
        subject_id="trajectory-subject",
        trace_id="trace-1",
        agent_run_id=agent_run_id,
        diagnosis_run_id="diagnosis-1",
        prompt_bundle_id="prompt-1",
        index_release_id="index-v1",
        context_manifest_json={"context_hash": f"context-{inference_request_id}"},
        context_hash=f"context-{inference_request_id}",
        request_class="DIAGNOSIS",
        data_classification="CONFIDENTIAL",
        status="SUCCEEDED",
        deadline=now,
        max_output_tokens=1024,
        temperature=0.0,
        prompt_hash=f"prompt-{inference_request_id}",
        response_json=response,
        response_hash=f"response-{inference_request_id}",
        usage_prompt_tokens=10,
        usage_completion_tokens=10,
        finish_reason="stop",
        latency_breakdown_json={},
        safety_decision="ALLOWED",
        guardrail_policy_version="guardrail-v1",
        guardrail_findings_json=[],
        degraded_from=None,
        failure_reason=None,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )
