"""Read-only projection of persisted agent execution into trajectories."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select

from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    AgentCheckpointRecord,
    AgentEventRecord,
    AgentRunRecord,
    ModelInferenceRecord,
    ToolCallRecord,
)
from industrial_ops_agent.persistence.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class TrajectoryReference:
    """Immutable reference to an existing execution record."""

    record_type: str
    record_id: str
    sequence: int | None
    checksum: str | None


@dataclass(frozen=True, slots=True)
class TrajectoryStep:
    """One model decision or executed environment action."""

    kind: str
    event_id: str
    sequence: int
    occurred_at: datetime
    observation: dict[str, Any]
    observation_checkpoint: TrajectoryReference | None
    action: dict[str, Any]
    result: dict[str, Any]
    result_checkpoint: TrajectoryReference | None
    model_inference_id: str | None
    model_response_hash: str | None
    tool_call_id: str | None
    gaps: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TrajectoryTerminalOutcome:
    """The final persisted execution event and run status."""

    event_id: str
    event_type: str
    sequence: int
    occurred_at: datetime
    status: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Trajectory:
    """A domain-neutral, read-only view of a single AgentRun."""

    agent_run_id: str
    status: str
    budget: dict[str, Any]
    started_at: datetime | None
    start_event_id: str | None
    steps: tuple[TrajectoryStep, ...]
    terminal_outcome: TrajectoryTerminalOutcome | None
    gaps: tuple[str, ...]


class TrajectoryRunNotFoundError(LookupError):
    """Raised when an AgentRun is not visible to the supplied tenant context."""


class TrajectoryProjector:
    """Projects existing persistence records without changing agent execution."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def project(self, context: TenantContext, agent_run_id: str) -> Trajectory:
        """Load one AgentRun and project its persisted execution trace."""

        with self._database.transaction(context) as session:
            agent_run = session.scalar(
                select(AgentRunRecord).where(
                    AgentRunRecord.tenant_id == context.tenant_id,
                    AgentRunRecord.agent_run_id == agent_run_id,
                )
            )
            if agent_run is None:
                raise TrajectoryRunNotFoundError(agent_run_id)

            events = list(
                session.scalars(
                    select(AgentEventRecord)
                    .where(
                        AgentEventRecord.tenant_id == context.tenant_id,
                        AgentEventRecord.agent_run_id == agent_run_id,
                    )
                    .order_by(AgentEventRecord.sequence)
                )
            )
            checkpoints = list(
                session.scalars(
                    select(AgentCheckpointRecord)
                    .where(
                        AgentCheckpointRecord.tenant_id == context.tenant_id,
                        AgentCheckpointRecord.agent_run_id == agent_run_id,
                    )
                    .order_by(AgentCheckpointRecord.sequence)
                )
            )
            inferences = list(
                session.scalars(
                    select(ModelInferenceRecord)
                    .where(
                        ModelInferenceRecord.tenant_id == context.tenant_id,
                        ModelInferenceRecord.agent_run_id == agent_run_id,
                    )
                    .order_by(ModelInferenceRecord.created_at)
                )
            )
            tool_calls = list(
                session.scalars(
                    select(ToolCallRecord)
                    .where(
                        ToolCallRecord.tenant_id == context.tenant_id,
                        ToolCallRecord.agent_run_id == agent_run_id,
                    )
                    .order_by(ToolCallRecord.created_at)
                )
            )

            return self._project_records(agent_run, events, checkpoints, inferences, tool_calls)

    def _project_records(
        self,
        agent_run: AgentRunRecord,
        events: list[AgentEventRecord],
        checkpoints: list[AgentCheckpointRecord],
        inferences: list[ModelInferenceRecord],
        tool_calls: list[ToolCallRecord],
    ) -> Trajectory:
        checkpoint_by_sequence = {checkpoint.sequence: checkpoint for checkpoint in checkpoints}
        inference_by_id = {item.inference_request_id: item for item in inferences}
        tool_call_by_id = {item.tool_call_id: item for item in tool_calls}
        node_starts: dict[str, AgentEventRecord] = {}
        model_starts: dict[str, AgentEventRecord] = {}
        steps: list[TrajectoryStep] = []
        gaps: list[str] = []
        start_event = next(
            (event for event in events if event.event_type.endswith(".graph_started")), None
        )

        if start_event is None:
            gaps.append("run_start_event_missing")

        for event in events:
            if event.event_type.endswith(".model_started"):
                inference_id = _text(event.payload.get("inference_request_id"))
                if inference_id:
                    model_starts[inference_id] = event
                continue
            if event.event_type.endswith(".graph_node_started"):
                node = _text(event.payload.get("node"))
                if node:
                    node_starts[node] = event
                continue
            if not event.event_type.endswith(".graph_node_completed"):
                continue

            node = _text(event.payload.get("node"))
            node_start = node_starts.pop(node, None) if node else None
            if node == "decide":
                steps.append(
                    _project_decision(
                        event,
                        node_start,
                        checkpoint_by_sequence,
                        inference_by_id,
                        model_starts,
                    )
                )
            elif node == "retrieve":
                steps.append(_project_retrieval(event, node_start, checkpoint_by_sequence))
            elif node == "tool":
                steps.append(
                    _project_tool(
                        event,
                        node_start,
                        checkpoint_by_sequence,
                        tool_call_by_id,
                    )
                )

        terminal_outcome = _terminal_outcome(agent_run, events)
        if terminal_outcome is None and agent_run.status in _TERMINAL_STATUSES:
            gaps.append("terminal_event_missing")

        return Trajectory(
            agent_run_id=agent_run.agent_run_id,
            status=agent_run.status,
            budget=deepcopy(agent_run.budget),
            started_at=start_event.occurred_at if start_event else None,
            start_event_id=start_event.event_id if start_event else None,
            steps=tuple(steps),
            terminal_outcome=terminal_outcome,
            gaps=tuple(gaps),
        )


_TERMINAL_STATUSES = frozenset(
    {"COMPLETED", "FAILED", "CANCELLED", "NEEDS_INFORMATION", "ESCALATED", "WAITING_EXPERT"}
)


def _project_decision(
    event: AgentEventRecord,
    node_start: AgentEventRecord | None,
    checkpoints: dict[int, AgentCheckpointRecord],
    inferences: dict[str, ModelInferenceRecord],
    model_starts: dict[str, AgentEventRecord],
) -> TrajectoryStep:
    gaps: list[str] = []
    inference_id = _text(event.payload.get("inference_request_id"))
    inference = inferences.get(inference_id) if inference_id else None
    model_start = model_starts.get(inference_id) if inference_id else None
    observation_checkpoint = _checkpoint_for_event(model_start or node_start, checkpoints)
    result_checkpoint = _checkpoint_for_event(event, checkpoints)
    observation = _pending_request(observation_checkpoint)
    if model_start is None:
        gaps.append("model_started_event_missing")
    if observation_checkpoint is None:
        gaps.append("decision_observation_checkpoint_missing")
    elif not observation:
        gaps.append("decision_request_missing")
    if inference is None:
        gaps.append("model_inference_record_missing")

    action = _json(inference.response_json) if inference and inference.response_json else {}
    if not action:
        action = _json(_state_value(result_checkpoint, "decision"))
    if not action:
        action = {"action": event.payload.get("action")} if event.payload.get("action") else {}
        gaps.append("decision_action_missing")

    return TrajectoryStep(
        kind="MODEL_DECISION",
        event_id=event.event_id,
        sequence=event.sequence,
        occurred_at=event.occurred_at,
        observation=observation,
        observation_checkpoint=_reference(observation_checkpoint),
        action=action,
        result={
            "next_node": event.payload.get("next_node"),
            "model_steps": event.payload.get("model_steps"),
            "tokens_used": event.payload.get("tokens_used"),
            "model_binding": _model_binding(inference),
        },
        result_checkpoint=_reference(result_checkpoint),
        model_inference_id=inference_id,
        model_response_hash=inference.response_hash if inference else None,
        tool_call_id=None,
        gaps=tuple(gaps),
    )


def _project_retrieval(
    event: AgentEventRecord,
    node_start: AgentEventRecord | None,
    checkpoints: dict[int, AgentCheckpointRecord],
) -> TrajectoryStep:
    gaps: list[str] = []
    observation_checkpoint = _checkpoint_for_event(node_start, checkpoints)
    result_checkpoint = _checkpoint_for_event(event, checkpoints)
    decision = _json(_state_value(observation_checkpoint, "decision"))
    query = decision.get("query")
    if observation_checkpoint is None:
        gaps.append("retrieval_observation_checkpoint_missing")
    if query is None:
        gaps.append("retrieval_query_missing")
    evidence = _state_value(result_checkpoint, "evidence")
    guard = _state_value(result_checkpoint, "retrieval_guard")
    if result_checkpoint is None:
        gaps.append("retrieval_result_checkpoint_missing")
    if evidence is None:
        gaps.append("retrieval_evidence_missing")

    return TrajectoryStep(
        kind="RETRIEVAL",
        event_id=event.event_id,
        sequence=event.sequence,
        occurred_at=event.occurred_at,
        observation=decision,
        observation_checkpoint=_reference(observation_checkpoint),
        action={"action": "RETRIEVE", "query": query},
        result={
            "evidence": deepcopy(evidence) if evidence is not None else [],
            "retrieval_guard": deepcopy(guard) if guard is not None else None,
            "evidence_count": event.payload.get("evidence_count"),
        },
        result_checkpoint=_reference(result_checkpoint),
        model_inference_id=None,
        model_response_hash=None,
        tool_call_id=None,
        gaps=tuple(gaps),
    )


def _project_tool(
    event: AgentEventRecord,
    node_start: AgentEventRecord | None,
    checkpoints: dict[int, AgentCheckpointRecord],
    tool_calls: dict[str, ToolCallRecord],
) -> TrajectoryStep:
    gaps: list[str] = []
    observation_checkpoint = _checkpoint_for_event(node_start, checkpoints)
    result_checkpoint = _checkpoint_for_event(event, checkpoints)
    decision = _json(_state_value(observation_checkpoint, "decision"))
    tool_id = _text(event.payload.get("tool_id")) or _text(decision.get("tool_id"))
    tool_call_id = _text(event.payload.get("tool_call_id"))
    tool_call = tool_calls.get(tool_call_id) if tool_call_id else None
    if observation_checkpoint is None:
        gaps.append("tool_observation_checkpoint_missing")
    if not tool_id:
        gaps.append("tool_id_missing")
    if tool_call is None:
        gaps.append("tool_call_record_missing")

    tool_fact = _find_tool_item(
        _state_value(result_checkpoint, "tool_facts"), tool_id, tool_call_id
    )
    tool_failure = _find_tool_item(
        _state_value(result_checkpoint, "tool_failures"), tool_id, tool_call_id
    )
    if result_checkpoint is None:
        gaps.append("tool_result_checkpoint_missing")
    if tool_fact is None and tool_failure is None:
        gaps.append("tool_result_missing")

    result: dict[str, Any] = {}
    if tool_fact is not None:
        result["tool_fact"] = tool_fact
    if tool_failure is not None:
        result["tool_failure"] = tool_failure
    if tool_call is not None:
        result["tool_call"] = {
            "status": tool_call.status,
            "tool_version": tool_call.tool_version,
            "risk_tier": tool_call.risk_tier,
            "input_digest": tool_call.input_digest,
            "output_metadata": deepcopy(tool_call.output_metadata),
        }

    return TrajectoryStep(
        kind="TOOL",
        event_id=event.event_id,
        sequence=event.sequence,
        occurred_at=event.occurred_at,
        observation=decision,
        observation_checkpoint=_reference(observation_checkpoint),
        action={"action": "CALL_TOOL", "tool_id": tool_id},
        result=result,
        result_checkpoint=_reference(result_checkpoint),
        model_inference_id=None,
        model_response_hash=None,
        tool_call_id=tool_call_id,
        gaps=tuple(gaps),
    )


def _terminal_outcome(
    agent_run: AgentRunRecord, events: list[AgentEventRecord]
) -> TrajectoryTerminalOutcome | None:
    if agent_run.status not in _TERMINAL_STATUSES or not events:
        return None
    event = events[-1]
    return TrajectoryTerminalOutcome(
        event_id=event.event_id,
        event_type=event.event_type,
        sequence=event.sequence,
        occurred_at=event.occurred_at,
        status=agent_run.status,
        payload=_json(event.payload),
    )


def _checkpoint_for_event(
    event: AgentEventRecord | None, checkpoints: dict[int, AgentCheckpointRecord]
) -> AgentCheckpointRecord | None:
    return checkpoints.get(event.sequence) if event else None


def _reference(checkpoint: AgentCheckpointRecord | None) -> TrajectoryReference | None:
    if checkpoint is None:
        return None
    return TrajectoryReference(
        record_type="agent_checkpoint",
        record_id=checkpoint.checkpoint_id,
        sequence=checkpoint.sequence,
        checksum=checkpoint.state_checksum,
    )


def _pending_request(checkpoint: AgentCheckpointRecord | None) -> dict[str, Any]:
    return _json(_state_value(checkpoint, "pending_request"))


def _state_value(checkpoint: AgentCheckpointRecord | None, key: str) -> Any:
    return checkpoint.state.get(key) if checkpoint else None


def _model_binding(inference: ModelInferenceRecord | None) -> dict[str, Any] | None:
    if inference is None:
        return None
    return {
        "model_alias": inference.model_alias,
        "resolved_release_id": inference.resolved_release_id,
        "manifest_hash": inference.manifest_hash,
        "prompt_hash": inference.prompt_hash,
        "context_hash": inference.context_hash,
    }


def _find_tool_item(
    value: Any, tool_id: str | None, tool_call_id: str | None
) -> dict[str, Any] | None:
    if not isinstance(value, list):
        return None
    for item in value:
        if not isinstance(item, dict):
            continue
        if tool_call_id and item.get("tool_call_id") == tool_call_id:
            return _json(item)
        if tool_id and item.get("tool_id") == tool_id:
            return _json(item)
    return None


def _json(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
