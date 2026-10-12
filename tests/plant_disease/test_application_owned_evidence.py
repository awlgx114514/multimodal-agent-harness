from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest import TestCase

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from industrial_ops_agent.persistence.models import (
    Base,
    EvidenceBundleRecord,
    MediaObjectRecord,
    RecognitionResultRecord,
    TenantRecord,
)


class ApplicationOwnedEvidenceTests(TestCase):
    def test_public_source_finding_persists_under_reference_application_owner(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        manifest_path = (
            repository
            / "artifacts"
            / "plant_disease"
            / "candidates"
            / "plantdoc-source-v2"
            / "plant_disease_gold_v1-600"
            / "manifest.json"
        )
        source_case = json.loads(manifest_path.read_text(encoding="utf-8"))["cases"][0]
        source_finding = source_case["findings"][0]
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        now = datetime.now(UTC)
        with Session(engine) as session:
            session.add(TenantRecord(id="plant-evidence-test", status="ACTIVE"))
            session.flush()
            session.add(
                MediaObjectRecord(
                    media_id="media-plantdoc-source",
                    tenant_id="plant-evidence-test",
                    draft_id=None,
                    application_id="plant_disease",
                    application_context_id=source_case["source_image_id"],
                    quarantine_key="tenant/plant-evidence-test/quarantine/app/plantdoc-source",
                    clean_key="tenant/plant-evidence-test/clean/app/plantdoc-source",
                    content_hash=source_case["image_sha256"],
                    declared_mime=source_case["mime_type"],
                    detected_mime=source_case["mime_type"],
                    size_bytes=source_case["image_size_bytes"],
                    scan_state="CLEAN",
                    scan_version=2,
                    content_credential_status="ABSENT",
                )
            )
            session.flush()
            session.add(
                EvidenceBundleRecord(
                    bundle_id="bundle-plantdoc-source",
                    tenant_id="plant-evidence-test",
                    draft_id=None,
                    asset_id=None,
                    media_id="media-plantdoc-source",
                    context_kind="APPLICATION",
                    application_id="plant_disease",
                    application_context_id=source_case["source_image_id"],
                    source_sha256=source_case["image_sha256"],
                    source_type="IMAGE",
                    processor_versions={"multimodal_processor": "recorded-by-source"},
                    security_findings_json=[],
                    automation_eligible=False,
                    automation_blockers_json=[],
                    status="CONFIRMED",
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.flush()
            session.add(
                RecognitionResultRecord(
                    result_id="result-plantdoc-source",
                    tenant_id="plant-evidence-test",
                    bundle_id="bundle-plantdoc-source",
                    result_type="VISUAL_FINDING",
                    ordinal=0,
                    payload={
                        "finding_id": source_finding["source_annotation_id"],
                        "label": source_finding["label"],
                        "region": source_case["expected_findings"][0]["region"],
                        "original_annotation": source_finding["original_annotation"],
                    },
                )
            )
            session.commit()

        with Session(engine) as session:
            bundle = session.get(EvidenceBundleRecord, "bundle-plantdoc-source")
            finding = session.scalar(
                select(RecognitionResultRecord).where(
                    RecognitionResultRecord.bundle_id == "bundle-plantdoc-source"
                )
            )
            self.assertEqual(bundle.application_id, "plant_disease")
            self.assertEqual(bundle.application_context_id, source_case["source_image_id"])
            self.assertIsNone(bundle.draft_id)
            self.assertIsNone(bundle.asset_id)
            self.assertEqual(
                finding.payload["finding_id"], source_finding["source_annotation_id"]
            )
        engine.dispose()
