"""Generic transcript ingestion and confirmation API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field

from industrial_ops_agent.api.dependencies import (
    get_identity,
    get_realtime_transcript_service,
)
from industrial_ops_agent.api.errors import STANDARD_ERROR_RESPONSES, AppError
from industrial_ops_agent.application.assets import ResourceNotVisible
from industrial_ops_agent.auth.identity import IdentityContext
from industrial_ops_agent.model_gateway.service import ModelGatewayError
from industrial_ops_agent.multimodal.realtime_transcripts import (
    RealtimeSessionError,
    RealtimeTranscriptSegment,
    RealtimeTranscriptService,
)

router = APIRouter(tags=["transcription"])


class TranscriptEntityResponse(BaseModel):
    entity_id: str
    entity_type: str
    value: str
    confidence: float
    requires_confirmation: bool


class RealtimeTranscriptResponse(BaseModel):
    segment_id: str
    session_id: str
    sequence: int
    start_ms: int
    end_ms: int
    text: str
    confirmed_text: str | None
    confidence: float
    language: str
    entities: list[TranscriptEntityResponse]
    resolved_release_id: str
    manifest_hash: str
    status: str
    agent_event_id: str | None
    agent_event_sequence: int | None
    security_policy_version: str | None
    security_findings: list[dict[str, str]]
    version: int


class RealtimeTranscriptEnvelope(BaseModel):
    data: RealtimeTranscriptResponse
    meta: dict[str, str]


class ConfirmRealtimeTranscriptRequest(BaseModel):
    decision: str = Field(pattern="^(ACCEPTED|REJECTED)$")
    corrected_text: str | None = Field(default=None, max_length=4_000)


@router.post(
    "/transcript-streams/{stream_id}/segments",
    response_model=RealtimeTranscriptEnvelope,
    status_code=201,
    responses=STANDARD_ERROR_RESPONSES,
)
async def transcribe_segment(
    stream_id: str,
    request: Request,
    identity: Annotated[IdentityContext, Depends(get_identity)],
    service: Annotated[RealtimeTranscriptService, Depends(get_realtime_transcript_service)],
    segment_id: Annotated[str, Header(alias="Segment-Id", min_length=1, max_length=128)],
    diagnosis_run_id: Annotated[str | None, Header(alias="Diagnosis-Run-Id")] = None,
    sequence: Annotated[int, Header(alias="Segment-Sequence", ge=1)] = 1,
    start_ms: Annotated[int, Header(alias="Segment-Start-Ms", ge=0)] = 0,
    end_ms: Annotated[int, Header(alias="Segment-End-Ms", ge=1)] = 1,
    content_type: Annotated[str, Header(alias="Content-Type")] = "audio/wav",
) -> RealtimeTranscriptEnvelope:
    if content_type.split(";", 1)[0] != "audio/wav":
        raise AppError(415, "transcript_media_type_invalid", "validation", "audio/wav is required")
    try:
        result = await service.transcribe(
            identity,
            stream_id,
            diagnosis_run_id=diagnosis_run_id,
            segment_id=segment_id,
            sequence=sequence,
            start_ms=start_ms,
            end_ms=end_ms,
            audio_wav=await request.body(),
            request_id=request.state.request_id,
        )
    except RealtimeSessionError as exc:
        raise AppError(409, exc.reason, "state", "Transcript stream state rejected") from exc
    except ModelGatewayError as exc:
        raise AppError(
            503,
            exc.reason,
            "dependency",
            "Transcription unavailable",
            retryable=True,
        ) from exc
    return RealtimeTranscriptEnvelope(
        data=_transcript_response(result),
        meta={"request_id": request.state.request_id},
    )


@router.post(
    "/transcripts/{segment_id}/confirmation",
    response_model=RealtimeTranscriptEnvelope,
    responses=STANDARD_ERROR_RESPONSES,
)
def confirm_transcript(
    segment_id: str,
    body: ConfirmRealtimeTranscriptRequest,
    request: Request,
    identity: Annotated[IdentityContext, Depends(get_identity)],
    service: Annotated[RealtimeTranscriptService, Depends(get_realtime_transcript_service)],
    if_match: Annotated[str, Header(alias="If-Match")],
) -> RealtimeTranscriptEnvelope:
    try:
        result = service.confirm(
            identity,
            segment_id,
            decision=body.decision,
            corrected_text=body.corrected_text,
            expected_version=_parse_version(if_match),
            request_id=request.state.request_id,
        )
    except ResourceNotVisible as exc:
        raise AppError(404, "transcript_not_found", "not_found", "Transcript not found") from exc
    except RealtimeSessionError as exc:
        raise AppError(409, exc.reason, "state", "Transcript confirmation rejected") from exc
    except ValueError as exc:
        raise AppError(422, "transcript_invalid", "validation", str(exc)) from exc
    return RealtimeTranscriptEnvelope(
        data=_transcript_response(result),
        meta={"request_id": request.state.request_id},
    )


def _transcript_response(
    transcript: RealtimeTranscriptSegment,
) -> RealtimeTranscriptResponse:
    return RealtimeTranscriptResponse(
        segment_id=transcript.segment_id,
        session_id=transcript.session_id,
        sequence=transcript.sequence,
        start_ms=transcript.start_ms,
        end_ms=transcript.end_ms,
        text=transcript.text,
        confirmed_text=transcript.confirmed_text,
        confidence=transcript.confidence,
        language=transcript.language,
        entities=[TranscriptEntityResponse.model_validate(item) for item in transcript.entities],
        resolved_release_id=transcript.resolved_release_id,
        manifest_hash=transcript.manifest_hash,
        status=transcript.status,
        agent_event_id=transcript.agent_event_id,
        agent_event_sequence=transcript.agent_event_sequence,
        security_policy_version=transcript.security_policy_version,
        security_findings=list(transcript.security_findings),
        version=transcript.version,
    )


def _parse_version(value: str) -> int:
    try:
        version = int(value.strip().removeprefix("W/").strip('"'))
    except ValueError as exc:
        raise AppError(
            400,
            "invalid_version_precondition",
            "validation",
            "If-Match is invalid",
        ) from exc
    if version < 1:
        raise AppError(400, "invalid_version_precondition", "validation", "If-Match is invalid")
    return version
