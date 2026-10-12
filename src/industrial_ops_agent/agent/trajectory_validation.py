"""Pure integrity checks for the existing trajectory projection contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from industrial_ops_agent.agent.trajectory import Trajectory, TrajectoryReference, TrajectoryStep


class TrajectoryQuality(StrEnum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"


class ValidationSeverity(StrEnum):
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    severity: ValidationSeverity
    message: str
    check: str
    blocks_evaluation: bool
    step_index: int | None = None
    step_event_id: str | None = None
    source_reference: TrajectoryReference | None = None


@dataclass(frozen=True, slots=True)
class ValidationCheckResult:
    name: str
    quality: TrajectoryQuality


@dataclass(frozen=True, slots=True)
class TrajectoryValidationReport:
    agent_run_id: str
    quality: TrajectoryQuality
    checks: tuple[ValidationCheckResult, ...]
    issues: tuple[ValidationIssue, ...]
    evaluation_eligible: bool
    contract_version: str = "trajectory-validation/v1"


_CHECKS = ("STRUCTURE", "OBSERVATION_BINDING", "ACTION_BINDING", "RESULT_BINDING", "TERMINAL")
_KINDS = frozenset({"MODEL_DECISION", "RETRIEVAL", "TOOL"})
_ACTIONS = frozenset({"RETRIEVE", "CALL_TOOL", "FINAL", "NEEDS_INFORMATION"})
_OUTCOMES = frozenset({"SUCCEEDED", "FAILED", "REJECTED", "CANCELLED"})
_TERMINAL_LABELS = {
    "completed": "COMPLETED",
    "failed": "FAILED",
    "cancelled": "CANCELLED",
    "needs_information": "NEEDS_INFORMATION",
}
# Exact mapping only: structured bindings are checked independently below.
_GAP_CHECKS = {
    "run_start_event_missing": "STRUCTURE",
    "model_started_event_missing": "OBSERVATION_BINDING",
    "decision_observation_checkpoint_missing": "OBSERVATION_BINDING",
    "decision_request_missing": "OBSERVATION_BINDING",
    "retrieval_observation_checkpoint_missing": "OBSERVATION_BINDING",
    "tool_observation_checkpoint_missing": "OBSERVATION_BINDING",
    "model_inference_record_missing": "ACTION_BINDING",
    "decision_action_missing": "ACTION_BINDING",
    "retrieval_query_missing": "ACTION_BINDING",
    "tool_id_missing": "ACTION_BINDING",
    "retrieval_result_checkpoint_missing": "RESULT_BINDING",
    "retrieval_evidence_missing": "RESULT_BINDING",
    "tool_call_record_missing": "RESULT_BINDING",
    "tool_result_checkpoint_missing": "RESULT_BINDING",
    "tool_result_missing": "RESULT_BINDING",
    "terminal_event_missing": "TERMINAL",
    "retrieval_candidate_ranking_unavailable": "RESULT_BINDING",
    "historical_metadata_unavailable": "STRUCTURE",
}
_BLOCKING_GAPS = frozenset(
    {
        "model_inference_record_missing",
        "decision_action_missing",
        "retrieval_result_checkpoint_missing",
        "retrieval_evidence_missing",
    }
)


def _present(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _quality(issues: tuple[ValidationIssue, ...]) -> TrajectoryQuality:
    if any(issue.severity == ValidationSeverity.ERROR for issue in issues):
        return TrajectoryQuality.FAIL
    if any(issue.blocks_evaluation for issue in issues):
        return TrajectoryQuality.PARTIAL
    return TrajectoryQuality.PASS


class _Issues:
    """Per-validation accumulator; no state retained by the validator."""

    def __init__(self) -> None:
        self.items: list[ValidationIssue] = []

    def add(
        self,
        check: str,
        code: str,
        message: str,
        *,
        error: bool = False,
        blocking: bool = True,
        index: int | None = None,
        step: TrajectoryStep | None = None,
        source: TrajectoryReference | None = None,
    ) -> None:
        self.items.append(
            ValidationIssue(
                code,
                ValidationSeverity.ERROR if error else ValidationSeverity.WARNING,
                message,
                check,
                error or blocking,
                index,
                step.event_id if step else None,
                source,
            )
        )


class TrajectoryValidator:
    """Validate an in-memory trajectory without resolving or executing anything."""

    def validate(self, trajectory: Trajectory) -> TrajectoryValidationReport:
        issues = _Issues()
        _structure(trajectory, issues)
        for index, step in enumerate(trajectory.steps):
            _observation(step, index, issues)
            _action(step, index, issues)
            _result(step, index, issues)
            _gaps(step.gaps, issues, index, step)
        _terminal(trajectory, issues)
        _gaps(trajectory.gaps, issues)
        result = tuple(issues.items)
        quality = _quality(result)
        checks = tuple(
            ValidationCheckResult(
                name,
                _quality(tuple(issue for issue in result if issue.check == name)),
            )
            for name in _CHECKS
        )
        return TrajectoryValidationReport(
            trajectory.agent_run_id,
            quality,
            checks,
            result,
            quality == TrajectoryQuality.PASS,
        )


def _structure(trajectory: Trajectory, issues: _Issues) -> None:
    if not _present(trajectory.agent_run_id):
        issues.add("STRUCTURE", "RUN_ID_MISSING", "Run identity is empty.", error=True)
    seen: dict[str, set[str]] = {
        "event_id": set(),
        "model_inference_id": set(),
        "tool_call_id": set(),
    }
    references: dict[str, TrajectoryReference] = {}
    references_by_sequence: dict[int, TrajectoryReference] = {}
    previous = 0
    for index, step in enumerate(trajectory.steps):
        if step.kind not in _KINDS:
            issues.add(
                "STRUCTURE",
                "STEP_KIND_UNSUPPORTED",
                "Unsupported projected step kind.",
                error=True,
                index=index,
                step=step,
            )
        if step.sequence <= previous:
            issues.add(
                "STRUCTURE",
                "STEP_SEQUENCE_INVALID",
                "Sequences must be positive/increasing.",
                error=True,
                index=index,
                step=step,
            )
        previous = step.sequence
        if not _present(step.event_id):
            issues.add(
                "STRUCTURE",
                "STEP_EVENT_ID_MISSING",
                "Step event identity is empty.",
                error=True,
                index=index,
                step=step,
            )
        for field in seen:
            identity = getattr(step, field)
            if _present(identity):
                if identity in seen[field] or (
                    field == "event_id" and identity == trajectory.start_event_id
                ):
                    issues.add(
                        "STRUCTURE",
                        "STEP_IDENTITY_DUPLICATE",
                        f"Repeated {field}.",
                        error=True,
                        index=index,
                        step=step,
                    )
                seen[field].add(identity)
        for is_result, ref in (
            (False, step.observation_checkpoint),
            (True, step.result_checkpoint),
        ):
            if ref is None:
                continue
            if (
                ref.sequence is None
                or not _valid_reference(ref)
                or (ref.sequence != step.sequence if is_result else ref.sequence >= step.sequence)
            ):
                issues.add(
                    "STRUCTURE",
                    "CHECKPOINT_BINDING_INVALID",
                    "Invalid checkpoint identity/order.",
                    error=True,
                    index=index,
                    step=step,
                    source=ref,
                )
            if ref.record_id in references and references[ref.record_id] != ref:
                issues.add(
                    "STRUCTURE",
                    "CHECKPOINT_BINDING_CONFLICT",
                    "One checkpoint has conflicting bindings.",
                    error=True,
                    index=index,
                    step=step,
                    source=ref,
                )
            if ref.sequence is not None:
                if (
                    ref.sequence in references_by_sequence
                    and references_by_sequence[ref.sequence] != ref
                ):
                    issues.add(
                        "STRUCTURE",
                        "CHECKPOINT_SEQUENCE_CONFLICT",
                        "One checkpoint sequence has conflicting records.",
                        error=True,
                        index=index,
                        step=step,
                        source=ref,
                    )
                references_by_sequence[ref.sequence] = ref
            references[ref.record_id] = ref
            if not _present(ref.checksum):
                issues.add(
                    "STRUCTURE",
                    "CHECKPOINT_CHECKSUM_MISSING",
                    "Checkpoint hash attribution is incomplete.",
                    index=index,
                    step=step,
                    source=ref,
                )


def _valid_reference(ref: TrajectoryReference | None) -> bool:
    return bool(
        ref
        and ref.record_type == "agent_checkpoint"
        and _present(ref.record_id)
        and ref.sequence is not None
        and ref.sequence > 0
    )


def _observation(step: TrajectoryStep, index: int, issues: _Issues) -> None:
    if step.kind not in _KINDS:
        return
    if not step.observation and not _valid_reference(step.observation_checkpoint):
        issues.add(
            "OBSERVATION_BINDING",
            "OBSERVATION_MISSING",
            "Action has no input or usable reference.",
            error=True,
            index=index,
            step=step,
        )
    request_id = step.observation.get("inference_request_id")
    if (
        step.kind == "MODEL_DECISION"
        and _present(request_id)
        and _present(step.model_inference_id)
        and request_id != step.model_inference_id
    ):
        issues.add(
            "OBSERVATION_BINDING",
            "INFERENCE_OBSERVATION_CONFLICT",
            "Request and inference identities disagree.",
            error=True,
            index=index,
            step=step,
            source=step.observation_checkpoint,
        )


def _action(step: TrajectoryStep, index: int, issues: _Issues) -> None:
    token = step.action.get("action")
    expected = {"RETRIEVAL": "RETRIEVE", "TOOL": "CALL_TOOL"}.get(step.kind)
    if step.kind in _KINDS and (
        not isinstance(token, str)
        or token not in _ACTIONS
        or (expected is not None and token != expected)
    ):
        issues.add(
            "ACTION_BINDING",
            "ACTION_UNSUPPORTED",
            "Missing or contradictory action token.",
            error=True,
            index=index,
            step=step,
        )
    if step.kind == "MODEL_DECISION":
        for value, code in (
            (step.model_inference_id, "MODEL_INFERENCE_ID_MISSING"),
            (step.model_response_hash, "MODEL_RESPONSE_HASH_MISSING"),
        ):
            if not _present(value):
                issues.add(
                    "ACTION_BINDING",
                    code,
                    "Model decision attribution is incomplete.",
                    index=index,
                    step=step,
                )
    elif step.kind == "RETRIEVAL" and not _present(step.action.get("query")):
        issues.add(
            "ACTION_BINDING",
            "RETRIEVAL_QUERY_MISSING",
            "Projected retrieval query is unavailable.",
            index=index,
            step=step,
            source=step.observation_checkpoint,
        )
    elif step.kind == "TOOL":
        if not _present(step.action.get("tool_id")):
            issues.add(
                "ACTION_BINDING",
                "TOOL_ID_MISSING",
                "Tool identity is unavailable.",
                error=True,
                index=index,
                step=step,
            )
        if not _present(step.tool_call_id) and not _unbound_failure(step):
            issues.add(
                "ACTION_BINDING",
                "TOOL_CALL_ID_MISSING",
                "Execution has no call binding.",
                index=index,
                step=step,
            )
        for key in ("tool_fact", "tool_failure"):
            item = step.result.get(key)
            if not isinstance(item, dict):
                continue
            for field, expected_id in (
                ("tool_id", step.action.get("tool_id")),
                ("tool_call_id", step.tool_call_id),
            ):
                if (
                    _present(item.get(field))
                    and _present(expected_id)
                    and item[field] != expected_id
                ):
                    issues.add(
                        "ACTION_BINDING",
                        "TOOL_IDENTITY_CONFLICT",
                        f"Result {field} contradicts action.",
                        error=True,
                        index=index,
                        step=step,
                        source=step.result_checkpoint,
                    )


def _tool_outcome(step: TrajectoryStep) -> str | None:
    audit = step.result.get("tool_call")
    status = audit.get("status") if isinstance(audit, dict) else None
    return status if isinstance(status, str) and status in _OUTCOMES else None


def _failure(step: TrajectoryStep) -> bool:
    value = step.result.get("tool_failure")
    return isinstance(value, dict) and _present(value.get("reason"))


def _tool_result(step: TrajectoryStep) -> bool:
    fact = step.result.get("tool_fact")
    return bool(
        (isinstance(fact, dict) and "values" in fact) or _failure(step) or _tool_outcome(step)
    )


def _unbound_failure(step: TrajectoryStep) -> bool:
    return (
        not _present(step.tool_call_id)
        and _failure(step)
        and not step.result.get("tool_fact")
        and not step.result.get("tool_call")
    )


def _result(step: TrajectoryStep, index: int, issues: _Issues) -> None:
    missing = False
    if step.kind == "MODEL_DECISION":
        missing = not (
            step.action and (_present(step.model_response_hash) or step.result_checkpoint)
        )
    elif step.kind == "RETRIEVAL":
        missing = not isinstance(step.result.get("evidence"), list)
    elif step.kind == "TOOL":
        missing = not _tool_result(step)
        if _failure(step) and _tool_outcome(step) == "SUCCEEDED":
            issues.add(
                "RESULT_BINDING",
                "TOOL_OUTCOME_CONFLICT",
                "Successful audit contradicts explicit failure.",
                error=True,
                index=index,
                step=step,
                source=step.result_checkpoint,
            )
        if step.result.get("tool_call") and _tool_outcome(step) is None:
            issues.add(
                "RESULT_BINDING",
                "TOOL_OUTCOME_UNSUPPORTED",
                "Audit has no supported explicit outcome.",
                index=index,
                step=step,
                source=step.result_checkpoint,
            )
    if missing:
        issues.add(
            "RESULT_BINDING",
            f"{step.kind.removesuffix('_DECISION')}_RESULT_MISSING",
            "Action has no interpretable result binding.",
            index=index,
            step=step,
            source=step.result_checkpoint,
        )


def _terminal(trajectory: Trajectory, issues: _Issues) -> None:
    terminal = trajectory.terminal_outcome
    if terminal is None:
        issues.add(
            "TERMINAL", "TERMINAL_MISSING", "Run has no projected terminal event.", error=True
        )
        return
    source = TrajectoryReference("agent_event", terminal.event_id, terminal.sequence, None)
    label_status = _TERMINAL_LABELS.get(terminal.event_type.rsplit(".", 1)[-1])
    if label_status is None:
        issues.add(
            "TERMINAL",
            "TERMINAL_EVENT_UNSUPPORTED",
            "Event label cannot establish a v1 lifecycle outcome.",
            error=True,
            source=source,
        )
    elif label_status != terminal.status:
        issues.add(
            "TERMINAL",
            "TERMINAL_EVENT_STATUS_CONFLICT",
            "Event and terminal status disagree.",
            error=True,
            source=source,
        )
    if trajectory.status != terminal.status:
        issues.add(
            "TERMINAL",
            "TERMINAL_RUN_STATUS_CONFLICT",
            "Run and terminal status disagree.",
            error=True,
            source=source,
        )
    last_sequence = trajectory.steps[-1].sequence if trajectory.steps else 0
    if (
        not _present(terminal.event_id)
        or terminal.sequence <= last_sequence
        or terminal.event_id == trajectory.start_event_id
        or any(step.event_id == terminal.event_id for step in trajectory.steps)
    ):
        issues.add(
            "TERMINAL",
            "TERMINAL_IDENTITY_ORDER_INVALID",
            "Terminal identity or ordering is invalid.",
            error=True,
            source=source,
        )


def _gaps(
    gaps: tuple[str, ...],
    issues: _Issues,
    index: int | None = None,
    step: TrajectoryStep | None = None,
) -> None:
    for gap in dict.fromkeys(gaps):
        check = _GAP_CHECKS.get(gap)
        blocking = gap in _BLOCKING_GAPS or check is None
        if step is not None:
            if gap == "tool_call_record_missing":
                blocking = not _unbound_failure(step)
            elif gap in {"tool_result_checkpoint_missing", "tool_result_missing"}:
                blocking = not _tool_result(step)
        elif gap in {
            "tool_call_record_missing",
            "tool_result_checkpoint_missing",
            "tool_result_missing",
        }:
            blocking = True
        issues.add(
            check or "STRUCTURE",
            f"PROJECTOR_GAP_{gap.upper()}" if check else "PROJECTOR_GAP_UNKNOWN",
            f"Projector limitation: {gap}.",
            blocking=blocking,
            index=index,
            step=step,
            source=step.result_checkpoint
            if step and check == "RESULT_BINDING"
            else step.observation_checkpoint
            if step
            else None,
        )
