from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest import TestCase

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from industrial_ops_agent.auth.identity import IdentityContext, Role
from industrial_ops_agent.auth.policy import Authorizer
from industrial_ops_agent.experiments.service import (
    EvaluationGovernanceService,
    ExperimentGateDenied,
)
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    Base,
    EvaluationGovernanceApprovalRecord,
    EvaluationPolicyRecord,
    EvaluationSuiteRecord,
    TenantRecord,
)
from industrial_ops_agent.security_audit import InMemorySecurityAuditSink, SecurityAuditor


class EvaluationGovernanceTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.database = Database.from_engine(self.engine)
        now = datetime.now(UTC)
        self.submitter = IdentityContext(
            subject_id="evaluation-submitter",
            oidc_subject="evaluation-submitter",
            tenant_id="evaluation-tenant",
            roles=frozenset({Role.MODEL_EVALUATOR, Role.MODEL_RELEASE_APPROVER}),
            asset_ids=frozenset(),
            site_ids=frozenset(),
            issued_at=now,
            expires_at=now + timedelta(minutes=5),
        )
        self.reviewer = _identity("evaluation-reviewer", Role.MODEL_RELEASE_APPROVER, now)
        self.service = EvaluationGovernanceService(
            self.database,
            Authorizer(
                SecurityAuditor(InMemorySecurityAuditSink(), hash_key=b"evaluation-review-key")
            ),
        )
        with Session(self.engine) as session:
            session.add(TenantRecord(id="evaluation-tenant", status="ACTIVE"))
            session.add(
                EvaluationSuiteRecord(
                    suite_id="suite-1",
                    tenant_id="evaluation-tenant",
                    name="PlantDoc GOLD",
                    version="1",
                    source_snapshot_id="snapshot-1",
                    tier="GOLD",
                    purpose="EVALUATION_ONLY",
                    status="DRAFT",
                    manifest_hash="a" * 64,
                    sample_count=600,
                    slice_counts={"all": 600},
                    created_by_subject_id=self.submitter.subject_id,
                )
            )
            session.add(
                EvaluationPolicyRecord(
                    policy_id="policy-1",
                    tenant_id="evaluation-tenant",
                    name="PlantDoc policy",
                    version="1",
                    status="DRAFT",
                    primary_metric="finding_f1",
                    hard_gates={"structured_output_valid": True},
                    thresholds={"finding_f1": 0.8},
                    policy_hash="b" * 64,
                    created_by_subject_id=self.submitter.subject_id,
                )
            )
            session.commit()

    def tearDown(self) -> None:
        self.database.dispose()

    def test_suite_requires_independent_review_of_submitted_digest(self) -> None:
        submitted = self.service.submit_suite(
            self.submitter, "suite-1", request_id="suite-submit"
        )
        self.assertEqual(submitted.status, "SUBMITTED")
        self.assertEqual(len(submitted.governance_digest), 64)
        with self.assertRaisesRegex(ExperimentGateDenied, "submitter_cannot_review"):
            self.service.decide_suite(
                self.submitter,
                "suite-1",
                decision="APPROVE",
                reason="Review complete.",
                request_id="suite-self-review",
            )
        with Session(self.engine) as session:
            record = session.scalar(select(EvaluationSuiteRecord))
            record.sample_count = 601
            session.commit()
        with self.assertRaisesRegex(ExperimentGateDenied, "digest_mismatch"):
            self.service.decide_suite(
                self.reviewer,
                "suite-1",
                decision="APPROVE",
                reason="Review complete.",
                request_id="suite-digest-review",
            )
        with Session(self.engine) as session:
            self.assertEqual(
                session.scalar(select(EvaluationGovernanceApprovalRecord)), None
            )

    def test_policy_decision_records_digest_and_reviewer(self) -> None:
        self.service.submit_policy(
            self.submitter, "policy-1", request_id="policy-submit"
        )
        approved = self.service.decide_policy(
            self.reviewer,
            "policy-1",
            decision="APPROVE",
            reason="Thresholds and hard gates reviewed.",
            request_id="policy-review",
        )
        self.assertEqual(approved.status, "ACTIVE")
        self.assertEqual(approved.reviewed_by_subject_id, self.reviewer.subject_id)
        with Session(self.engine) as session:
            decision = session.scalar(select(EvaluationGovernanceApprovalRecord))
            self.assertEqual(decision.resource_kind, "POLICY")
            self.assertEqual(decision.resource_digest, "b" * 64)
            self.assertEqual(decision.decided_by_subject_id, self.reviewer.subject_id)


def _identity(subject_id: str, role: Role, now: datetime) -> IdentityContext:
    return IdentityContext(
        subject_id=subject_id,
        oidc_subject=subject_id,
        tenant_id="evaluation-tenant",
        roles=frozenset({role}),
        asset_ids=frozenset(),
        site_ids=frozenset(),
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
    )
