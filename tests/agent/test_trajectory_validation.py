from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest import TestCase

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from industrial_ops_agent.agent.trajectory import (
    Trajectory,
    TrajectoryProjector,
    TrajectoryReference,
    TrajectoryStep,
    TrajectoryTerminalOutcome,
)
from industrial_ops_agent.agent.trajectory_validation import (
    TrajectoryQuality,
    TrajectoryValidator,
    ValidationSeverity,
)
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    AgentCheckpointRecord,
    AgentEventRecord,
    AgentRunRecord,
    Base,
    TenantRecord,
)
from industrial_ops_agent.persistence.tenant import TenantContext

NOW = datetime(2026, 10, 1, tzinfo=UTC)


def reference(sequence: int) -> TrajectoryReference:
    return TrajectoryReference("agent_checkpoint", f"checkpoint-{sequence}", sequence, "hash")


def complete() -> Trajectory:
    steps = (
        TrajectoryStep(
            "MODEL_DECISION",
            "decision",
            2,
            NOW,
            {"inference_request_id": "inference-1", "messages": [{"content": "question"}]},
            reference(1),
            {"action": "RETRIEVE", "query": "question"},
            {"next_node": "retrieve", "model_binding": {"resolved_release_id": "release"}},
            reference(2),
            "inference-1",
            "response-hash",
            None,
            (),
        ),
        TrajectoryStep(
            "RETRIEVAL",
            "retrieval",
            4,
            NOW,
            {"action": "RETRIEVE", "query": "question"},
            reference(3),
            {"action": "RETRIEVE", "query": "question"},
            {"evidence": [], "evidence_count": 0},
            reference(4),
            None,
            None,
            None,
            (),
        ),
        TrajectoryStep(
            "TOOL",
            "tool",
            6,
            NOW,
            {"action": "CALL_TOOL", "tool_id": "records.read"},
            reference(5),
            {"action": "CALL_TOOL", "tool_id": "records.read"},
            {
                "tool_fact": {"tool_id": "records.read", "tool_call_id": "call-1", "values": {}},
                "tool_call": {"status": "SUCCEEDED"},
            },
            reference(6),
            None,
            None,
            "call-1",
            (),
        ),
    )
    terminal = TrajectoryTerminalOutcome("end", "application.completed", 7, NOW, "COMPLETED", {})
    return Trajectory("run-1", "COMPLETED", {}, NOW, "start", steps, terminal, ())


def changed_step(trajectory: Trajectory, index: int, **changes: object) -> Trajectory:
    steps = list(trajectory.steps)
    steps[index] = replace(steps[index], **changes)
    return replace(trajectory, steps=tuple(steps))


class TrajectoryValidationTests(TestCase):
    def setUp(self) -> None:
        self.validator = TrajectoryValidator()

    def test_complete_success_is_pass_and_eligible(self) -> None:
        report = self.validator.validate(complete())
        self.assertEqual(report.agent_run_id, "run-1")
        self.assertEqual(report.quality, TrajectoryQuality.PASS)
        self.assertTrue(report.evaluation_eligible)
        self.assertEqual(report.issues, ())
        self.assertEqual(
            [check.name for check in report.checks],
            [
                "STRUCTURE",
                "OBSERVATION_BINDING",
                "ACTION_BINDING",
                "RESULT_BINDING",
                "TERMINAL",
            ],
        )

    def test_complete_failed_execution_is_still_pass(self) -> None:
        trajectory = complete()
        trajectory = changed_step(
            trajectory,
            2,
            result={
                "tool_failure": {"tool_id": "records.read", "reason": "environment_unavailable"},
                "tool_call": {"status": "FAILED"},
            },
        )
        trajectory = replace(
            trajectory,
            status="FAILED",
            terminal_outcome=replace(
                trajectory.terminal_outcome,
                event_type="application.failed",
                status="FAILED",
            ),
        )
        report = self.validator.validate(trajectory)
        self.assertEqual(report.quality, TrajectoryQuality.PASS)
        self.assertTrue(report.evaluation_eligible)

    def test_noncritical_ranking_and_history_limitations_do_not_block(self) -> None:
        trajectory = replace(
            complete(),
            gaps=(
                "retrieval_candidate_ranking_unavailable",
                "historical_metadata_unavailable",
            ),
        )
        report = self.validator.validate(trajectory)
        self.assertEqual(report.quality, TrajectoryQuality.PASS)
        self.assertTrue(report.evaluation_eligible)
        self.assertTrue(
            all(issue.severity == ValidationSeverity.WARNING for issue in report.issues)
        )
        self.assertTrue(all(not issue.blocks_evaluation for issue in report.issues))

    def test_missing_observation_is_fail_for_all_supported_steps(self) -> None:
        for index in range(3):
            with self.subTest(index=index):
                report = self.validator.validate(
                    changed_step(
                        complete(),
                        index,
                        observation={},
                        observation_checkpoint=None,
                    )
                )
                self.assertEqual(report.quality, TrajectoryQuality.FAIL)
                issue = next(i for i in report.issues if i.code == "OBSERVATION_MISSING")
                self.assertEqual(issue.step_index, index)
                self.assertFalse(report.evaluation_eligible)

    def test_checkpoint_reference_is_sufficient_observation(self) -> None:
        report = self.validator.validate(changed_step(complete(), 0, observation={}))
        self.assertEqual(report.quality, TrajectoryQuality.PASS)

    def test_executed_tool_without_result_is_partial(self) -> None:
        report = self.validator.validate(
            changed_step(
                complete(),
                2,
                result={},
                result_checkpoint=None,
                gaps=("tool_result_missing",),
            )
        )
        self.assertEqual(report.quality, TrajectoryQuality.PARTIAL)
        self.assertFalse(report.evaluation_eligible)
        self.assertIn("TOOL_RESULT_MISSING", [i.code for i in report.issues])

    def test_explicit_preexecution_failure_needs_no_fabricated_call(self) -> None:
        trajectory = changed_step(
            complete(),
            2,
            tool_call_id=None,
            result={
                "tool_failure": {"tool_id": "records.read", "reason": "tool_rate_limit_exceeded"},
            },
            gaps=("tool_call_record_missing",),
        )
        report = self.validator.validate(trajectory)
        self.assertEqual(report.quality, TrajectoryQuality.PASS)
        self.assertIsNone(trajectory.steps[2].tool_call_id)

    def test_successful_fact_without_call_identity_is_partial(self) -> None:
        trajectory = changed_step(
            complete(),
            2,
            tool_call_id=None,
            result={
                "tool_fact": {"tool_id": "records.read", "values": {}},
            },
        )
        self.assertEqual(self.validator.validate(trajectory).quality, TrajectoryQuality.PARTIAL)

    def test_audited_outcome_alone_is_valid_even_without_checkpoint_fact(self) -> None:
        for status in ("SUCCEEDED", "FAILED", "REJECTED", "CANCELLED"):
            with self.subTest(status=status):
                trajectory = changed_step(
                    complete(),
                    2,
                    result={"tool_call": {"status": status}},
                    result_checkpoint=None,
                    gaps=("tool_result_missing",),
                )
                self.assertEqual(
                    self.validator.validate(trajectory).quality, TrajectoryQuality.PASS
                )

    def test_missing_terminal_is_fail(self) -> None:
        report = self.validator.validate(replace(complete(), terminal_outcome=None))
        self.assertEqual(report.quality, TrajectoryQuality.FAIL)
        self.assertIn("TERMINAL_MISSING", [i.code for i in report.issues])

    def test_terminal_status_label_and_order_contradictions_are_fail(self) -> None:
        original = complete()
        for changes in (
            {"status": "FAILED"},
            {"event_type": "application.failed"},
            {"event_type": "application.graph_node_completed"},
            {"sequence": 6},
            {"event_id": "tool"},
        ):
            with self.subTest(changes=changes):
                trajectory = replace(
                    original,
                    terminal_outcome=replace(
                        original.terminal_outcome,
                        **changes,
                    ),
                )
                self.assertEqual(
                    self.validator.validate(trajectory).quality, TrajectoryQuality.FAIL
                )

    def test_cancelled_and_needs_information_terminal_are_valid(self) -> None:
        for status in ("CANCELLED", "NEEDS_INFORMATION"):
            with self.subTest(status=status):
                trajectory = complete()
                trajectory = replace(
                    trajectory,
                    status=status,
                    terminal_outcome=replace(
                        trajectory.terminal_outcome,
                        status=status,
                        event_type=f"application.{status.lower()}",
                    ),
                )
                self.assertEqual(
                    self.validator.validate(trajectory).quality, TrajectoryQuality.PASS
                )

    def test_invalid_sequence_identity_and_type_are_fail(self) -> None:
        for index, changes in (
            (1, {"sequence": 2}),
            (0, {"sequence": 0}),
            (1, {"event_id": "decision"}),
            (0, {"event_id": ""}),
            (0, {"kind": "UNKNOWN"}),
            (0, {"action": {"action": "UNKNOWN"}}),
        ):
            with self.subTest(changes=changes):
                report = self.validator.validate(changed_step(complete(), index, **changes))
                self.assertEqual(report.quality, TrajectoryQuality.FAIL)
        self.assertEqual(
            self.validator.validate(replace(complete(), agent_run_id="")).quality,
            TrajectoryQuality.FAIL,
        )

    def test_duplicate_execution_identity_is_fail(self) -> None:
        for index in (0, 2):
            trajectory = complete()
            duplicate = replace(
                trajectory.steps[index],
                event_id="duplicate",
                sequence=8,
                observation_checkpoint=reference(7),
                result_checkpoint=reference(8),
            )
            trajectory = replace(
                trajectory,
                steps=(*trajectory.steps, duplicate),
                terminal_outcome=replace(trajectory.terminal_outcome, sequence=9),
            )
            with self.subTest(kind=duplicate.kind):
                self.assertEqual(
                    self.validator.validate(trajectory).quality, TrajectoryQuality.FAIL
                )

    def test_conflicting_request_tool_and_checkpoint_references_are_fail(self) -> None:
        cases = (
            changed_step(complete(), 0, observation={"inference_request_id": "other"}),
            changed_step(
                complete(),
                2,
                result={
                    "tool_fact": {
                        "tool_id": "other",
                        "tool_call_id": "call-1",
                        "values": {},
                    }
                },
            ),
            changed_step(
                complete(),
                2,
                result={
                    "tool_fact": {
                        "tool_id": "records.read",
                        "tool_call_id": "other",
                        "values": {},
                    }
                },
            ),
            changed_step(
                complete(), 1, observation_checkpoint=replace(reference(1), checksum="other")
            ),
            changed_step(complete(), 0, result_checkpoint=reference(1)),
            changed_step(
                complete(),
                2,
                result={"tool_call": {"status": "SUCCEEDED"}, "tool_failure": {"reason": "failed"}},
            ),
        )
        for index, trajectory in enumerate(cases):
            with self.subTest(index=index):
                self.assertEqual(
                    self.validator.validate(trajectory).quality, TrajectoryQuality.FAIL
                )

    def test_missing_inference_hash_query_and_checksum_are_partial(self) -> None:
        cases = (
            changed_step(complete(), 0, model_inference_id=None),
            changed_step(complete(), 0, model_response_hash=None),
            changed_step(complete(), 1, action={"action": "RETRIEVE", "query": None}),
            changed_step(
                complete(), 0, observation_checkpoint=replace(reference(1), checksum=None)
            ),
        )
        for index, trajectory in enumerate(cases):
            with self.subTest(index=index):
                self.assertEqual(
                    self.validator.validate(trajectory).quality, TrajectoryQuality.PARTIAL
                )

    def test_missing_retrieval_evidence_gap_is_not_a_real_empty_result(self) -> None:
        trajectory = changed_step(complete(), 1, gaps=("retrieval_evidence_missing",))
        self.assertEqual(self.validator.validate(trajectory).quality, TrajectoryQuality.PARTIAL)

    def test_unknown_gap_is_conservative_partial_not_substring_matched(self) -> None:
        trajectory = replace(complete(), gaps=("prefix_historical_metadata_unavailable_suffix",))
        report = self.validator.validate(trajectory)
        self.assertEqual(report.quality, TrajectoryQuality.PARTIAL)
        self.assertIn("PROJECTOR_GAP_UNKNOWN", [i.code for i in report.issues])

    def test_missing_start_metadata_is_nonblocking_if_core_bindings_are_complete(self) -> None:
        trajectory = replace(
            complete(), start_event_id=None, started_at=None, gaps=("run_start_event_missing",)
        )
        self.assertEqual(self.validator.validate(trajectory).quality, TrajectoryQuality.PASS)

    def test_readonly_deterministic_and_opaque_domain_payload(self) -> None:
        trajectory = changed_step(
            complete(),
            0,
            action={
                "action": "FINAL",
                "report": {
                    "DiagnosisReport": "opaque",
                    "EvidenceBundle": "opaque",
                    "asset_model": "opaque",
                },
            },
        )
        before = deepcopy(trajectory)
        first = self.validator.validate(trajectory)
        self.assertEqual(first, self.validator.validate(trajectory))
        self.assertEqual(trajectory, before)
        self.assertEqual(first.quality, TrajectoryQuality.PASS)
        self.assertFalse(hasattr(first, "training_eligible"))

    def test_validator_import_boundary(self) -> None:
        path = Path(__file__).resolve().parents[2] / (
            "src/industrial_ops_agent/agent/trajectory_validation.py"
        )
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        project_imports = [
            name for name in imports if name and name.startswith("industrial_ops_agent")
        ]
        self.assertEqual(project_imports, ["industrial_ops_agent.agent.trajectory"])

    def test_identity_only_tool_fact_is_not_an_execution_result(self) -> None:
        trajectory = changed_step(
            complete(),
            2,
            result={
                "tool_fact": {"tool_id": "records.read", "tool_call_id": "call-1"},
            },
        )
        self.assertEqual(self.validator.validate(trajectory).quality, TrajectoryQuality.PARTIAL)

    def test_every_current_projector_gap_has_an_exact_quality_rule(self) -> None:
        policies = {
            "run_start_event_missing": (None, TrajectoryQuality.PASS),
            "terminal_event_missing": (None, TrajectoryQuality.PASS),
            "model_started_event_missing": (0, TrajectoryQuality.PASS),
            "decision_observation_checkpoint_missing": (0, TrajectoryQuality.PASS),
            "decision_request_missing": (0, TrajectoryQuality.PASS),
            "model_inference_record_missing": (0, TrajectoryQuality.PARTIAL),
            "decision_action_missing": (0, TrajectoryQuality.PARTIAL),
            "retrieval_observation_checkpoint_missing": (1, TrajectoryQuality.PASS),
            "retrieval_query_missing": (1, TrajectoryQuality.PASS),
            "retrieval_result_checkpoint_missing": (1, TrajectoryQuality.PARTIAL),
            "retrieval_evidence_missing": (1, TrajectoryQuality.PARTIAL),
            "tool_observation_checkpoint_missing": (2, TrajectoryQuality.PASS),
            "tool_id_missing": (2, TrajectoryQuality.PASS),
            "tool_call_record_missing": (2, TrajectoryQuality.PARTIAL),
            "tool_result_checkpoint_missing": (2, TrajectoryQuality.PASS),
            "tool_result_missing": (2, TrajectoryQuality.PASS),
        }
        path = Path(__file__).resolve().parents[2] / "src/industrial_ops_agent/agent/trajectory.py"
        actual_gaps = {
            node.args[0].value
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "gaps"
            and node.func.attr == "append"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        }
        self.assertEqual(set(policies), actual_gaps)
        for gap, (index, quality) in policies.items():
            with self.subTest(gap=gap):
                trajectory = complete()
                trajectory = (
                    replace(trajectory, gaps=(gap,))
                    if index is None
                    else changed_step(trajectory, index, gaps=(gap,))
                )
                report = self.validator.validate(trajectory)
                self.assertEqual(report.quality, quality)
                self.assertNotIn("PROJECTOR_GAP_UNKNOWN", [issue.code for issue in report.issues])

    def test_model_and_retrieval_missing_result_are_partial(self) -> None:
        cases = (
            changed_step(
                complete(), 0, model_response_hash=None, result_checkpoint=None, result={}
            ),
            changed_step(complete(), 1, result={}, result_checkpoint=None),
        )
        for trajectory in cases:
            with self.subTest(kind=trajectory.steps[0].kind):
                self.assertEqual(
                    self.validator.validate(trajectory).quality, TrajectoryQuality.PARTIAL
                )

    def test_same_checkpoint_sequence_cannot_bind_different_records(self) -> None:
        trajectory = changed_step(
            complete(),
            1,
            observation_checkpoint=replace(
                reference(2),
                record_id="different-checkpoint",
                checksum="different-hash",
            ),
        )
        self.assertEqual(self.validator.validate(trajectory).quality, TrajectoryQuality.FAIL)

    def test_unsupported_human_intervention_label_is_not_guessed_from_status(self) -> None:
        trajectory = complete()
        trajectory = replace(
            trajectory,
            status="WAITING_EXPERT",
            terminal_outcome=replace(
                trajectory.terminal_outcome,
                status="WAITING_EXPERT",
                event_type="application.expert_takeover_requested",
            ),
        )
        report = self.validator.validate(trajectory)
        self.assertEqual(report.quality, TrajectoryQuality.FAIL)
        issue = next(i for i in report.issues if i.code == "TERMINAL_EVENT_UNSUPPORTED")
        self.assertEqual(issue.source_reference.record_id, "end")

    def test_persisted_records_project_then_validate_without_database_changes(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        database = Database.from_engine(engine)
        self.addCleanup(database.dispose)
        with Session(engine) as session:
            session.add(TenantRecord(id="tenant", status="active"))
            session.add(
                AgentRunRecord(
                    tenant_id="tenant",
                    agent_run_id="run",
                    status="COMPLETED",
                    budget={},
                    last_sequence=4,
                    version=4,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            for sequence, event_type, payload in (
                (1, "sample.graph_started", {}),
                (2, "sample.graph_node_started", {"node": "retrieve"}),
                (3, "sample.graph_node_completed", {"node": "retrieve", "evidence_count": 0}),
                (4, "sample.completed", {}),
            ):
                session.add(
                    AgentEventRecord(
                        tenant_id="tenant",
                        agent_run_id="run",
                        event_id=f"event-{sequence}",
                        sequence=sequence,
                        event_type=event_type,
                        payload=payload,
                        visibility="authorized",
                        occurred_at=NOW,
                        created_at=NOW,
                        updated_at=NOW,
                    )
                )
            for sequence, state in (
                (2, {"decision": {"action": "RETRIEVE", "query": "question"}}),
                (3, {"evidence": []}),
            ):
                session.add(
                    AgentCheckpointRecord(
                        tenant_id="tenant",
                        agent_run_id="run",
                        checkpoint_id=f"cp-{sequence}",
                        sequence=sequence,
                        graph_version="sample-v1",
                        state=state,
                        state_checksum="hash",
                        created_at=NOW,
                        updated_at=NOW,
                    )
                )
            session.commit()
        trajectory = TrajectoryProjector(database).project(
            TenantContext("tenant", "subject"), "run"
        )
        self.assertEqual(self.validator.validate(trajectory).quality, TrajectoryQuality.PASS)
        with Session(engine) as session:
            run = session.scalar(select(AgentRunRecord))
            self.assertEqual((run.status, run.version, run.last_sequence), ("COMPLETED", 4, 4))
            self.assertEqual(len(list(session.scalars(select(AgentEventRecord)))), 4)
            self.assertEqual(len(list(session.scalars(select(AgentCheckpointRecord)))), 2)
