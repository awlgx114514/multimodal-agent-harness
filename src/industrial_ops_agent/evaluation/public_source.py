"""Validated, domain-neutral contract for externally sourced evaluation data."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import select

from industrial_ops_agent.auth.identity import IdentityContext
from industrial_ops_agent.auth.policy import Action, Authorizer, ResourceContext
from industrial_ops_agent.data_pipeline.storage import DatasetStore, ImmutableObjectExists
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    PublicEvaluationSourceApprovalRecord,
    PublicEvaluationSourceRecord,
)

PUBLIC_EVALUATION_SOURCE_CONTRACT = "public-vlm-evaluation-source-v1"
_DIGEST_LENGTH = 64


class EvaluationSourceContractError(ValueError):
    pass


class EvaluationSourceReviewDenied(ValueError):
    pass


class EvaluationSourceGovernanceService:
    def __init__(
        self,
        database: Database,
        authorizer: Authorizer,
        store: DatasetStore,
    ) -> None:
        self._database = database
        self._authorizer = authorizer
        self._store = store

    def list_pending_for_review(
        self,
        identity: IdentityContext,
        *,
        request_id: str,
    ) -> list[PublicEvaluationSourceRecord]:
        self._authorizer.require(
            identity,
            Action.REVIEW_PUBLIC_EVALUATION_SOURCE,
            ResourceContext(
                tenant_id=identity.tenant_id,
                resource_id="public-evaluation-source-pending-list",
            ),
            request_id=request_id,
        )
        with self._database.transaction(identity.tenant_context) as session:
            return list(
                session.scalars(
                    select(PublicEvaluationSourceRecord)
                    .where(
                        PublicEvaluationSourceRecord.tenant_id == identity.tenant_id,
                        PublicEvaluationSourceRecord.status == "PENDING_REVIEW",
                    )
                    .order_by(
                        PublicEvaluationSourceRecord.created_at.asc(),
                        PublicEvaluationSourceRecord.source_id.asc(),
                    )
                )
            )

    def get_for_review(
        self,
        identity: IdentityContext,
        source_id: str,
        *,
        request_id: str,
    ) -> tuple[PublicEvaluationSourceRecord, dict[str, Any]]:
        self._authorizer.require(
            identity,
            Action.REVIEW_PUBLIC_EVALUATION_SOURCE,
            ResourceContext(tenant_id=identity.tenant_id, resource_id=source_id),
            request_id=request_id,
        )
        with self._database.transaction(identity.tenant_context) as session:
            source = session.scalar(
                select(PublicEvaluationSourceRecord).where(
                    PublicEvaluationSourceRecord.tenant_id == identity.tenant_id,
                    PublicEvaluationSourceRecord.source_id == source_id,
                )
            )
            if source is None:
                raise EvaluationSourceReviewDenied("evaluation_source_not_visible")
        manifest_bytes = self._store.get_bytes(source.manifest_key)
        if sha256(manifest_bytes).hexdigest() != source.manifest_hash:
            raise EvaluationSourceReviewDenied("evaluation_source_manifest_digest_mismatch")
        try:
            manifest = json.loads(manifest_bytes)
            contract = EvaluationSourceContract.from_manifest(
                manifest,
                manifest_hash=source.manifest_hash,
                source_bytes=manifest_bytes,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, EvaluationSourceContractError) as exc:
            raise EvaluationSourceReviewDenied("evaluation_source_manifest_is_invalid") from exc
        if (
            contract.contract_version != source.contract_version
            or contract.sample_count != source.sample_count
        ):
            raise EvaluationSourceReviewDenied("evaluation_source_record_mismatch")
        return source, manifest

    def submit(
        self,
        identity: IdentityContext,
        manifest: Mapping[str, Any],
        *,
        manifest_bytes: bytes,
        request_id: str,
    ) -> PublicEvaluationSourceRecord:
        manifest_hash = sha256(manifest_bytes).hexdigest()
        contract = EvaluationSourceContract.from_manifest(
            manifest,
            manifest_hash=manifest_hash,
            source_bytes=manifest_bytes,
        )
        self._authorizer.require(
            identity,
            Action.SUBMIT_PUBLIC_EVALUATION_SOURCE,
            ResourceContext(tenant_id=identity.tenant_id, resource_id=manifest_hash),
            request_id=request_id,
        )
        source_id = f"public-source-{uuid4().hex}"
        manifest_key = f"public-evaluation-sources/{source_id}/manifest.json"
        try:
            self._store.put_bytes(manifest_key, manifest_bytes)
        except ImmutableObjectExists as exc:
            raise EvaluationSourceReviewDenied("evaluation_source_manifest_key_conflict") from exc
        now = datetime.now(UTC)
        metadata = {
            "source_name": contract.source_name,
            "source_url": contract.source_url,
            "source_revision": contract.source_revision,
            "archive_sha256": contract.archive_sha256,
            "annotation_sha256": contract.annotation_sha256,
            "license_id": contract.license_id,
            "license_sha256": contract.license_sha256,
            "attribution": contract.attribution,
        }
        with self._database.transaction(identity.tenant_context) as session:
            existing = session.scalar(
                select(PublicEvaluationSourceRecord).where(
                    PublicEvaluationSourceRecord.tenant_id == identity.tenant_id,
                    PublicEvaluationSourceRecord.manifest_hash == manifest_hash,
                )
            )
            if existing is not None:
                raise EvaluationSourceReviewDenied("evaluation_source_manifest_already_submitted")
            record = PublicEvaluationSourceRecord(
                source_id=source_id,
                tenant_id=identity.tenant_id,
                contract_version=contract.contract_version,
                source_metadata=metadata,
                manifest_key=manifest_key,
                manifest_hash=manifest_hash,
                sample_count=contract.sample_count,
                status="PENDING_REVIEW",
                submitted_by_subject_id=identity.subject_id,
                reviewed_by_subject_id=None,
                reviewed_at=None,
                review_reason=None,
                version=1,
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            session.flush()
            return record

    def decide(
        self,
        identity: IdentityContext,
        source_id: str,
        *,
        decision: str,
        reason: str,
        request_id: str,
    ) -> PublicEvaluationSourceRecord:
        if decision not in {"APPROVE", "REJECT"} or not reason.strip() or len(reason) > 2000:
            raise EvaluationSourceReviewDenied("evaluation_source_decision_is_invalid")
        self._authorizer.require(
            identity,
            Action.REVIEW_PUBLIC_EVALUATION_SOURCE,
            ResourceContext(tenant_id=identity.tenant_id, resource_id=source_id),
            request_id=request_id,
        )
        with self._database.transaction(identity.tenant_context) as session:
            source = session.scalar(
                select(PublicEvaluationSourceRecord)
                .where(
                    PublicEvaluationSourceRecord.tenant_id == identity.tenant_id,
                    PublicEvaluationSourceRecord.source_id == source_id,
                )
                .with_for_update()
            )
            if source is None:
                raise EvaluationSourceReviewDenied("evaluation_source_not_visible")
            if source.status != "PENDING_REVIEW":
                raise EvaluationSourceReviewDenied("evaluation_source_is_not_pending_review")
            if source.submitted_by_subject_id == identity.subject_id:
                raise EvaluationSourceReviewDenied("evaluation_source_submitter_cannot_review")
            manifest_bytes = self._store.get_bytes(source.manifest_key)
            if sha256(manifest_bytes).hexdigest() != source.manifest_hash:
                raise EvaluationSourceReviewDenied("evaluation_source_manifest_digest_mismatch")
            manifest = json.loads(manifest_bytes)
            EvaluationSourceContract.from_manifest(
                manifest,
                manifest_hash=source.manifest_hash,
                source_bytes=manifest_bytes,
            )
            now = datetime.now(UTC)
            source.status = "APPROVED" if decision == "APPROVE" else "REJECTED"
            source.reviewed_by_subject_id = identity.subject_id
            source.reviewed_at = now
            source.review_reason = reason.strip()
            source.version += 1
            session.add(
                PublicEvaluationSourceApprovalRecord(
                    approval_id=f"public-source-approval-{uuid4().hex}",
                    tenant_id=identity.tenant_id,
                    source_id=source.source_id,
                    manifest_hash=source.manifest_hash,
                    decision=decision,
                    reason=reason.strip(),
                    decided_by_subject_id=identity.subject_id,
                    decided_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.flush()
            return source


@dataclass(frozen=True, slots=True)
class PublicEvaluationCase:
    source_image_id: str
    image_file: str
    image_sha256: str
    split: str
    expected_findings: tuple[dict[str, Any], ...]
    source_annotation_ids: tuple[str, ...]
    original_annotations: tuple[dict[str, str], ...]


@dataclass(frozen=True, slots=True)
class EvaluationSourceContract:
    contract_version: str
    source_name: str
    source_url: str
    source_revision: str
    archive_sha256: str
    annotation_sha256: dict[str, str]
    license_id: str
    license_sha256: str
    attribution: str
    manifest_hash: str
    sample_count: int
    review_status: str
    formal_suite_id: str | None
    cases: tuple[PublicEvaluationCase, ...]

    @classmethod
    def from_manifest(
        cls,
        manifest: Mapping[str, Any],
        *,
        manifest_hash: str,
        source_bytes: bytes,
    ) -> EvaluationSourceContract:
        if sha256(source_bytes).hexdigest() != manifest_hash:
            raise EvaluationSourceContractError("evaluation_source_manifest_digest_mismatch")
        if not isinstance(manifest, Mapping):
            raise EvaluationSourceContractError("evaluation_source_manifest_is_invalid")
        source = manifest.get("source")
        cases_raw = manifest.get("cases")
        sample_count = manifest.get("sample_count")
        if (
            not isinstance(source, Mapping)
            or not isinstance(cases_raw, list)
            or not cases_raw
            or isinstance(sample_count, bool)
            or not isinstance(sample_count, int)
            or sample_count != len(cases_raw)
            or manifest.get("review_status") != "PENDING_REVIEW"
            or manifest.get("formal_suite_id") is not None
        ):
            raise EvaluationSourceContractError("evaluation_source_manifest_state_is_invalid")

        source_name = _required_text(source, "dataset")
        source_url = _required_text(source, "url")
        parsed_url = urlparse(source_url)
        source_revision = _required_text(source, "revision")
        archive_hash = _required_digest(source.get("archive_sha256"))
        annotation_hashes = source.get("annotation_sha256")
        if (
            parsed_url.scheme != "https"
            or not parsed_url.netloc
            or not isinstance(annotation_hashes, dict)
            or not annotation_hashes
            or any(
                not isinstance(name, str)
                or not name
                or not _valid_digest(value)
                for name, value in annotation_hashes.items()
            )
        ):
            raise EvaluationSourceContractError("evaluation_source_provenance_is_invalid")
        license_id = _required_text(source, "license")
        license_hash = _required_digest(source.get("license_sha256"))
        attribution = _required_text(source, "attribution")

        cases = tuple(_case(value) for value in cases_raw)
        source_image_ids = [item.source_image_id for item in cases]
        image_hashes = [item.image_sha256 for item in cases]
        if len(set(source_image_ids)) != len(source_image_ids):
            raise EvaluationSourceContractError("evaluation_source_image_identity_is_duplicated")
        if len(set(image_hashes)) != len(image_hashes):
            raise EvaluationSourceContractError("evaluation_source_image_content_is_duplicated")

        return cls(
            contract_version=PUBLIC_EVALUATION_SOURCE_CONTRACT,
            source_name=source_name,
            source_url=source_url,
            source_revision=source_revision,
            archive_sha256=archive_hash,
            annotation_sha256=dict(sorted(annotation_hashes.items())),
            license_id=license_id,
            license_sha256=license_hash,
            attribution=attribution,
            manifest_hash=manifest_hash,
            sample_count=sample_count,
            review_status="PENDING_REVIEW",
            formal_suite_id=None,
            cases=cases,
        )


def _case(value: Any) -> PublicEvaluationCase:
    if not isinstance(value, dict):
        raise EvaluationSourceContractError("evaluation_source_case_is_invalid")
    source_image_id = _required_text(value, "source_image_id")
    image_file = _required_text(value, "image_file")
    image_hash = _required_digest(value.get("image_sha256"))
    split = value.get("split")
    findings = value.get("expected_findings")
    source_findings = value.get("findings")
    if (
        split not in {"TRAIN", "TEST"}
        or image_file.startswith(("/", "\\"))
        or ".." in image_file.replace("\\", "/").split("/")
        or not isinstance(findings, list)
        or not findings
        or not isinstance(source_findings, list)
        or len(findings) != len(source_findings)
    ):
        raise EvaluationSourceContractError("evaluation_source_case_is_invalid")
    expected_findings: list[dict[str, Any]] = []
    annotation_ids: list[str] = []
    original_annotations: list[dict[str, str]] = []
    for finding, source_finding in zip(findings, source_findings, strict=True):
        if (
            not isinstance(finding, dict)
            or set(finding) != {"label", "region"}
            or not isinstance(source_finding, dict)
        ):
            raise EvaluationSourceContractError("evaluation_source_finding_is_invalid")
        label = _required_text(finding, "label")
        region = finding.get("region")
        if not isinstance(region, dict) or set(region) != {"x", "y", "width", "height"}:
            raise EvaluationSourceContractError("evaluation_source_region_is_invalid")
        coordinates = {key: _finite_number(region.get(key)) for key in region}
        x, y = coordinates["x"], coordinates["y"]
        width, height = coordinates["width"], coordinates["height"]
        if (
            not 0 <= x < 1
            or not 0 <= y < 1
            or not 0 < width <= 1
            or not 0 < height <= 1
            or x + width > 1
            or y + height > 1
            or source_finding.get("label") != label
        ):
            raise EvaluationSourceContractError("evaluation_source_region_is_invalid")
        annotation_id = _required_text(source_finding, "source_annotation_id")
        original = source_finding.get("original_annotation")
        if not isinstance(original, dict) or not all(
            isinstance(key, str) and isinstance(item, str) for key, item in original.items()
        ):
            raise EvaluationSourceContractError("evaluation_source_original_annotation_is_invalid")
        expected_findings.append({"label": label, "region": dict(coordinates)})
        annotation_ids.append(annotation_id)
        original_annotations.append(dict(original))
    if len(set(annotation_ids)) != len(annotation_ids):
        raise EvaluationSourceContractError("evaluation_source_annotation_identity_is_duplicated")
    return PublicEvaluationCase(
        source_image_id=source_image_id,
        image_file=image_file,
        image_sha256=image_hash,
        split=str(split),
        expected_findings=tuple(expected_findings),
        source_annotation_ids=tuple(annotation_ids),
        original_annotations=tuple(original_annotations),
    )


def _required_text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise EvaluationSourceContractError("evaluation_source_required_text_is_missing")
    return item.strip()


def _required_digest(value: Any) -> str:
    if not _valid_digest(value):
        raise EvaluationSourceContractError("evaluation_source_digest_is_invalid")
    return str(value).lower()


def _valid_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == _DIGEST_LENGTH
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


def _finite_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise EvaluationSourceContractError("evaluation_source_region_is_invalid")
    result = float(value)
    if not math.isfinite(result):
        raise EvaluationSourceContractError("evaluation_source_region_is_invalid")
    return result
