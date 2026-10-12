"""Domain-neutral multimodal perception contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256


class EvidenceSchemaError(ValueError):
    """Processor output does not satisfy the evidence contract."""

class QrPayloadKind(StrEnum):
    TEXT = "TEXT"
    HTTPS_URL = "HTTPS_URL"
    OTHER_URI = "OTHER_URI"


TEMPORAL_VIDEO_EVENT_TYPES = frozenset(
    {"motion_candidate", "signal_pattern_candidate", "action_sequence_candidate"}
)


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Normalized source-region coordinates in the inclusive 0..1 image space."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        values = (self.x, self.y, self.width, self.height)
        if any(value < 0 or value > 1 for value in values):
            raise EvidenceSchemaError("bounding box coordinates must be normalized")
        if self.width <= 0 or self.height <= 0:
            raise EvidenceSchemaError("bounding box must have a positive area")
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise EvidenceSchemaError("bounding box exceeds the source image")


@dataclass(frozen=True, slots=True)
class OcrBlock:
    block_id: str
    page_number: int
    text: str
    bbox: BoundingBox
    confidence: float
    source_frame_id: str | None = None

    def __post_init__(self) -> None:
        if not self.block_id or self.page_number < 1 or not self.text.strip():
            raise EvidenceSchemaError("OCR block identity, page and text are required")
        _validate_confidence(self.confidence)

@dataclass(frozen=True, slots=True)
class QrCodeCandidate:
    candidate_id: str
    text: str
    payload_kind: QrPayloadKind
    bbox: BoundingBox
    source_frame_id: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.candidate_id.strip()
            or not self.text.strip()
            or len(self.text.encode("utf-8")) > 4_096
            or (self.source_frame_id is not None and not self.source_frame_id.strip())
        ):
            raise EvidenceSchemaError("QR candidate contract is invalid")


@dataclass(frozen=True, slots=True)
class VisualFinding:
    finding_id: str
    label: str
    bbox: BoundingBox
    confidence: float
    evidence_level: str
    model_release_id: str
    description: str
    source_frame_id: str | None = None

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.finding_id,
                self.label,
                self.evidence_level,
                self.model_release_id,
                self.description,
            )
        ):
            raise EvidenceSchemaError("visual finding fields cannot be empty")
        if self.evidence_level not in {"candidate", "supporting"}:
            raise EvidenceSchemaError("VLM findings can only be candidate evidence")
        _validate_confidence(self.confidence)

@dataclass(frozen=True, slots=True)
class AsrSegment:
    segment_id: str
    start_ms: int
    end_ms: int
    text: str
    language: str
    confidence: float
    model_release_id: str
    source_audio_track_id: str | None = None
    hotword_profile_id: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.segment_id.strip()
            or self.start_ms < 0
            or self.end_ms <= self.start_ms
            or not self.text.strip()
            or self.language not in {"zh", "en"}
            or not self.model_release_id.strip()
            or (self.source_audio_track_id is not None and not self.source_audio_track_id.strip())
            or (self.hotword_profile_id is not None and not self.hotword_profile_id.strip())
        ):
            raise EvidenceSchemaError("ASR segment contract is invalid")
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class VideoKeyframe:
    frame_id: str
    timestamp_ms: int
    image_sha256: str
    sampling_reason: str
    image_jpeg: bytes | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            not self.frame_id.strip()
            or self.timestamp_ms < 0
            or len(self.image_sha256) != 64
            or self.sampling_reason not in {"first_frame", "periodic", "scene_change"}
        ):
            raise EvidenceSchemaError("video keyframe contract is invalid")
        if self.image_jpeg is not None and (
            len(self.image_jpeg) > 2 * 1024 * 1024
            or not self.image_jpeg.startswith(b"\xff\xd8\xff")
            or sha256(self.image_jpeg).hexdigest() != self.image_sha256
        ):
            raise EvidenceSchemaError("video keyframe artifact is invalid")


@dataclass(frozen=True, slots=True)
class VideoEvent:
    event_id: str
    event_type: str
    start_ms: int
    end_ms: int
    keyframe_ids: tuple[str, ...]
    confidence: float
    description: str
    finding_ids: tuple[str, ...] = ()
    model_release_id: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.event_id.strip()
            or self.event_type
            not in {
                "periodic_observation",
                "scene_change",
                "visual_candidate",
                *TEMPORAL_VIDEO_EVENT_TYPES,
            }
            or self.start_ms < 0
            or self.end_ms < self.start_ms
            or not self.keyframe_ids
            or not self.description.strip()
            or len(set(self.keyframe_ids)) != len(self.keyframe_ids)
            or len(set(self.finding_ids)) != len(self.finding_ids)
            or (self.event_type == "visual_candidate") != bool(self.finding_ids)
            or (self.event_type in TEMPORAL_VIDEO_EVENT_TYPES) != bool(self.model_release_id)
            or (
                self.event_type in TEMPORAL_VIDEO_EVENT_TYPES
                and (len(self.keyframe_ids) < 2 or self.end_ms <= self.start_ms)
            )
        ):
            raise EvidenceSchemaError("video event contract is invalid")
        _validate_confidence(self.confidence)

@dataclass(frozen=True, slots=True)
class PerceptionResult:
    """Domain-neutral observations emitted from one image or video input."""

    source_type: str
    ocr_blocks: tuple[OcrBlock, ...] = ()
    visual_findings: tuple[VisualFinding, ...] = ()
    qr_codes: tuple[QrCodeCandidate, ...] = ()
    asr_segments: tuple[AsrSegment, ...] = ()
    video_keyframes: tuple[VideoKeyframe, ...] = ()
    video_events: tuple[VideoEvent, ...] = ()
    processor_versions: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.source_type not in {"image", "video"}:
            raise EvidenceSchemaError("perception source type is invalid")
        if not self.processor_versions:
            raise EvidenceSchemaError("perception processor versions are required")


@dataclass(frozen=True, slots=True)
class PerceptionRequest:
    """Media and caller-provided context required for domain-neutral perception."""

    tenant_id: str
    source_id: str
    content_hash: str
    mime_type: str
    content: bytes
    vlm_instruction: str
    subject_id: str = "recognition-worker"
    trace_id: str = "recognition-worker"
    business_run_id: str | None = None
    event_identity: str | None = None
    processor_profile: str = "local-core-v1"
    asr_context: str | None = None
    temporal_instruction: str | None = None

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.tenant_id,
                self.source_id,
                self.content_hash,
                self.mime_type,
                self.vlm_instruction,
            )
        ):
            raise EvidenceSchemaError("perception request identity is incomplete")
        if len(self.content_hash) != 64 or not self.content:
            raise EvidenceSchemaError("perception request media is invalid")

def _validate_confidence(value: float) -> None:
    if value < 0 or value > 1:
        raise EvidenceSchemaError("confidence must be between 0 and 1")
