"""TDD smoke for the Batch 2A persisted-evidence provenance bridge."""

from __future__ import annotations

from datetime import UTC, datetime

from industrial_ops_agent.agent.diagnosis_runtime import _report_from_model
from industrial_ops_agent.agent.evidence import AgentEvidenceContext, AgentEvidenceItem
from industrial_ops_agent.agent.models import AgentBudget, DiagnosisManifest
from industrial_ops_agent.industrial_recognition.diagnosis_evidence import _result_is_authorized
from industrial_ops_agent.persistence.models import (
    RecognitionCorrectionRecord,
    RecognitionResultRecord,
)


def main() -> None:
    now = datetime.now(UTC)
    recognition = AgentEvidenceItem(
        citation_id="recognition:bundle-1:result-1",
        kind="RECOGNITION",
        title="OCR finding",
        content="ALARM-42",
        content_checksum="sha256:content",
        source_checksum="source-1",
        citation={
            "citation_id": "recognition:bundle-1:result-1",
            "evidence_bundle_id": "bundle-1",
            "recognition_result_id": "result-1",
            "source_id": "ocr-1",
        },
    )
    context = AgentEvidenceContext((recognition,))
    assert context.recognition == (recognition,)
    assert context.knowledge == ()

    manifest = DiagnosisManifest(
        incident_version=1,
        evidence_bundle_id="bundle-1",
        evidence_version=2,
        model_release="model-1",
        prompt_bundle="prompt-1",
        index_release_id="index-1",
        agent_graph_version="graph-1",
        tool_versions={},
        budget=AgentBudget(),
        created_at=now,
        evidence_refs=(recognition.citation,),
        evidence_refs_hash="sha256:refs",
    ).as_dict()
    assert manifest["evidence_refs"] == [recognition.citation]
    assert manifest["evidence_refs_hash"] == "sha256:refs"
    report = _report_from_model(
        {
            "status": "COMPLETED",
            "conclusion": "Alarm confirmed.",
            "citation_ids": [recognition.citation_id],
            "contradictions": [],
            "missing_information": [],
            "next_checks": [],
            "confidence": 0.9,
        },
        [recognition],
    )
    assert report.citations[0]["source_id"] == "ocr-1"
    assert report.citations[0]["evidence_bundle_id"] == "bundle-1"
    result = RecognitionResultRecord(
        result_id="result-rejected",
        tenant_id="tenant-1",
        bundle_id="bundle-1",
        result_type="VISUAL_FINDING",
        ordinal=1,
        payload={"finding_id": "finding-rejected", "label": "noise"},
    )
    correction = RecognitionCorrectionRecord(
        correction_id="correction-1",
        tenant_id="tenant-1",
        bundle_id="bundle-1",
        target_type="FINDING",
        target_id="finding-rejected",
        original_value=None,
        corrected_value=None,
        disposition="REJECTED",
        reviewer_subject_id="reviewer-1",
        occurred_at=now,
        evidence_version=2,
    )
    assert not _result_is_authorized(result, [correction])
    print("BATCH2A2_PROVENANCE_BRIDGE_PASS")


if __name__ == "__main__":
    main()
