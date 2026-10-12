"""Domain-neutral multimodal perception contracts and provider adapters."""

from industrial_ops_agent.multimodal.models import (
    AsrSegment,
    BoundingBox,
    OcrBlock,
    PerceptionRequest,
    PerceptionResult,
    QrCodeCandidate,
    VisualFinding,
)

__all__ = [
    "AsrSegment",
    "BoundingBox",
    "OcrBlock",
    "PerceptionRequest",
    "PerceptionResult",
    "QrCodeCandidate",
    "VisualFinding",
]
