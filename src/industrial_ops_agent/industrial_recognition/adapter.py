"""Map generic perception into the existing Industrial Diagnosis evidence contract."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from industrial_ops_agent.guardrails.prompt_injection import PromptInjectionGuard
from industrial_ops_agent.industrial_recognition.evidence import (
    REVIEWABLE_VIDEO_EVENT_TYPES,
    AsrEntityCandidate,
    EntityValidationStatus,
    EvidenceBundle,
    EvidenceSchemaError,
    EvidenceSecurityFinding,
    ExtractedEntity,
)
from industrial_ops_agent.industrial_recognition.evidence import (
    AsrSegment as EvidenceAsrSegment,
)
from industrial_ops_agent.industrial_recognition.evidence import (
    BoundingBox as EvidenceBoundingBox,
)
from industrial_ops_agent.industrial_recognition.evidence import (
    OcrBlock as EvidenceOcrBlock,
)
from industrial_ops_agent.industrial_recognition.evidence import (
    QrCodeCandidate as EvidenceQrCodeCandidate,
)
from industrial_ops_agent.industrial_recognition.evidence import (
    QrPayloadKind as EvidenceQrPayloadKind,
)
from industrial_ops_agent.industrial_recognition.evidence import (
    VideoEvent as EvidenceVideoEvent,
)
from industrial_ops_agent.industrial_recognition.evidence import (
    VideoKeyframe as EvidenceVideoKeyframe,
)
from industrial_ops_agent.industrial_recognition.evidence import (
    VisualFinding as EvidenceVisualFinding,
)
from industrial_ops_agent.multimodal.models import (
    AsrSegment,
    BoundingBox,
    OcrBlock,
    PerceptionResult,
    QrCodeCandidate,
    VideoEvent,
    VideoKeyframe,
    VisualFinding,
)


@dataclass(frozen=True, slots=True)
class IndustrialRecognitionContext:
    """Industrial identifiers and policy inputs excluded from multimodal perception."""

    bundle_id: str
    tenant_id: str
    draft_id: str
    asset_id: str
    media_id: str
    source_sha256: str
    occurred_at: datetime


class IndustrialEvidenceMapper:
    """Own the industrial entity, safety and EvidenceBundle interpretation rules."""

    def __init__(self, guard: PromptInjectionGuard | None = None) -> None:
        self._guard = guard or PromptInjectionGuard()

    def to_evidence_bundle(
        self,
        result: PerceptionResult,
        context: IndustrialRecognitionContext,
    ) -> EvidenceBundle:
        versions = dict(result.processor_versions)
        versions["entity_validator"] = "industrial-entity-rules-v2"
        ocr_blocks = tuple(_to_evidence_ocr_block(block) for block in result.ocr_blocks)
        visual_findings = tuple(
            _to_evidence_visual_finding(finding) for finding in result.visual_findings
        )
        video_keyframes = tuple(
            _to_evidence_video_keyframe(keyframe) for keyframe in result.video_keyframes
        )
        video_events = tuple(_to_evidence_video_event(event) for event in result.video_events)
        qr_codes = _secure_qr_candidates(self._guard, result.qr_codes)
        asr_segments = tuple(
            _to_evidence_asr_segment(segment)
            for segment in result.asr_segments
        )

        security_findings = _security_findings(
            self._guard,
            ocr_blocks=result.ocr_blocks,
            asr_segments=result.asr_segments,
            visual_findings=result.visual_findings,
            video_events=result.video_events,
        )
        return EvidenceBundle.create(
            bundle_id=context.bundle_id,
            tenant_id=context.tenant_id,
            draft_id=context.draft_id,
            asset_id=context.asset_id,
            media_id=context.media_id,
            source_sha256=context.source_sha256,
            source_type=result.source_type,
            ocr_blocks=ocr_blocks,
            asr_segments=asr_segments,
            visual_findings=visual_findings,
            video_keyframes=video_keyframes,
            video_events=video_events,
            qr_codes=qr_codes,
            extracted_entities=_extract_entities(result.ocr_blocks),
            processor_versions=versions,
            occurred_at=context.occurred_at,
            security_policy_version=self._guard.policy_version,
            security_findings=security_findings,
        )


def industrial_perception_instructions(asset_model: str) -> tuple[str, tuple[str, ...], str]:
    """Build the existing Industrial Diagnosis instructions outside multimodal providers."""

    vlm_instruction = (
        "Inspect this industrial asset image. Return only JSON. "
        f"Expected asset model: {asset_model}. Findings are candidates, "
        "must use normalized [x,y,width,height] regions, and must never "
        "claim a final diagnosis. If the model is unsupported, set supported=false."
    )
    temporal_instruction = (
        f"Industrial asset model: {asset_model}. Frames are chronological. "
        "Only report a candidate when motion, repeated signal change, or action "
        "ordering is visible across at least two supplied frames. Reference exact "
        "frame_id values. Single-frame appearance is handled elsewhere. If this "
        "asset or task is unsupported, set supported=false."
    )
    return vlm_instruction, (asset_model,), temporal_instruction


def _security_findings(
    guard: PromptInjectionGuard,
    *,
    ocr_blocks: tuple[OcrBlock, ...] = (),
    asr_segments: tuple[AsrSegment, ...] = (),
    visual_findings: tuple[VisualFinding, ...] = (),
    video_events: tuple[VideoEvent, ...] = (),
) -> tuple[EvidenceSecurityFinding, ...]:
    sources = [("OCR_BLOCK", item.block_id, item.text, "ocr_block") for item in ocr_blocks]
    sources.extend(
        ("ASR_SEGMENT", item.segment_id, item.text, "asr_segment") for item in asr_segments
    )
    sources.extend(
        (
            "VISUAL_FINDING",
            item.finding_id,
            f"{item.label}\n{item.description}",
            "visual_finding",
        )
        for item in visual_findings
    )
    sources.extend(
        ("VIDEO_EVENT", item.event_id, item.description, "video_event")
        for item in video_events
        if item.event_type in REVIEWABLE_VIDEO_EVENT_TYPES
    )
    findings: list[EvidenceSecurityFinding] = []
    for source_type, source_id, text, source_role in sources:
        decision = guard.inspect_text(text, source_role=source_role)
        findings.extend(
            EvidenceSecurityFinding(
                source_type=source_type,
                source_id=source_id,
                policy_version=decision.policy_version,
                pattern_id=finding.pattern_id,
                category=finding.category,
                severity=finding.severity,
                content_hash=finding.content_hash,
            )
            for finding in decision.findings
        )
    return tuple(
        sorted(
            findings,
            key=lambda item: (
                item.source_type,
                item.source_id,
                item.pattern_id,
                item.content_hash,
            ),
        )
    )


def _secure_qr_candidates(
    guard: PromptInjectionGuard,
    candidates: tuple[QrCodeCandidate, ...],
) -> tuple[EvidenceQrCodeCandidate, ...]:
    secured: list[EvidenceQrCodeCandidate] = []
    for candidate in candidates:
        decision = guard.inspect_text(candidate.text, source_role="qr_code")
        secured.append(
            EvidenceQrCodeCandidate(
                candidate_id=candidate.candidate_id,
                text=candidate.text,
                payload_kind=EvidenceQrPayloadKind(candidate.payload_kind.value),
                bbox=_to_evidence_bounding_box(candidate.bbox),
                source_frame_id=candidate.source_frame_id,
                security_findings=tuple(
                    EvidenceSecurityFinding(
                        source_type="QR_CODE",
                        source_id=candidate.candidate_id,
                        policy_version=decision.policy_version,
                        pattern_id=finding.pattern_id,
                        category=finding.category,
                        severity=finding.severity,
                        content_hash=finding.content_hash,
                    )
                    for finding in decision.findings
                ),
            )
        )
    return tuple(secured)


def _to_evidence_asr_segment(segment: AsrSegment) -> EvidenceAsrSegment:
    return EvidenceAsrSegment(
        segment_id=segment.segment_id,
        start_ms=segment.start_ms,
        end_ms=segment.end_ms,
        text=segment.text,
        language=segment.language,
        confidence=segment.confidence,
        model_release_id=segment.model_release_id,
        source_audio_track_id=segment.source_audio_track_id,
        hotword_profile_id=segment.hotword_profile_id,
        entity_candidates=_extract_asr_entity_candidates(
            segment.segment_id,
            segment.text,
            segment.confidence,
        ),
    )


def _to_evidence_bounding_box(box: BoundingBox) -> EvidenceBoundingBox:
    return EvidenceBoundingBox(box.x, box.y, box.width, box.height)


def _to_evidence_ocr_block(block: OcrBlock) -> EvidenceOcrBlock:
    return EvidenceOcrBlock(
        block_id=block.block_id,
        page_number=block.page_number,
        text=block.text,
        bbox=_to_evidence_bounding_box(block.bbox),
        confidence=block.confidence,
        source_frame_id=block.source_frame_id,
    )


def _to_evidence_visual_finding(finding: VisualFinding) -> EvidenceVisualFinding:
    return EvidenceVisualFinding(
        finding_id=finding.finding_id,
        label=finding.label,
        bbox=_to_evidence_bounding_box(finding.bbox),
        confidence=finding.confidence,
        evidence_level=finding.evidence_level,
        model_release_id=finding.model_release_id,
        description=finding.description,
        source_frame_id=finding.source_frame_id,
    )


def _to_evidence_video_keyframe(keyframe: VideoKeyframe) -> EvidenceVideoKeyframe:
    return EvidenceVideoKeyframe(
        frame_id=keyframe.frame_id,
        timestamp_ms=keyframe.timestamp_ms,
        image_sha256=keyframe.image_sha256,
        sampling_reason=keyframe.sampling_reason,
        image_jpeg=keyframe.image_jpeg,
    )


def _to_evidence_video_event(event: VideoEvent) -> EvidenceVideoEvent:
    return EvidenceVideoEvent(
        event_id=event.event_id,
        event_type=event.event_type,
        start_ms=event.start_ms,
        end_ms=event.end_ms,
        keyframe_ids=event.keyframe_ids,
        confidence=event.confidence,
        description=event.description,
        finding_ids=event.finding_ids,
        model_release_id=event.model_release_id,
    )


@dataclass(frozen=True, slots=True)
class _EntityRule:
    entity_type: str
    pattern: re.Pattern[str]
    value_group: int | None
    authoritative_confirmation_required: bool


_ENTITY_RULES: tuple[_EntityRule, ...] = (
    _EntityRule(
        "alarm_code",
        re.compile(
            r"(?:ALARM|FAULT|ERROR|ERR|报警码|故障码)\s*[:#：-]?\s*"
            r"([A-Z]{1,4}[\s_—–-]?\d{2,6})\b",
            re.IGNORECASE,
        ),
        1,
        False,
    ),
    _EntityRule(
        "part_number",
        re.compile(
            r"(?:P/N|PART(?:\s+(?:NO|NUMBER))?|零件号|部件号)\s*[:#：-]*\s*"
            r"([A-Z0-9][A-Z0-9._/-]{3,})",
            re.IGNORECASE,
        ),
        1,
        True,
    ),
    _EntityRule(
        "serial_number",
        re.compile(
            r"(?:S/N|SERIAL(?:\s+NO)?|序列号|设备号)\s*[:#：-]*\s*"
            r"([A-Z0-9][A-Z0-9._/-]{3,})",
            re.IGNORECASE,
        ),
        1,
        True,
    ),
    _EntityRule(
        "measurement",
        re.compile(
            r"(?<![A-Z0-9])[-+]?\d+(?:\.\d+)?\s*"
            r"(?:°C|℃|MPA|KPA|BAR|V|A|HZ|RPM|MM/S)(?![A-Z])",
            re.IGNORECASE,
        ),
        None,
        True,
    ),
)

_UNIT_NORMALIZATION = {
    "℃": "°C",
    "°C": "°C",
    "MPA": "MPa",
    "KPA": "kPa",
    "BAR": "bar",
    "V": "V",
    "A": "A",
    "HZ": "Hz",
    "RPM": "rpm",
    "MM/S": "mm/s",
}

_ASR_ENTITY_CONFIRMATION_THRESHOLD = 0.9


def _extract_asr_entity_candidates(
    segment_id: str,
    text: str,
    confidence: float,
) -> tuple[AsrEntityCandidate, ...]:
    rows: list[AsrEntityCandidate] = []
    for rule in _ENTITY_RULES:
        for match in rule.pattern.finditer(text):
            value_group = rule.value_group if rule.value_group is not None else 0
            value = match.group(value_group)
            start_offset = match.start(value_group)
            end_offset = match.end(value_group)
            normalized = _normalize_entity_value(rule.entity_type, value)
            digest = sha256(
                f"{segment_id}\0{rule.entity_type}\0{start_offset}\0{normalized}".encode()
            ).hexdigest()[:16]
            rows.append(
                AsrEntityCandidate(
                    entity_id=f"asr-entity-{digest}",
                    source_segment_id=segment_id,
                    entity_type=rule.entity_type,
                    value=value,
                    normalized_value=normalized,
                    confidence=confidence,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    requires_confirmation=confidence < _ASR_ENTITY_CONFIRMATION_THRESHOLD,
                )
            )
    return tuple(rows)


def _extract_entities(blocks: tuple[OcrBlock, ...]) -> tuple[ExtractedEntity, ...]:
    rows: list[ExtractedEntity] = []
    for block in blocks:
        for rule in _ENTITY_RULES:
            for match in rule.pattern.finditer(block.text):
                value = match.group(rule.value_group) if rule.value_group else match.group(0)
                normalized = _normalize_entity_value(rule.entity_type, value)
                if block.confidence < 0.9:
                    status = EntityValidationStatus.REQUIRES_CONFIRMATION
                    reason = "low_ocr_confidence"
                elif rule.authoritative_confirmation_required:
                    status = EntityValidationStatus.REQUIRES_CONFIRMATION
                    reason = "authoritative_source_or_human_confirmation_required"
                else:
                    status = EntityValidationStatus.VALID
                    reason = None
                digest = sha256(
                    f"{block.block_id}\0{rule.entity_type}\0{match.start()}\0{normalized}".encode()
                ).hexdigest()[:16]
                rows.append(
                    ExtractedEntity(
                        entity_id=f"entity-{digest}",
                        entity_type=rule.entity_type,
                        value=value,
                        normalized_value=normalized,
                        confidence=block.confidence,
                        validation_status=status,
                        source_block_id=block.block_id,
                        validation_reason=reason,
                    )
                )
    return tuple(rows)


def _normalize_entity_value(entity_type: str, value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    normalized = normalized.replace("—", "-").replace("–", "-").replace("℃", "°C")
    if entity_type == "measurement":
        match = re.fullmatch(
            r"([-+]?\d+(?:\.\d+)?)\s*(°C|MPA|KPA|BAR|V|A|HZ|RPM|MM/S)",
            normalized,
            re.IGNORECASE,
        )
        if match is None:
            raise EvidenceSchemaError("measurement normalization failed")
        return f"{match.group(1)} {_UNIT_NORMALIZATION[match.group(2).upper()]}"
    return re.sub(r"[\s_]", "-", normalized.upper()).strip("-")
