"""Persist governed transcript segments and promote confirmed text to Agent input events."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import select

from industrial_ops_agent.application.assets import ResourceNotVisible
from industrial_ops_agent.auth.errors import AuthorizationDenied
from industrial_ops_agent.auth.identity import IdentityContext
from industrial_ops_agent.auth.policy import Action, Authorizer, ResourceContext
from industrial_ops_agent.guardrails.prompt_injection import PromptInjectionGuard
from industrial_ops_agent.model_gateway.service import ModelGatewayError
from industrial_ops_agent.multimodal.transcription import (
    TranscriptionGateway,
    TranscriptionRequest,
)
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    AgentEventRecord,
    AgentRunRecord,
    DiagnosisRunRecord,
    RealtimeTranscriptSegmentRecord,
)
from industrial_ops_agent.persistence.tenant import TenantContext, validate_boundary_identifier


class RealtimeSessionError(RuntimeError):
    """A transcript stream or confirmation transition violated its contract."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class RealtimeTranscriptSegment:
    segment_id: str
    session_id: str
    sequence: int
    start_ms: int
    end_ms: int
    text: str
    confirmed_text: str | None
    confidence: float
    language: str
    entities: tuple[dict[str, object], ...]
    resolved_release_id: str
    manifest_hash: str
    status: str
    agent_event_id: str | None
    agent_event_sequence: int | None
    security_policy_version: str | None
    security_findings: tuple[dict[str, str], ...]
    version: int


class RealtimeTranscriptService:
    """Generic ASR validation, human confirmation, and Agent-event promotion."""

    def __init__(
        self,
        database: Database,
        authorizer: Authorizer,
        gateway: TranscriptionGateway,
        *,
        model_alias: str,
        timeout_seconds: float,
        hotwords: tuple[str, ...] = (),
        prompt_injection_guard: PromptInjectionGuard | None = None,
    ) -> None:
        self._database = database
        self._authorizer = authorizer
        self._gateway = gateway
        self._model_alias = model_alias
        self._timeout_seconds = timeout_seconds
        self._hotwords = tuple(hotwords)
        self._prompt_injection_guard = prompt_injection_guard or PromptInjectionGuard()

    async def transcribe(
        self,
        identity: IdentityContext,
        stream_id: str,
        *,
        diagnosis_run_id: str | None,
        segment_id: str,
        sequence: int,
        start_ms: int,
        end_ms: int,
        audio_wav: bytes,
        request_id: str,
    ) -> RealtimeTranscriptSegment:
        validate_boundary_identifier(stream_id, field="stream_id")
        validate_boundary_identifier(segment_id, field="segment_id")
        if sequence < 1 or start_ms < 0 or end_ms <= start_ms:
            raise RealtimeSessionError("realtime_segment_timeline_invalid")
        if diagnosis_run_id is not None:
            validate_boundary_identifier(diagnosis_run_id, field="diagnosis_run_id")
        now = datetime.now(UTC)
        audio_hash = sha256(audio_wav).hexdigest()
        existing = await asyncio.to_thread(
            self._find_existing,
            identity.tenant_context,
            stream_id,
            segment_id,
            sequence,
            start_ms,
            end_ms,
            audio_hash,
        )
        if existing is not None:
            return existing
        inference_id = "asr-" + sha256(
            f"{identity.tenant_id}\0{stream_id}\0{segment_id}".encode()
        ).hexdigest()
        result = await self._gateway.transcribe(
            TenantContext(identity.tenant_id, identity.subject_id),
            TranscriptionRequest(
                inference_request_id=inference_id,
                model_alias=self._model_alias,
                session_id=stream_id,
                segment_id=segment_id,
                subject_id=identity.subject_id,
                trace_id=request_id,
                audio_wav=audio_wav,
                language="zh",
                hotwords=self._hotwords,
                deadline=now + timedelta(seconds=self._timeout_seconds),
                hotword_profile_id="generic-transcription-v1",
            ),
        )
        if abs((end_ms - start_ms) - round(result.duration_seconds * 1_000)) > 1_500:
            raise ModelGatewayError("asr_segment_timeline_mismatch")
        decision = self._prompt_injection_guard.inspect_text(result.text, source_role="asr_segment")
        findings = tuple(
            {
                "source_type": "ASR_SEGMENT",
                "source_id": segment_id,
                "policy_version": decision.policy_version,
                "pattern_id": finding.pattern_id,
                "category": finding.category,
                "severity": finding.severity,
                "content_hash": finding.content_hash,
            }
            for finding in decision.findings
        )
        status = "SECURITY_REVIEW_REQUIRED" if findings else (
            "REQUIRES_CONFIRMATION" if result.confidence < 0.75 else "PROVISIONAL"
        )

        def persist() -> RealtimeTranscriptSegment:
            with self._database.transaction(identity.tenant_context) as session:
                existing_record = session.scalar(
                    select(RealtimeTranscriptSegmentRecord).where(
                        RealtimeTranscriptSegmentRecord.tenant_id == identity.tenant_id,
                        RealtimeTranscriptSegmentRecord.segment_id == segment_id,
                    )
                )
                if existing_record is not None:
                    return _view(existing_record)
                collision = session.scalar(
                    select(RealtimeTranscriptSegmentRecord).where(
                        RealtimeTranscriptSegmentRecord.tenant_id == identity.tenant_id,
                        RealtimeTranscriptSegmentRecord.session_id == stream_id,
                        RealtimeTranscriptSegmentRecord.sequence == sequence,
                    )
                )
                if collision is not None:
                    raise RealtimeSessionError("realtime_segment_sequence_conflict")
                record = RealtimeTranscriptSegmentRecord(
                    segment_id=segment_id,
                    tenant_id=identity.tenant_id,
                    session_id=stream_id,
                    diagnosis_run_id=diagnosis_run_id,
                    sequence=sequence,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=result.text,
                    confirmed_text=None,
                    confidence=result.confidence,
                    language=result.language,
                    entities_json=[],
                    security_policy_version=decision.policy_version,
                    security_findings_json=list(findings),
                    audio_sha256=result.audio_sha256,
                    resolved_release_id=result.resolved_release_id,
                    manifest_hash=result.manifest_hash,
                    status=status,
                    reviewer_subject_id=None,
                    reviewed_at=None,
                    agent_event_id=None,
                    agent_event_sequence=None,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                session.add(record)
                session.flush()
                return _view(record)

        return await asyncio.to_thread(persist)

    def confirm(
        self,
        identity: IdentityContext,
        segment_id: str,
        *,
        decision: str,
        corrected_text: str | None,
        expected_version: int,
        request_id: str,
    ) -> RealtimeTranscriptSegment:
        if decision not in {"ACCEPTED", "REJECTED"}:
            raise ValueError("transcript decision is invalid")
        normalized = corrected_text.strip() if corrected_text else None
        if decision == "ACCEPTED" and normalized is not None and len(normalized) > 4_000:
            raise ValueError("corrected transcript is too long")
        try:
            self._authorizer.require(
                identity,
                Action.CONFIRM_REALTIME_TRANSCRIPT,
                ResourceContext(identity.tenant_id, segment_id),
                request_id=request_id,
            )
        except AuthorizationDenied as exc:
            raise ResourceNotVisible from exc
        now = datetime.now(UTC)
        with self._database.transaction(identity.tenant_context) as session:
            record = session.scalar(
                select(RealtimeTranscriptSegmentRecord)
                .where(
                    RealtimeTranscriptSegmentRecord.tenant_id == identity.tenant_id,
                    RealtimeTranscriptSegmentRecord.segment_id == segment_id,
                )
                .with_for_update()
            )
            if record is None:
                raise ResourceNotVisible
            if record.version != expected_version:
                raise RealtimeSessionError("realtime_transcript_version_conflict")
            if record.status in {"ACCEPTED", "REJECTED"}:
                raise RealtimeSessionError("realtime_transcript_already_reviewed")
            if not record.security_policy_version:
                raise RealtimeSessionError("realtime_transcript_security_check_missing")
            if decision == "ACCEPTED" and record.security_findings_json and (
                normalized is None
                or self._prompt_injection_guard.inspect_text(
                    normalized, source_role="asr_segment"
                ).decision
                != "ALLOWED"
            ):
                raise RealtimeSessionError("realtime_transcript_security_blocked")
            event: AgentEventRecord | None = None
            if decision == "ACCEPTED":
                if record.diagnosis_run_id is None:
                    raise RealtimeSessionError("realtime_transcript_diagnosis_required")
                diagnosis = session.scalar(
                    select(DiagnosisRunRecord).where(
                        DiagnosisRunRecord.tenant_id == identity.tenant_id,
                        DiagnosisRunRecord.diagnosis_run_id == record.diagnosis_run_id,
                    )
                )
                if diagnosis is None:
                    raise ResourceNotVisible
                agent_run = session.scalar(
                    select(AgentRunRecord)
                    .where(
                        AgentRunRecord.tenant_id == identity.tenant_id,
                        AgentRunRecord.agent_run_id == diagnosis.agent_run_id,
                    )
                    .with_for_update()
                )
                if agent_run is None:
                    raise ResourceNotVisible
                event = _confirmed_input_event(
                    identity,
                    record,
                    diagnosis,
                    agent_run,
                    confirmed_text=normalized or record.text,
                    occurred_at=now,
                )
                session.add(event)
                agent_run.last_sequence = event.sequence
                agent_run.version += 1
                agent_run.updated_at = now
            record.status = decision
            record.confirmed_text = normalized or record.text if decision == "ACCEPTED" else None
            record.reviewer_subject_id = identity.subject_id
            record.reviewed_at = now
            record.agent_event_id = event.event_id if event else None
            record.agent_event_sequence = event.sequence if event else None
            record.version += 1
            record.updated_at = now
            return _view(record)

    def _find_existing(
        self,
        context: TenantContext,
        stream_id: str,
        segment_id: str,
        sequence: int,
        start_ms: int,
        end_ms: int,
        audio_hash: str,
    ) -> RealtimeTranscriptSegment | None:
        with self._database.transaction(context) as session:
            record = session.scalar(
                select(RealtimeTranscriptSegmentRecord).where(
                    RealtimeTranscriptSegmentRecord.tenant_id == context.tenant_id,
                    RealtimeTranscriptSegmentRecord.segment_id == segment_id,
                )
            )
            if record is not None:
                existing_key = (
                    record.session_id,
                    record.sequence,
                    record.start_ms,
                    record.end_ms,
                    record.audio_sha256,
                )
                if existing_key != (
                    stream_id, sequence, start_ms, end_ms, audio_hash
                ):
                    raise RealtimeSessionError("realtime_segment_idempotency_conflict")
                return _view(record)
            return None


def _view(record: RealtimeTranscriptSegmentRecord) -> RealtimeTranscriptSegment:
    return RealtimeTranscriptSegment(
        segment_id=record.segment_id,
        session_id=record.session_id,
        sequence=record.sequence,
        start_ms=record.start_ms,
        end_ms=record.end_ms,
        text=record.text,
        confirmed_text=record.confirmed_text,
        confidence=record.confidence,
        language=record.language,
        entities=tuple(dict(item) for item in record.entities_json),
        resolved_release_id=record.resolved_release_id,
        manifest_hash=record.manifest_hash,
        status=record.status,
        agent_event_id=record.agent_event_id,
        agent_event_sequence=record.agent_event_sequence,
        security_policy_version=record.security_policy_version,
        security_findings=tuple(dict(item) for item in record.security_findings_json),
        version=record.version,
    )


def _confirmed_input_event(
    identity: IdentityContext,
    transcript: RealtimeTranscriptSegmentRecord,
    diagnosis: DiagnosisRunRecord,
    agent_run: AgentRunRecord,
    *,
    confirmed_text: str,
    occurred_at: datetime,
) -> AgentEventRecord:
    return AgentEventRecord(
        event_id=f"agent-event-{uuid4().hex}",
        tenant_id=identity.tenant_id,
        agent_run_id=agent_run.agent_run_id,
        sequence=agent_run.last_sequence + 1,
        event_type="agent.user_input.confirmed",
        payload={
            "diagnosis_run_id": diagnosis.diagnosis_run_id,
            "source_type": "confirmed_transcript",
            "source_id": transcript.segment_id,
            "stream_id": transcript.session_id,
            "text": confirmed_text,
            "language": transcript.language,
            "reviewer_subject_id": identity.subject_id,
            "asr_release_id": transcript.resolved_release_id,
            "asr_manifest_hash": transcript.manifest_hash,
        },
        visibility="authorized",
        occurred_at=occurred_at,
        created_at=occurred_at,
        updated_at=occurred_at,
    )
