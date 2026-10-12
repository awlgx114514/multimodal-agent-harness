from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from industrial_ops_agent.auth.identity import IdentityContext, Role
from industrial_ops_agent.auth.policy import Authorizer
from industrial_ops_agent.data_pipeline.storage import FilesystemDatasetStore
from industrial_ops_agent.evaluation.public_source import (
    EvaluationSourceGovernanceService,
    EvaluationSourceReviewDenied,
)
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    Base,
    PublicEvaluationSourceApprovalRecord,
    PublicEvaluationSourceRecord,
    TenantRecord,
)
from industrial_ops_agent.security_audit import InMemorySecurityAuditSink, SecurityAuditor


class PublicEvaluationSourceGovernanceTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.database = Database.from_engine(self.engine)
        now = datetime.now(UTC)
        self.submitter = _identity("source-submitter", Role.MODEL_EVALUATOR, now)
        self.reviewer = _identity("source-reviewer", Role.MODEL_RELEASE_APPROVER, now)
        self.dual_role_identity = IdentityContext(
            subject_id="source-dual-role",
            oidc_subject="source-dual-role",
            tenant_id="source-tenant",
            roles=frozenset({Role.MODEL_EVALUATOR, Role.MODEL_RELEASE_APPROVER}),
            asset_ids=frozenset(),
            site_ids=frozenset(),
            issued_at=now,
            expires_at=now + timedelta(minutes=5),
        )
        with Session(self.engine) as session:
            session.add(TenantRecord(id="source-tenant", status="ACTIVE"))
            session.commit()
        repository = Path(__file__).resolve().parents[2]
        candidate = (
            repository
            / "artifacts"
            / "plant_disease"
            / "candidates"
            / "plantdoc-source-v2"
            / "plant_disease_gold_v1-600"
            / "manifest.json"
        )
        self.manifest_bytes = candidate.read_bytes()
        self.manifest = json.loads(self.manifest_bytes)
        self.manifest_hash = sha256(self.manifest_bytes).hexdigest()
        self.temporary_directory = TemporaryDirectory(prefix="public-evaluation-source-")
        self.addCleanup(self.temporary_directory.cleanup)
        self.store_root = Path(self.temporary_directory.name)
        self.store = FilesystemDatasetStore(self.store_root)
        self.service = EvaluationSourceGovernanceService(
            self.database,
            self._authorizer(),
            self.store,
        )

    def tearDown(self) -> None:
        self.database.dispose()

    def test_submission_persists_source_pending_and_does_not_create_suite(self) -> None:
        source = self.service.submit(
            self.submitter,
            self.manifest,
            manifest_bytes=self.manifest_bytes,
            request_id="source-submit-request",
        )

        self.assertEqual(source.status, "PENDING_REVIEW")
        self.assertEqual(source.manifest_hash, self.manifest_hash)
        self.assertEqual(source.sample_count, 600)
        self.assertIsNone(source.reviewed_by_subject_id)
        with Session(self.engine) as session:
            self.assertEqual(
                session.scalar(select(PublicEvaluationSourceApprovalRecord)), None
            )

    def test_reviewer_can_inspect_pending_source_and_verified_manifest(self) -> None:
        source = self.service.submit(
            self.submitter,
            self.manifest,
            manifest_bytes=self.manifest_bytes,
            request_id="source-submit-request",
        )

        pending = self.service.list_pending_for_review(
            self.reviewer,
            request_id="source-review-list-request",
        )
        inspected_source, inspected_manifest = self.service.get_for_review(
            self.reviewer,
            source.source_id,
            request_id="source-review-manifest-request",
        )

        self.assertEqual([item.source_id for item in pending], [source.source_id])
        self.assertEqual(inspected_source.manifest_hash, self.manifest_hash)
        self.assertEqual(inspected_manifest, self.manifest)

    def test_reviewer_must_be_independent_and_record_a_decision(self) -> None:
        source = self.service.submit(
            self.dual_role_identity,
            self.manifest,
            manifest_bytes=self.manifest_bytes,
            request_id="source-submit-request",
        )

        with self.assertRaises(EvaluationSourceReviewDenied):
            self.service.decide(
                self.dual_role_identity,
                source.source_id,
                decision="APPROVE",
                reason="Source verified.",
                request_id="source-self-approval",
            )

        reviewed = self.service.decide(
            self.reviewer,
            source.source_id,
            decision="APPROVE",
            reason="Pinned public source and annotation provenance reviewed.",
            request_id="source-review-request",
        )

        self.assertEqual(reviewed.status, "APPROVED")
        self.assertEqual(reviewed.reviewed_by_subject_id, self.reviewer.subject_id)
        with Session(self.engine) as session:
            approvals = list(session.scalars(select(PublicEvaluationSourceApprovalRecord)))
            self.assertEqual(len(approvals), 1)
            self.assertEqual(approvals[0].decision, "APPROVE")

    def test_decision_rechecks_stored_manifest_digest(self) -> None:
        source = self.service.submit(
            self.submitter,
            self.manifest,
            manifest_bytes=self.manifest_bytes,
            request_id="source-submit-request",
        )
        (self.store_root / source.manifest_key).write_bytes(b"changed source manifest")

        with self.assertRaises(EvaluationSourceReviewDenied):
            self.service.decide(
                self.reviewer,
                source.source_id,
                decision="APPROVE",
                reason="Source verified.",
                request_id="source-review-request",
            )

        with Session(self.engine) as session:
            persisted = session.get(PublicEvaluationSourceRecord, source.source_id)
            self.assertEqual(persisted.status, "PENDING_REVIEW")

    def _authorizer(self) -> Authorizer:
        return Authorizer(
            SecurityAuditor(InMemorySecurityAuditSink(), hash_key=b"source-review-test-key")
        )


def _identity(subject_id: str, role: Role, now: datetime) -> IdentityContext:
    return IdentityContext(
        subject_id=subject_id,
        oidc_subject=subject_id,
        tenant_id="source-tenant",
        roles=frozenset({role}),
        asset_ids=frozenset(),
        site_ids=frozenset(),
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
    )
