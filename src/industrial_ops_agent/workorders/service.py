"""Role-checked optimistic WorkOrder state transitions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from industrial_ops_agent.auth.identity import IdentityContext
from industrial_ops_agent.auth.policy import Action, Authorizer, ResourceContext
from industrial_ops_agent.domain import as_utc as _utc
from industrial_ops_agent.maintenance_planning.review_isolation import (
    work_order_read_transaction,
)
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    AssetRecord,
    AssetSiteLinkRecord,
    CustomerServiceUpdateRecord,
    IncidentRecord,
    PartIssueRecord,
    PartMaterialMovementRecord,
    PartReservationRecord,
    WorkOrderCompletionRecord,
    WorkOrderControlRecord,
    WorkOrderEventRecord,
    WorkOrderFieldEntryRecord,
    WorkOrderRecord,
    WorkOrderReworkRecord,
    WorkOrderVerificationRecord,
)


class WorkOrderNotVisible(Exception):
    pass


class WorkOrderConflict(Exception):
    def __init__(self, reason: str, current_version: int | None = None) -> None:
        super().__init__(reason)
        self.reason, self.current_version = reason, current_version


@dataclass(frozen=True, slots=True)
class WorkOrderView:
    work_order_id: str
    incident_id: str
    proposal_id: str
    reservation_id: str | None
    creation_mode: Literal["PARTS_RESERVATION", "SERVICE_AUTHORIZATION"]
    authorization_type: Literal["COVERED_SERVICE"] | None
    diagnosis_run_id: str | None
    diagnosis_version: int | None
    initial_parts_required: bool
    part_issue_required: bool
    part_accounting_required: bool
    status: str
    assigned_subject_id: str | None
    pending_assignment_operation_id: str | None
    priority: str
    sla_due_at: datetime | None
    sla_status: str
    service_window_start: datetime | None
    service_window_end: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WorkOrderClosureFacts:
    completion_id: str
    verification_id: str


@dataclass(frozen=True, slots=True)
class DispatchQueueItem:
    work_order: WorkOrderView
    asset_id: str
    asset_display_name: str | None
    model_code: str | None
    site_id: str | None
    site_name: str | None
    incident_description: str


@dataclass(frozen=True, slots=True)
class WorkOrderControlView:
    control_id: str
    work_order_version: int
    command_type: str
    previous_status: str
    target_status: str
    reason: str
    recovery_condition: str | None
    responsible_subject_id: str | None
    service_window_start: datetime | None
    service_window_end: datetime | None
    sla_due_at: datetime | None
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class WorkOrderFieldEntryView:
    entry_id: str
    sequence: int
    client_operation_id: str
    entry_type: str
    payload: dict[str, Any]
    actor_subject_id: str
    occurred_at: datetime
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class WorkOrderPartAllocationView:
    reservation_id: str
    part_number: str
    approved_quantity: int
    status: str
    source: str
    source_record_id: str
    as_of: datetime
    issue_required: bool
    issue_status: str
    usage_enabled: bool
    legal_actions: list[str]
    part_issue_id: str | None
    proposal_id: str | None
    approval_id: str | None
    operation_id: str | None
    reconciliation_id: str | None
    external_issue_id: str | None
    issue_source: str | None
    issue_source_record_id: str | None
    issue_as_of: datetime | None


@dataclass(frozen=True, slots=True)
class WorkOrderPartAccountingEntryView:
    entry_id: str
    quantity: int
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class WorkOrderPartMovementView:
    movement_id: str
    operation_id: str
    proposal_id: str
    approval_id: str
    movement_kind: str
    field_entry_id: str | None
    quantity: int
    status: str
    external_movement_id: str | None
    source: str | None
    source_record_id: str | None
    as_of: datetime | None
    reconciliation_id: str | None
    reason: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WorkOrderPartAccountingView:
    mode: str
    work_order_id: str
    work_order_version: int
    reservation_id: str
    part_issue_id: str | None
    part_number: str
    issued_quantity: int
    recorded_usage_quantity: int
    consumed_quantity: int
    returned_quantity: int
    active_consumption_quantity: int
    active_return_quantity: int
    unaccounted_quantity: int
    returnable_quantity: int
    eligible_entries: list[WorkOrderPartAccountingEntryView]
    movements: list[WorkOrderPartMovementView]
    close_ready: bool
    blocking_reasons: list[str]
    legal_actions: list[str]


@dataclass(frozen=True, slots=True)
class WorkOrderRepairRoundView:
    round_number: int
    status: str
    completion_id: str | None
    completed_by_subject_id: str | None
    root_cause: str | None
    actions: list[str]
    evidence_ids: list[str]
    part_reservation_ids: list[str]
    cost_amount: str | None
    customer_confirmation: str | None
    field_entry_sequence_start: int | None
    field_entry_sequence_end: int | None
    completed_at: datetime | None
    verification_id: str | None
    verifier_subject_id: str | None
    verification_passed: bool | None
    verification_reason: str | None
    verified_at: datetime | None
    rework_id: str | None
    rework_status: str | None
    rework_reason: str | None
    entry_sequence_checkpoint: int | None
    rework_opened_at: datetime | None
    rework_resolved_at: datetime | None


@dataclass(frozen=True, slots=True)
class WorkOrderRepairHistoryView:
    work_order_id: str
    current_round: int
    rounds: list[WorkOrderRepairRoundView]


@dataclass(frozen=True, slots=True)
class WorkOrderClosurePartView:
    reservation_id: str
    part_number: str
    quantity: int
    status: str
    source: str
    as_of: datetime


@dataclass(frozen=True, slots=True)
class WorkOrderClosureReportView:
    report_contract_version: str
    closure_facts_digest: str
    work_order_id: str
    incident_id: str
    asset_id: str
    asset_display_name: str | None
    model_code: str | None
    serial_number: str | None
    site_id: str | None
    site_name: str | None
    closed_at: datetime
    closed_by_subject_id: str
    close_reason: str | None
    close_operation_id: str | None
    close_proposal_id: str | None
    repair_round_count: int
    rework_count: int
    completion_id: str
    completion_round_number: int
    completed_by_subject_id: str
    completed_at: datetime
    root_cause: str
    actions: list[str]
    evidence_ids: list[str]
    parts: list[WorkOrderClosurePartView]
    cost_amount: str | None
    field_customer_confirmation: str | None
    verification_id: str
    verifier_subject_id: str
    verification_reason: str
    verified_at: datetime
    customer_result_confirmation_id: str | None
    customer_result_accepted: bool
    customer_confirmed_by_subject_id: str | None
    customer_confirmed_at: datetime | None
    customer_satisfaction_rating: int | None


class WorkOrderService:
    def __init__(self, database: Database, authorizer: Authorizer) -> None:
        self._database, self._authorizer = database, authorizer

    def get(
        self, identity: IdentityContext, work_order_id: str, *, request_id: str
    ) -> WorkOrderView:
        with work_order_read_transaction(
            self._database,
            identity,
            work_order_id,
            request_id=request_id,
        ) as session:
            work, incident, site_id = self._load(session, identity.tenant_id, work_order_id)
            self._require(
                identity,
                Action.READ_WORK_ORDER,
                work_order_id,
                incident.asset_id,
                site_id,
                request_id,
            )
            return _view(work)

    def list_controls(
        self,
        identity: IdentityContext,
        work_order_id: str,
        *,
        request_id: str,
    ) -> list[WorkOrderControlView]:
        with work_order_read_transaction(
            self._database,
            identity,
            work_order_id,
            request_id=request_id,
        ) as session:
            _work, incident, site_id = self._load(session, identity.tenant_id, work_order_id)
            self._require(
                identity,
                Action.READ_WORK_ORDER,
                work_order_id,
                incident.asset_id,
                site_id,
                request_id,
            )
            records = session.scalars(
                select(WorkOrderControlRecord)
                .where(
                    WorkOrderControlRecord.tenant_id == identity.tenant_id,
                    WorkOrderControlRecord.work_order_id == work_order_id,
                )
                .order_by(WorkOrderControlRecord.work_order_version)
            )
            return [_control_view(record) for record in records]

    def get_part_allocation(
        self,
        identity: IdentityContext,
        work_order_id: str,
        *,
        request_id: str,
    ) -> WorkOrderPartAllocationView:
        with work_order_read_transaction(
            self._database,
            identity,
            work_order_id,
            request_id=request_id,
        ) as session:
            work, incident, site_id = self._load(
                session,
                identity.tenant_id,
                work_order_id,
            )
            self._require(
                identity,
                Action.READ_WORK_ORDER,
                work_order_id,
                incident.asset_id,
                site_id,
                request_id,
            )
            if work.assigned_subject_id != identity.subject_id:
                raise WorkOrderConflict("assignee_mismatch", work.version)
            if work.creation_mode == "SERVICE_AUTHORIZATION":
                raise WorkOrderConflict("parts_not_required", work.version)
            reservation = self._load_available_part_allocation(session, work)
            issue = session.scalar(
                select(PartIssueRecord).where(
                    PartIssueRecord.tenant_id == work.tenant_id,
                    PartIssueRecord.work_order_id == work.work_order_id,
                )
            )
            if not work.part_issue_required:
                issue_status = "LEGACY_COMPATIBLE"
                usage_enabled = True
                legal_actions: list[str] = []
            elif issue is None:
                issue_status = "NOT_REQUESTED"
                usage_enabled = False
                legal_actions = (
                    ["PROPOSE_ISSUE"]
                    if work.status in {"ACCEPTED", "IN_PROGRESS", "ON_HOLD"}
                    and reservation.status == "RESERVED"
                    else []
                )
            else:
                issue_status = issue.status
                usage_enabled = issue.status == "ISSUED" and reservation.status == "ISSUED"
                legal_actions = []
            return WorkOrderPartAllocationView(
                reservation_id=reservation.reservation_id,
                part_number=reservation.part_number,
                approved_quantity=reservation.quantity,
                status=reservation.status,
                source=reservation.source,
                source_record_id=reservation.source_record_id,
                as_of=_utc(reservation.as_of),
                issue_required=work.part_issue_required,
                issue_status=issue_status,
                usage_enabled=usage_enabled,
                legal_actions=legal_actions,
                part_issue_id=issue.part_issue_id if issue is not None else None,
                proposal_id=issue.proposal_id if issue is not None else None,
                approval_id=issue.approval_id if issue is not None else None,
                operation_id=issue.operation_id if issue is not None else None,
                reconciliation_id=issue.reconciliation_id if issue is not None else None,
                external_issue_id=issue.external_issue_id if issue is not None else None,
                issue_source=issue.source if issue is not None else None,
                issue_source_record_id=issue.source_record_id if issue is not None else None,
                issue_as_of=(
                    _utc(issue.as_of) if issue is not None and issue.as_of is not None else None
                ),
            )

    def get_part_accounting(
        self,
        identity: IdentityContext,
        work_order_id: str,
        *,
        request_id: str,
    ) -> WorkOrderPartAccountingView:
        """Return the server-authoritative issue/usage/consumption/return ledger."""

        with work_order_read_transaction(
            self._database,
            identity,
            work_order_id,
            request_id=request_id,
        ) as session:
            work, incident, site_id = self._load(
                session,
                identity.tenant_id,
                work_order_id,
            )
            self._require(
                identity,
                Action.READ_WORK_ORDER,
                work_order_id,
                incident.asset_id,
                site_id,
                request_id,
            )
            if work.assigned_subject_id != identity.subject_id:
                raise WorkOrderConflict("assignee_mismatch", work.version)
            return self.part_accounting_in_session(session, work)

    @classmethod
    def part_accounting_in_session(
        cls,
        session: Session,
        work: WorkOrderRecord,
    ) -> WorkOrderPartAccountingView:
        if work.creation_mode == "SERVICE_AUTHORIZATION":
            raise WorkOrderConflict("parts_not_required", work.version)
        reservation = cls._load_available_part_allocation(session, work)
        issue = session.scalar(
            select(PartIssueRecord).where(
                PartIssueRecord.tenant_id == work.tenant_id,
                PartIssueRecord.work_order_id == work.work_order_id,
                PartIssueRecord.reservation_id == reservation.reservation_id,
            )
        )
        if not work.part_accounting_required:
            return WorkOrderPartAccountingView(
                mode="LEGACY_ACCOUNTING_COMPATIBLE",
                work_order_id=work.work_order_id,
                work_order_version=work.version,
                reservation_id=reservation.reservation_id,
                part_issue_id=issue.part_issue_id if issue is not None else None,
                part_number=reservation.part_number,
                issued_quantity=(
                    issue.quantity
                    if issue is not None and issue.status == "ISSUED"
                    else reservation.quantity
                ),
                recorded_usage_quantity=0,
                consumed_quantity=0,
                returned_quantity=0,
                active_consumption_quantity=0,
                active_return_quantity=0,
                unaccounted_quantity=0,
                returnable_quantity=0,
                eligible_entries=[],
                movements=[],
                close_ready=True,
                blocking_reasons=[],
                legal_actions=[],
            )
        if (
            issue is None
            or issue.status != "ISSUED"
            or reservation.status != "ISSUED"
            or issue.quantity != reservation.quantity
            or issue.part_number != reservation.part_number
        ):
            raise WorkOrderConflict("part_issue_not_issued", work.version)

        entries = list(
            session.scalars(
                select(WorkOrderFieldEntryRecord)
                .where(
                    WorkOrderFieldEntryRecord.tenant_id == work.tenant_id,
                    WorkOrderFieldEntryRecord.work_order_id == work.work_order_id,
                    WorkOrderFieldEntryRecord.entry_type == "PART",
                )
                .order_by(WorkOrderFieldEntryRecord.sequence)
            )
        )
        movements = list(
            session.scalars(
                select(PartMaterialMovementRecord)
                .where(
                    PartMaterialMovementRecord.tenant_id == work.tenant_id,
                    PartMaterialMovementRecord.work_order_id == work.work_order_id,
                    PartMaterialMovementRecord.part_issue_id == issue.part_issue_id,
                )
                .order_by(PartMaterialMovementRecord.created_at)
            )
        )
        active_statuses = {"PENDING_APPROVAL", "APPROVED", "RECONCILING"}
        recorded_usage = sum(cls._part_entry_quantity(item, work.version) for item in entries)
        consumed = sum(
            item.quantity
            for item in movements
            if item.movement_kind == "CONSUME" and item.status == "APPLIED"
        )
        returned = sum(
            item.quantity
            for item in movements
            if item.movement_kind == "RETURN" and item.status == "APPLIED"
        )
        active_consumption = sum(
            item.quantity
            for item in movements
            if item.movement_kind == "CONSUME" and item.status in active_statuses
        )
        active_return = sum(
            item.quantity
            for item in movements
            if item.movement_kind == "RETURN" and item.status in active_statuses
        )
        occupied_entries = {
            item.field_entry_id
            for item in movements
            if (
                item.movement_kind == "CONSUME"
                and item.field_entry_id is not None
                and item.status in active_statuses | {"APPLIED"}
            )
        }
        eligible = [
            WorkOrderPartAccountingEntryView(
                entry_id=item.entry_id,
                quantity=cls._part_entry_quantity(item, work.version),
                occurred_at=_utc(item.occurred_at),
            )
            for item in entries
            if item.entry_id not in occupied_entries
        ]
        in_progress = any(item.status in active_statuses for item in movements)
        unconsumed = any(
            not any(
                movement.movement_kind == "CONSUME"
                and movement.field_entry_id == entry.entry_id
                and movement.status == "APPLIED"
                for movement in movements
            )
            for entry in entries
        )
        balance = issue.quantity - consumed - returned
        unaccounted = max(balance, 0)
        blocking_reasons: list[str] = []
        if unconsumed:
            blocking_reasons.append("unconsumed_field_entries")
        if balance != 0:
            blocking_reasons.append("unaccounted_issued_quantity")
        if in_progress:
            blocking_reasons.append("part_movement_in_progress")
        legal_actions: list[str] = []
        if work.status in {"ACCEPTED", "IN_PROGRESS", "ON_HOLD"}:
            if eligible:
                legal_actions.append("PROPOSE_CONSUMPTION")
            if issue.quantity - recorded_usage - returned - active_return > 0:
                legal_actions.append("PROPOSE_RETURN")
        return WorkOrderPartAccountingView(
            mode="AUTHORITATIVE",
            work_order_id=work.work_order_id,
            work_order_version=work.version,
            reservation_id=reservation.reservation_id,
            part_issue_id=issue.part_issue_id,
            part_number=issue.part_number,
            issued_quantity=issue.quantity,
            recorded_usage_quantity=recorded_usage,
            consumed_quantity=consumed,
            returned_quantity=returned,
            active_consumption_quantity=active_consumption,
            active_return_quantity=active_return,
            unaccounted_quantity=unaccounted,
            returnable_quantity=max(
                issue.quantity - recorded_usage - returned - active_return,
                0,
            ),
            eligible_entries=eligible,
            movements=[cls._part_movement_view(item) for item in movements],
            close_ready=not blocking_reasons,
            blocking_reasons=blocking_reasons,
            legal_actions=legal_actions,
        )

    @staticmethod
    def _part_entry_quantity(
        entry: WorkOrderFieldEntryRecord,
        current_version: int,
    ) -> int:
        quantity = entry.payload.get("quantity")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise WorkOrderConflict("part_entry_quantity_invalid", current_version)
        return quantity

    @staticmethod
    def _part_movement_view(
        item: PartMaterialMovementRecord,
    ) -> WorkOrderPartMovementView:
        return WorkOrderPartMovementView(
            movement_id=item.movement_id,
            operation_id=item.operation_id,
            proposal_id=item.proposal_id,
            approval_id=item.approval_id,
            movement_kind=item.movement_kind,
            field_entry_id=item.field_entry_id,
            quantity=item.quantity,
            status=item.status,
            external_movement_id=item.external_movement_id,
            source=item.source,
            source_record_id=item.source_record_id,
            as_of=_utc(item.as_of) if item.as_of is not None else None,
            reconciliation_id=item.reconciliation_id,
            reason=item.reason,
            created_at=_utc(item.created_at),
            updated_at=_utc(item.updated_at),
        )

    @staticmethod
    def _load_available_part_allocation(
        session: Session,
        work: WorkOrderRecord,
    ) -> PartReservationRecord:
        reservation = session.scalar(
            select(PartReservationRecord).where(
                PartReservationRecord.tenant_id == work.tenant_id,
                PartReservationRecord.reservation_id == work.reservation_id,
            )
        )
        if (
            reservation is None
            or reservation.incident_id != work.incident_id
            or reservation.status not in {"RESERVED", "ISSUED"}
        ):
            raise WorkOrderConflict("part_allocation_unavailable", work.version)
        return reservation

    def repair_history(
        self,
        identity: IdentityContext,
        work_order_id: str,
        *,
        request_id: str,
    ) -> WorkOrderRepairHistoryView:
        """Project immutable completion, verification, and rework facts by round."""

        with work_order_read_transaction(
            self._database,
            identity,
            work_order_id,
            request_id=request_id,
        ) as session:
            _work, incident, site_id = self._load(
                session,
                identity.tenant_id,
                work_order_id,
            )
            self._require(
                identity,
                Action.READ_WORK_ORDER,
                work_order_id,
                incident.asset_id,
                site_id,
                request_id,
            )
            completions = list(
                session.scalars(
                    select(WorkOrderCompletionRecord)
                    .where(
                        WorkOrderCompletionRecord.tenant_id == identity.tenant_id,
                        WorkOrderCompletionRecord.work_order_id == work_order_id,
                    )
                    .order_by(WorkOrderCompletionRecord.round_number)
                )
            )
            verifications = list(
                session.scalars(
                    select(WorkOrderVerificationRecord)
                    .where(
                        WorkOrderVerificationRecord.tenant_id == identity.tenant_id,
                        WorkOrderVerificationRecord.work_order_id == work_order_id,
                    )
                    .order_by(WorkOrderVerificationRecord.round_number)
                )
            )
            reworks = list(
                session.scalars(
                    select(WorkOrderReworkRecord)
                    .where(
                        WorkOrderReworkRecord.tenant_id == identity.tenant_id,
                        WorkOrderReworkRecord.work_order_id == work_order_id,
                    )
                    .order_by(WorkOrderReworkRecord.round_number)
                )
            )
            completion_by_round = {item.round_number: item for item in completions}
            verification_by_round = {item.round_number: item for item in verifications}
            rework_by_round = {item.round_number: item for item in reworks}
            current_round = max([1, *completion_by_round.keys(), *rework_by_round.keys()])
            rounds: list[WorkOrderRepairRoundView] = []
            for round_number in range(1, current_round + 1):
                completion = completion_by_round.get(round_number)
                verification = verification_by_round.get(round_number)
                rework = rework_by_round.get(round_number)
                if completion is None:
                    status = "REWORK_IN_PROGRESS" if rework is not None else "IN_PROGRESS"
                elif verification is None:
                    status = "AWAITING_VERIFICATION"
                elif verification.passed:
                    status = "VERIFIED"
                else:
                    status = "REWORK_REQUIRED"
                rounds.append(
                    WorkOrderRepairRoundView(
                        round_number=round_number,
                        status=status,
                        completion_id=(completion.completion_id if completion else None),
                        completed_by_subject_id=(
                            completion.completed_by_subject_id if completion else None
                        ),
                        root_cause=(completion.root_cause if completion else None),
                        actions=(completion.actions if completion else []),
                        evidence_ids=(completion.evidence_ids if completion else []),
                        part_reservation_ids=(
                            completion.part_reservation_ids if completion else []
                        ),
                        cost_amount=(completion.cost_amount if completion else None),
                        customer_confirmation=(
                            completion.customer_confirmation if completion else None
                        ),
                        field_entry_sequence_start=(
                            completion.field_entry_sequence_start if completion else None
                        ),
                        field_entry_sequence_end=(
                            completion.field_entry_sequence_end if completion else None
                        ),
                        completed_at=(completion.completed_at if completion else None),
                        verification_id=(verification.verification_id if verification else None),
                        verifier_subject_id=(
                            verification.verifier_subject_id if verification else None
                        ),
                        verification_passed=(verification.passed if verification else None),
                        verification_reason=(verification.reason if verification else None),
                        verified_at=(verification.verified_at if verification else None),
                        rework_id=(rework.rework_id if rework else None),
                        rework_status=(rework.status if rework else None),
                        rework_reason=(rework.reason if rework else None),
                        entry_sequence_checkpoint=(
                            rework.entry_sequence_checkpoint if rework else None
                        ),
                        rework_opened_at=(rework.opened_at if rework else None),
                        rework_resolved_at=(rework.resolved_at if rework else None),
                    )
                )
            return WorkOrderRepairHistoryView(
                work_order_id=work_order_id,
                current_round=current_round,
                rounds=rounds,
            )

    def closure_report(
        self,
        identity: IdentityContext,
        work_order_id: str,
        *,
        request_id: str,
    ) -> WorkOrderClosureReportView:
        """Project the immutable facts accepted by the final close transition."""

        with work_order_read_transaction(
            self._database,
            identity,
            work_order_id,
            request_id=request_id,
        ) as session:
            work, incident, site_id = self._load(
                session,
                identity.tenant_id,
                work_order_id,
            )
            self._require(
                identity,
                Action.READ_WORK_ORDER,
                work_order_id,
                incident.asset_id,
                site_id,
                request_id,
            )
            if work.status != "CLOSED":
                raise WorkOrderConflict("closure_report_not_ready", work.version)
            asset = session.scalar(
                select(AssetRecord).where(
                    AssetRecord.tenant_id == identity.tenant_id,
                    AssetRecord.asset_id == incident.asset_id,
                )
            )
            site = session.scalar(
                select(AssetSiteLinkRecord).where(
                    AssetSiteLinkRecord.tenant_id == identity.tenant_id,
                    AssetSiteLinkRecord.asset_id == incident.asset_id,
                )
            )
            close_event = session.scalar(
                select(WorkOrderEventRecord).where(
                    WorkOrderEventRecord.tenant_id == identity.tenant_id,
                    WorkOrderEventRecord.work_order_id == work_order_id,
                    WorkOrderEventRecord.event_type == "work_order.closed",
                )
            )
            completion = session.scalar(
                select(WorkOrderCompletionRecord)
                .where(
                    WorkOrderCompletionRecord.tenant_id == identity.tenant_id,
                    WorkOrderCompletionRecord.work_order_id == work_order_id,
                )
                .order_by(WorkOrderCompletionRecord.round_number.desc())
            )
            verification = (
                session.scalar(
                    select(WorkOrderVerificationRecord).where(
                        WorkOrderVerificationRecord.tenant_id == identity.tenant_id,
                        WorkOrderVerificationRecord.completion_id == completion.completion_id,
                        WorkOrderVerificationRecord.passed.is_(True),
                    )
                )
                if completion is not None
                else None
            )
            customer_confirmation = session.scalar(
                select(CustomerServiceUpdateRecord)
                .where(
                    CustomerServiceUpdateRecord.tenant_id == identity.tenant_id,
                    CustomerServiceUpdateRecord.work_order_id == work_order_id,
                    CustomerServiceUpdateRecord.update_type == "RESULT_CONFIRMATION",
                    CustomerServiceUpdateRecord.result_accepted.is_(True),
                )
                .order_by(
                    CustomerServiceUpdateRecord.occurred_at.desc(),
                    CustomerServiceUpdateRecord.created_at.desc(),
                )
            )
            if asset is None or close_event is None or completion is None or verification is None:
                raise WorkOrderConflict("closure_report_facts_incomplete", work.version)
            part_records = list(
                session.scalars(
                    select(PartReservationRecord)
                    .where(
                        PartReservationRecord.tenant_id == identity.tenant_id,
                        PartReservationRecord.reservation_id.in_(completion.part_reservation_ids),
                    )
                    .order_by(PartReservationRecord.reservation_id)
                )
            )
            if len(part_records) != len(set(completion.part_reservation_ids)):
                raise WorkOrderConflict("closure_report_facts_incomplete", work.version)
            customer_result_accepted = customer_confirmation is not None or bool(
                completion.customer_confirmation
            )
            if not customer_result_accepted:
                raise WorkOrderConflict("closure_report_facts_incomplete", work.version)
            parts = [
                WorkOrderClosurePartView(
                    reservation_id=item.reservation_id,
                    part_number=item.part_number,
                    quantity=item.quantity,
                    status=item.status,
                    source=item.source,
                    as_of=_utc(item.as_of),
                )
                for item in part_records
            ]
            close_reason = _optional_payload_text(close_event.payload, "reason")
            close_operation_id = _optional_payload_text(
                close_event.payload,
                "operation_id",
            )
            close_proposal_id = _optional_payload_text(
                close_event.payload,
                "proposal_id",
            )
            repair_round_count = int(
                session.scalar(
                    select(func.count(WorkOrderCompletionRecord.completion_id)).where(
                        WorkOrderCompletionRecord.tenant_id == identity.tenant_id,
                        WorkOrderCompletionRecord.work_order_id == work_order_id,
                    )
                )
                or 0
            )
            rework_count = int(
                session.scalar(
                    select(func.count(WorkOrderReworkRecord.rework_id)).where(
                        WorkOrderReworkRecord.tenant_id == identity.tenant_id,
                        WorkOrderReworkRecord.work_order_id == work_order_id,
                    )
                )
                or 0
            )
            digest_values: dict[str, Any] = {
                "work_order_id": work_order_id,
                "incident_id": incident.incident_id,
                "asset_id": incident.asset_id,
                "closed_at": _utc(close_event.occurred_at),
                "closed_by_subject_id": close_event.actor_subject_id,
                "close_reason": close_reason,
                "close_operation_id": close_operation_id,
                "close_proposal_id": close_proposal_id,
                "repair_round_count": repair_round_count,
                "rework_count": rework_count,
                "completion_id": completion.completion_id,
                "completion_round_number": completion.round_number,
                "completed_by_subject_id": completion.completed_by_subject_id,
                "completed_at": _utc(completion.completed_at),
                "root_cause": completion.root_cause,
                "actions": completion.actions,
                "evidence_ids": completion.evidence_ids,
                "parts": [
                    {
                        "reservation_id": item.reservation_id,
                        "part_number": item.part_number,
                        "quantity": item.quantity,
                        "status": item.status,
                        "source": item.source,
                        "as_of": item.as_of,
                    }
                    for item in parts
                ],
                "cost_amount": completion.cost_amount,
                "field_customer_confirmation": completion.customer_confirmation,
                "verification_id": verification.verification_id,
                "verifier_subject_id": verification.verifier_subject_id,
                "verification_reason": verification.reason,
                "verified_at": _utc(verification.verified_at),
                "customer_result_confirmation_id": (
                    customer_confirmation.update_id if customer_confirmation else None
                ),
                "customer_result_accepted": customer_result_accepted,
                "customer_confirmed_by_subject_id": (
                    customer_confirmation.actor_subject_id if customer_confirmation else None
                ),
                "customer_confirmed_at": (
                    _utc(customer_confirmation.occurred_at) if customer_confirmation else None
                ),
                "customer_satisfaction_rating": (
                    customer_confirmation.satisfaction_rating if customer_confirmation else None
                ),
            }
            return WorkOrderClosureReportView(
                report_contract_version="work-order-closure-report/v1",
                closure_facts_digest=_closure_report_digest(digest_values),
                work_order_id=work_order_id,
                incident_id=incident.incident_id,
                asset_id=incident.asset_id,
                asset_display_name=asset.display_name,
                model_code=asset.model_code,
                serial_number=asset.serial_number,
                site_id=site.site_id if site else None,
                site_name=site.site_name if site else None,
                closed_at=_utc(close_event.occurred_at),
                closed_by_subject_id=close_event.actor_subject_id,
                close_reason=close_reason,
                close_operation_id=close_operation_id,
                close_proposal_id=close_proposal_id,
                repair_round_count=repair_round_count,
                rework_count=rework_count,
                completion_id=completion.completion_id,
                completion_round_number=completion.round_number,
                completed_by_subject_id=completion.completed_by_subject_id,
                completed_at=_utc(completion.completed_at),
                root_cause=completion.root_cause,
                actions=completion.actions,
                evidence_ids=completion.evidence_ids,
                parts=parts,
                cost_amount=completion.cost_amount,
                field_customer_confirmation=completion.customer_confirmation,
                verification_id=verification.verification_id,
                verifier_subject_id=verification.verifier_subject_id,
                verification_reason=verification.reason,
                verified_at=_utc(verification.verified_at),
                customer_result_confirmation_id=(
                    customer_confirmation.update_id if customer_confirmation else None
                ),
                customer_result_accepted=customer_result_accepted,
                customer_confirmed_by_subject_id=(
                    customer_confirmation.actor_subject_id if customer_confirmation else None
                ),
                customer_confirmed_at=(
                    _utc(customer_confirmation.occurred_at) if customer_confirmation else None
                ),
                customer_satisfaction_rating=(
                    customer_confirmation.satisfaction_rating if customer_confirmation else None
                ),
            )

    @classmethod
    def _validate_part_entry(
        cls,
        session: Session,
        work: WorkOrderRecord,
        payload: dict[str, Any],
    ) -> None:
        reservation = cls._load_available_part_allocation(session, work)
        if work.part_issue_required:
            issue = session.scalar(
                select(PartIssueRecord).where(
                    PartIssueRecord.tenant_id == work.tenant_id,
                    PartIssueRecord.work_order_id == work.work_order_id,
                    PartIssueRecord.reservation_id == reservation.reservation_id,
                )
            )
            if issue is None or issue.status != "ISSUED" or reservation.status != "ISSUED":
                raise WorkOrderConflict("part_issue_required", work.version)
        if (
            payload.get("part_reservation_id") != reservation.reservation_id
            or payload.get("part_number") != reservation.part_number
        ):
            raise WorkOrderConflict("part_allocation_mismatch", work.version)
        quantity = payload.get("quantity")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise WorkOrderConflict("part_allocation_mismatch", work.version)
        if quantity > reservation.quantity:
            raise WorkOrderConflict("part_quantity_exceeds_allocation", work.version)
        if work.part_accounting_required:
            issue = session.scalar(
                select(PartIssueRecord).where(
                    PartIssueRecord.tenant_id == work.tenant_id,
                    PartIssueRecord.work_order_id == work.work_order_id,
                    PartIssueRecord.reservation_id == reservation.reservation_id,
                )
            )
            if issue is None or issue.status != "ISSUED" or reservation.status != "ISSUED":
                raise WorkOrderConflict("part_issue_not_issued", work.version)
            existing_usage = sum(
                cls._part_entry_quantity(entry, work.version)
                for entry in session.scalars(
                    select(WorkOrderFieldEntryRecord).where(
                        WorkOrderFieldEntryRecord.tenant_id == work.tenant_id,
                        WorkOrderFieldEntryRecord.work_order_id == work.work_order_id,
                        WorkOrderFieldEntryRecord.entry_type == "PART",
                    )
                )
            )
            occupied_return = int(
                session.scalar(
                    select(func.coalesce(func.sum(PartMaterialMovementRecord.quantity), 0)).where(
                        PartMaterialMovementRecord.tenant_id == work.tenant_id,
                        PartMaterialMovementRecord.work_order_id == work.work_order_id,
                        PartMaterialMovementRecord.part_issue_id == issue.part_issue_id,
                        PartMaterialMovementRecord.movement_kind == "RETURN",
                        PartMaterialMovementRecord.status.in_(
                            {"PENDING_APPROVAL", "APPROVED", "RECONCILING", "APPLIED"}
                        ),
                    )
                )
                or 0
            )
            if existing_usage + quantity + occupied_return > issue.quantity:
                raise WorkOrderConflict("part_accounting_capacity_exceeded", work.version)

    def _require(
        self,
        identity: IdentityContext,
        action: Action,
        resource_id: str,
        asset_id: str,
        site_id: str | None,
        request_id: str,
    ) -> None:
        if asset_id in identity.asset_ids:
            resource = ResourceContext(identity.tenant_id, resource_id, asset_id=asset_id)
        elif site_id is not None and site_id in identity.site_ids:
            resource = ResourceContext(identity.tenant_id, resource_id, site_id=site_id)
        else:
            resource = ResourceContext(identity.tenant_id, resource_id, asset_id=asset_id)
        self._authorizer.require(
            identity,
            action,
            resource,
            request_id=request_id,
        )

    @staticmethod
    def _load(
        session: Session,
        tenant_id: str,
        work_order_id: str,
        *,
        for_update: bool = False,
    ) -> tuple[WorkOrderRecord, IncidentRecord, str | None]:
        statement = (
            select(WorkOrderRecord, IncidentRecord, AssetSiteLinkRecord.site_id)
            .join(IncidentRecord, IncidentRecord.incident_id == WorkOrderRecord.incident_id)
            .outerjoin(
                AssetSiteLinkRecord,
                AssetSiteLinkRecord.asset_id == IncidentRecord.asset_id,
            )
            .where(
                WorkOrderRecord.tenant_id == tenant_id,
                IncidentRecord.tenant_id == tenant_id,
                WorkOrderRecord.work_order_id == work_order_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(of=(WorkOrderRecord, IncidentRecord))
        row = session.execute(statement).tuples().one_or_none()
        if row is None:
            raise WorkOrderNotVisible
        return row


def _view(record: WorkOrderRecord) -> WorkOrderView:
    return WorkOrderView(
        work_order_id=record.work_order_id,
        incident_id=record.incident_id,
        proposal_id=record.proposal_id,
        reservation_id=record.reservation_id,
        creation_mode=record.creation_mode,  # type: ignore[arg-type]
        authorization_type=record.authorization_type,  # type: ignore[arg-type]
        diagnosis_run_id=record.diagnosis_run_id,
        diagnosis_version=record.diagnosis_version,
        initial_parts_required=record.creation_mode == "PARTS_RESERVATION",
        part_issue_required=record.part_issue_required,
        part_accounting_required=record.part_accounting_required,
        status=record.status,
        assigned_subject_id=record.assigned_subject_id,
        pending_assignment_operation_id=record.pending_assignment_operation_id,
        priority=record.priority,
        sla_due_at=_utc(record.sla_due_at) if record.sla_due_at is not None else None,
        sla_status=_sla_status(record),
        service_window_start=(
            _utc(record.service_window_start) if record.service_window_start is not None else None
        ),
        service_window_end=(
            _utc(record.service_window_end) if record.service_window_end is not None else None
        ),
        version=record.version,
        created_at=_utc(record.created_at),
        updated_at=_utc(record.updated_at),
    )


def _control_view(record: WorkOrderControlRecord) -> WorkOrderControlView:
    return WorkOrderControlView(
        control_id=record.control_id,
        work_order_version=record.work_order_version,
        command_type=record.command_type,
        previous_status=record.previous_status,
        target_status=record.target_status,
        reason=record.reason,
        recovery_condition=record.recovery_condition,
        responsible_subject_id=record.responsible_subject_id,
        service_window_start=(
            _utc(record.service_window_start) if record.service_window_start is not None else None
        ),
        service_window_end=(
            _utc(record.service_window_end) if record.service_window_end is not None else None
        ),
        sla_due_at=_utc(record.sla_due_at) if record.sla_due_at is not None else None,
        occurred_at=_utc(record.occurred_at),
    )


def _field_entry_view(record: WorkOrderFieldEntryRecord) -> WorkOrderFieldEntryView:
    return WorkOrderFieldEntryView(
        entry_id=record.entry_id,
        sequence=record.sequence,
        client_operation_id=record.client_operation_id,
        entry_type=record.entry_type,
        payload=record.payload,
        actor_subject_id=record.actor_subject_id,
        occurred_at=_utc(record.occurred_at),
        recorded_at=_utc(record.created_at),
    )


def _optional_payload_text(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    return value if isinstance(value, str) and value else None


def _closure_report_digest(values: dict[str, Any]) -> str:
    canonical = json.dumps(
        values,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_closure_report_json_default,
    ).encode("utf-8")
    return f"sha256:{sha256(canonical).hexdigest()}"


def _closure_report_json_default(value: object) -> str:
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    raise TypeError(f"closure report value is not serializable: {type(value).__name__}")


def _validate_service_window(
    service_window_start: datetime,
    service_window_end: datetime,
    sla_due_at: datetime,
) -> None:
    start = _utc(service_window_start)
    end = _utc(service_window_end)
    due = _utc(sla_due_at)
    if start >= end:
        raise WorkOrderConflict("service_window_invalid")
    if end > due:
        raise WorkOrderConflict("service_window_exceeds_sla")


def _sla_status(record: WorkOrderRecord) -> str:
    if record.sla_due_at is None:
        return "UNPLANNED"
    due = _utc(record.sla_due_at)
    if record.status in {"COMPLETED", "VERIFIED", "CLOSED"}:
        return "MET" if _utc(record.updated_at) <= due else "BREACHED"
    remaining_seconds = (due - datetime.now(UTC)).total_seconds()
    if remaining_seconds < 0:
        return "BREACHED"
    if remaining_seconds <= 2 * 60 * 60:
        return "AT_RISK"
    return "ON_TRACK"
