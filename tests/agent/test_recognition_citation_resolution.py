from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from industrial_ops_agent.application.citations import (
    CitationNotVisible,
    CitationResolution,
    CitationResolver,
)
from industrial_ops_agent.auth.errors import AuthorizationDenied
from industrial_ops_agent.auth.identity import IdentityContext, Role
from industrial_ops_agent.auth.policy import Authorizer
from industrial_ops_agent.industrial_recognition.diagnosis_evidence import (
    DiagnosisEvidenceResolutionError,
    RecognitionCitationResolver,
)
from industrial_ops_agent.knowledge.models import CitationView
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    AssetRecord,
    Base,
    EvidenceBundleRecord,
    IncidentDraftRecord,
    MediaObjectRecord,
    RecognitionCorrectionRecord,
    RecognitionResultRecord,
    TenantRecord,
)
from industrial_ops_agent.security_audit import InMemorySecurityAuditSink, SecurityAuditor


class RecognitionCitationResolverTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.database = Database.from_engine(self.engine)
        self.now = datetime(2026, 10, 3, tzinfo=UTC)
        self.identity = IdentityContext(
            subject_id="subject-citation",
            oidc_subject="subject-citation",
            tenant_id="tenant-citation",
            roles=frozenset({Role.AFTER_SALES_ENGINEER}),
            asset_ids=frozenset({"asset-citation"}),
            site_ids=frozenset(),
            issued_at=self.now,
            expires_at=self.now + timedelta(minutes=5),
        )
        with Session(self.engine) as session:
            session.add(TenantRecord(id="tenant-citation", status="ACTIVE"))
            session.flush()
            session.add(
                AssetRecord(
                    asset_id="asset-citation",
                    tenant_id="tenant-citation",
                    source_system="test",
                    source_record_id="asset-citation",
                    model_code="MODEL-1",
                    version=1,
                )
            )
            session.flush()
            session.add(
                IncidentDraftRecord(
                    draft_id="draft-citation",
                    tenant_id="tenant-citation",
                    asset_id="asset-citation",
                    author_subject_id="subject-citation",
                    description="test incident",
                    version=1,
                    status="SUBMITTED",
                )
            )
            session.flush()
            session.add(
                MediaObjectRecord(
                    media_id="media-citation",
                    tenant_id="tenant-citation",
                    draft_id="draft-citation",
                    quarantine_key="tenant/draft/media/quarantine/source",
                    clean_key="tenant/draft/media/clean/source",
                    content_hash="a" * 64,
                    declared_mime="image/jpeg",
                    detected_mime="image/jpeg",
                    size_bytes=32,
                    scan_state="CLEAN",
                    scan_version=1,
                    content_credential_status="ABSENT",
                )
            )
            session.flush()
            session.add(
                EvidenceBundleRecord(
                    bundle_id="bundle-citation",
                    tenant_id="tenant-citation",
                    draft_id="draft-citation",
                    asset_id="asset-citation",
                    media_id="media-citation",
                    source_sha256="b" * 64,
                    source_type="IMAGE",
                    processor_versions={"test": "1"},
                    security_findings_json=[],
                    automation_eligible=True,
                    automation_blockers_json=[],
                    status="CONFIRMED",
                    version=3,
                )
            )
            session.flush()
            session.add(
                RecognitionResultRecord(
                    result_id="result-citation",
                    tenant_id="tenant-citation",
                    bundle_id="bundle-citation",
                    result_type="VISUAL_FINDING",
                    ordinal=0,
                    payload={
                        "finding_id": "finding-citation",
                        "label": "crack",
                        "description": "A visible crack",
                        "internal_raw_payload": "must not be returned",
                    },
                )
            )
            session.commit()

    def tearDown(self) -> None:
        self.database.dispose()

    def _authorizer(self) -> Authorizer:
        return Authorizer(
            SecurityAuditor(InMemorySecurityAuditSink(), hash_key=b"citation-test-key")
        )

    def test_resolves_confirmed_finding_with_minimal_source_provenance(self) -> None:
        citation = RecognitionCitationResolver(
            self.database, self._authorizer()
        ).resolve(
            self.identity,
            "recognition:bundle-citation:result-citation",
            request_id="request-citation",
        )

        self.assertEqual(citation.citation_id, "recognition:bundle-citation:result-citation")
        self.assertEqual(citation.title, "Visual finding: crack")
        self.assertEqual(citation.content_excerpt, "A visible crack")
        self.assertEqual(citation.evidence_version, 3)
        self.assertEqual(citation.source_id, "finding-citation")
        self.assertNotIn("internal_raw_payload", repr(citation))

    def test_rejects_finding_marked_rejected_after_confirmation(self) -> None:
        with Session(self.engine) as session:
            session.add(
                RecognitionCorrectionRecord(
                    correction_id="correction-citation",
                    tenant_id="tenant-citation",
                    bundle_id="bundle-citation",
                    target_type="FINDING",
                    target_id="finding-citation",
                    original_value="A visible crack",
                    corrected_value=None,
                    disposition="REJECTED",
                    reviewer_subject_id="subject-citation",
                    occurred_at=self.now,
                    evidence_version=3,
                )
            )
            session.commit()

        with self.assertRaises(DiagnosisEvidenceResolutionError):
            RecognitionCitationResolver(
                self.database, self._authorizer()
            ).resolve(
                self.identity,
                "recognition:bundle-citation:result-citation",
                request_id="request-citation",
            )

    def test_enforces_asset_scope_for_recognition_citation(self) -> None:
        other_asset_identity = IdentityContext(
            subject_id="subject-citation",
            oidc_subject="subject-citation",
            tenant_id="tenant-citation",
            roles=frozenset({Role.AFTER_SALES_ENGINEER}),
            asset_ids=frozenset(),
            site_ids=frozenset(),
            issued_at=self.now,
            expires_at=self.now + timedelta(minutes=5),
        )

        with self.assertRaises(AuthorizationDenied):
            RecognitionCitationResolver(
                self.database, self._authorizer()
            ).resolve(
                other_asset_identity,
                "recognition:bundle-citation:result-citation",
                request_id="request-citation",
            )

    def test_rejects_unconfirmed_bundle(self) -> None:
        with Session(self.engine) as session:
            bundle = session.get(EvidenceBundleRecord, "bundle-citation")
            self.assertIsNotNone(bundle)
            bundle.status = "READY_FOR_CONFIRMATION"  # type: ignore[union-attr]
            session.commit()

        with self.assertRaises(DiagnosisEvidenceResolutionError):
            RecognitionCitationResolver(
                self.database, self._authorizer()
            ).resolve(
                self.identity,
                "recognition:bundle-citation:result-citation",
                request_id="request-citation",
            )

    def test_application_citation_boundary_dispatches_recognition_source(self) -> None:
        resolved = CitationResolver(
            self.database, self._authorizer()
        ).resolve(
            self.identity,
            "recognition:bundle-citation:result-citation",
            request_id="request-citation",
        )

        self.assertEqual(resolved.source_type, "RECOGNITION")
        self.assertEqual(
            resolved.citation.citation_id,
            "recognition:bundle-citation:result-citation",
        )

    def test_application_citation_boundary_hides_unavailable_sources(self) -> None:
        with self.assertRaises(CitationNotVisible):
            CitationResolver(self.database, self._authorizer()).resolve(
                self.identity,
                "recognition:missing-bundle:missing-result",
                request_id="request-citation",
            )

    def test_resolved_recognition_citation_keeps_original_expert_report_reference(self) -> None:
        resolved = CitationResolver(self.database, self._authorizer()).resolve(
            self.identity,
            "recognition:bundle-citation:result-citation",
            request_id="request-citation",
        )

        self.assertEqual(
            resolved.expert_reference(),
            {
                "citation_id": "recognition:bundle-citation:result-citation",
                "evidence_kind": "RECOGNITION",
                "evidence_bundle_id": "bundle-citation",
                "evidence_version": 3,
                "recognition_result_id": "result-citation",
                "result_type": "VISUAL_FINDING",
                "source_id": "finding-citation",
                "media_id": "media-citation",
                "source_sha256": "b" * 64,
                "result_hash": (
                    "sha256:738f4014e229a11effe30f5e2c92c9f3e5b9932b7355c8c56682b0a31969b7ab"
                ),
                "finding_id": "finding-citation",
            },
        )

    def test_knowledge_expert_reference_retains_existing_fields(self) -> None:
        citation = CitationView(
            citation_id="knowledge:citation-1",
            document_id="document-1",
            document_version_id="version-1",
            document_version=2,
            chunk_id="chunk-1",
            title="Manual",
            source_uri="managed://manual",
            source_checksum="source-hash",
            content_checksum="content-hash",
            content_excerpt="Existing excerpt",
            page_number=4,
            bounding_box=None,
            start_offset=10,
            end_offset=25,
        )

        reference = CitationResolution("KNOWLEDGE", citation, None).expert_reference()

        self.assertEqual(
            reference,
            {
                "citation_id": "knowledge:citation-1",
                "chunk_id": "chunk-1",
                "document_id": "document-1",
                "document_version_id": "version-1",
                "document_version": 2,
                "title": "Manual",
                "source_checksum": "source-hash",
                "content_checksum": "content-hash",
                "page_number": 4,
            },
        )
