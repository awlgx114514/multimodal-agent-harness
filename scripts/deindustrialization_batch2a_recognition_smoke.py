"""Behavioral smoke for the Batch 2A perception-to-recognition boundary."""

from __future__ import annotations

import asyncio
from dataclasses import fields
from datetime import UTC, datetime
from hashlib import sha256
from inspect import signature

from industrial_ops_agent.industrial_recognition.adapter import (
    IndustrialEvidenceMapper,
    IndustrialRecognitionContext,
)
from industrial_ops_agent.industrial_recognition.evidence import (
    FindingDisposition,
    QrDisposition,
)
from industrial_ops_agent.multimodal.models import (
    BoundingBox,
    OcrBlock,
    PerceptionRequest,
    PerceptionResult,
    QrCodeCandidate,
    QrPayloadKind,
    VisualFinding,
)
from industrial_ops_agent.multimodal.processor import MultimodalProcessor
from industrial_ops_agent.multimodal.providers import (
    OcrProviderResult,
    VlmProvider,
    VlmProviderResult,
)
from industrial_ops_agent.multimodal.video import VideoAsrProvider, VideoTemporalProvider


def _perception_result() -> PerceptionResult:
    return PerceptionResult(
        source_type="image",
        ocr_blocks=(
            OcrBlock(
                block_id="ocr-1",
                page_number=1,
                text="ALARM-42",
                bbox=BoundingBox(0.1, 0.1, 0.2, 0.1),
                confidence=0.98,
            ),
        ),
        visual_findings=(
            VisualFinding(
                finding_id="finding-1",
                label="indicator_light",
                bbox=BoundingBox(0.3, 0.2, 0.1, 0.1),
                confidence=0.91,
                evidence_level="candidate",
                model_release_id="vlm-r1",
                description="red indicator is visible",
            ),
        ),
        qr_codes=(
            QrCodeCandidate(
                candidate_id="qr-1",
                text="https://example.invalid/manual",
                payload_kind=QrPayloadKind.HTTPS_URL,
                bbox=BoundingBox(0.5, 0.5, 0.2, 0.2),
            ),
        ),
        processor_versions={"ocr": "ocr-r1", "vlm": "vlm-r1"},
    )


def _box_tuple(box: BoundingBox) -> tuple[float, float, float, float]:
    return (box.x, box.y, box.width, box.height)


class _Ocr:
    async def recognize(self, content: bytes, **_: object) -> OcrProviderResult:
        del content
        return OcrProviderResult(
            blocks=(
                OcrBlock(
                    block_id="processor-ocr-1",
                    page_number=1,
                    text="ALARM-42",
                    bbox=BoundingBox(0.1, 0.1, 0.2, 0.1),
                    confidence=0.98,
                ),
            ),
            processor_version="ocr-r1",
        )


class _Vlm:
    def __init__(self) -> None:
        self.instruction: str | None = None

    async def inspect(self, content: bytes, *, instruction: str, **_: object) -> VlmProviderResult:
        del content
        self.instruction = instruction
        return VlmProviderResult(
            findings=(
                VisualFinding(
                    finding_id="processor-finding-1",
                    label="indicator_light",
                    bbox=BoundingBox(0.3, 0.2, 0.1, 0.1),
                    confidence=0.91,
                    evidence_level="candidate",
                    model_release_id="vlm-r1",
                    description="red indicator is visible",
                ),
            ),
            processor_version="vlm-r1",
        )


async def _process_image() -> None:
    content = b"clean-image"
    vlm = _Vlm()
    result = await MultimodalProcessor(_Ocr(), vlm).process(
        PerceptionRequest(
            tenant_id="tenant-1",
            source_id="media-1",
            content_hash=sha256(content).hexdigest(),
            mime_type="image/jpeg",
            content=content,
            vlm_instruction="Return candidate visual observations only.",
        )
    )
    assert isinstance(result, PerceptionResult)
    assert result.ocr_blocks[0].block_id == "processor-ocr-1"
    assert result.visual_findings[0].finding_id == "processor-finding-1"
    assert result.processor_versions == {"ocr": "ocr-r1", "vlm": "vlm-r1"}
    assert vlm.instruction == "Return candidate visual observations only."


def main() -> None:
    assert "asset_model" not in signature(VlmProvider.inspect).parameters
    assert "asset_model" not in signature(VideoAsrProvider.transcribe).parameters
    assert "asset_model" not in signature(VideoTemporalProvider.analyze).parameters

    request = PerceptionRequest(
        tenant_id="tenant-1",
        source_id="media-1",
        content_hash="a" * 64,
        mime_type="image/jpeg",
        content=b"clean-image",
        vlm_instruction="Return candidate visual observations only.",
    )
    assert request.source_id == "media-1"
    assert request.vlm_instruction == "Return candidate visual observations only."
    assert not {"asset_id", "asset_model", "draft_id", "bundle_id"}.intersection(
        field.name for field in fields(request)
    )
    asyncio.run(_process_image())

    result = _perception_result()
    assert len(result.ocr_blocks) == 1
    assert result.ocr_blocks[0].text == "ALARM-42"
    assert len(result.visual_findings) == 1
    assert result.visual_findings[0].confidence == 0.91
    assert len(result.qr_codes) == 1
    assert result.processor_versions == {"ocr": "ocr-r1", "vlm": "vlm-r1"}

    industrial_fields = {
        "asset_id",
        "asset_model",
        "draft_id",
        "bundle_id",
        "incident_id",
        "diagnosis_run_id",
        "status",
        "review_state",
        "confirmation_state",
        "automation_eligible",
    }
    assert not industrial_fields.intersection(field.name for field in fields(result))

    bundle = IndustrialEvidenceMapper().to_evidence_bundle(
        result,
        IndustrialRecognitionContext(
            bundle_id="bundle-1",
            tenant_id="tenant-1",
            draft_id="draft-1",
            asset_id="asset-1",
            media_id="media-1",
            source_sha256="a" * 64,
            occurred_at=datetime(2026, 9, 14, tzinfo=UTC),
        ),
    )
    assert (bundle.bundle_id, bundle.tenant_id, bundle.draft_id, bundle.asset_id) == (
        "bundle-1",
        "tenant-1",
        "draft-1",
        "asset-1",
    )
    assert [
        (item.block_id, item.text, _box_tuple(item.bbox), item.confidence)
        for item in bundle.ocr_blocks
    ] == [
        (item.block_id, item.text, _box_tuple(item.bbox), item.confidence)
        for item in result.ocr_blocks
    ]
    assert [
        (item.finding_id, item.label, _box_tuple(item.bbox), item.confidence, item.description)
        for item in bundle.visual_findings
    ] == [
        (item.finding_id, item.label, _box_tuple(item.bbox), item.confidence, item.description)
        for item in result.visual_findings
    ]
    assert [(item.candidate_id, item.text, _box_tuple(item.bbox)) for item in bundle.qr_codes] == [
        (item.candidate_id, item.text, _box_tuple(item.bbox)) for item in result.qr_codes
    ]
    assert bundle.status.value == "READY_FOR_CONFIRMATION"
    assert bundle.automation_eligible is False
    assert bundle.automation_blockers == ("qr_codes_not_reviewed",)
    confirmed = bundle.confirm(
        reviewer_subject_id="reviewer-1",
        corrections={},
        finding_dispositions={"finding-1": FindingDisposition.ACCEPTED},
        transcript_decisions={},
        qr_code_decisions={"qr-1": (QrDisposition.ACCEPTED, None)},
        expected_version=1,
        occurred_at=datetime(2026, 9, 14, 1, tzinfo=UTC),
    )
    assert confirmed.status.value == "CONFIRMED"
    assert confirmed.automation_eligible is True
    assert confirmed.automatic_diagnosis_eligible is True
    print("DEINDUSTRIALIZATION_BATCH2A_PERCEPTION_CONTRACT_PASS")


if __name__ == "__main__":
    main()
