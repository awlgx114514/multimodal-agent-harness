"""Industrial Diagnosis adapter for resolving persisted recognition evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from industrial_ops_agent.agent.evidence import AgentEvidenceContext, AgentEvidenceItem
from industrial_ops_agent.auth.identity import IdentityContext
from industrial_ops_agent.auth.policy import Action, Authorizer, ResourceContext
from industrial_ops_agent.model_gateway.context_manifest import canonical_sha256
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    EvidenceBundleRecord,
    RecognitionCorrectionRecord,
    RecognitionResultRecord,
)
from industrial_ops_agent.persistence.repositories import EvidenceBundleRepository
from industrial_ops_agent.persistence.tenant import TenantContext

_SOURCE_FIELDS = {
    "OCR_BLOCK": "block_id",
    "ASR_SEGMENT": "segment_id",
    "ENTITY": "entity_id",
    "VISUAL_FINDING": "finding_id",
    "VIDEO_KEYFRAME": "frame_id",
    "VIDEO_EVENT": "event_id",
    "QR_CODE": "candidate_id",
}


class DiagnosisEvidenceResolutionError(RuntimeError):
    """Persisted recognition evidence cannot satisfy a manifest reference."""


@dataclass(frozen=True, slots=True)
class RecognitionCitationView:
    citation_id: str
    title: str
    content_excerpt: str
    source_checksum: str
    evidence_bundle_id: str
    evidence_version: int
    recognition_result_id: str
    result_type: str
    source_id: str
    media_id: str
    result_hash: str
    source_frame_id: str | None = None
    finding_id: str | None = None


class RecognitionCitationResolver:
    """Resolve a confirmed, currently authorized recognition citation."""

    def __init__(self, database: Database, authorizer: Authorizer) -> None:
        self._database = database
        self._authorizer = authorizer

    def resolve(
        self,
        identity: IdentityContext,
        citation_id: str,
        *,
        request_id: str,
    ) -> RecognitionCitationView:
        prefix = "recognition:"
        if not citation_id.startswith(prefix):
            raise DiagnosisEvidenceResolutionError("diagnosis_evidence_reference_invalid")
        bundle_id, separator, result_id = citation_id[len(prefix) :].partition(":")
        if not separator or not bundle_id or not result_id:
            raise DiagnosisEvidenceResolutionError("diagnosis_evidence_reference_invalid")

        self._authorizer.require(
            identity,
            Action.READ_CITATION,
            ResourceContext(tenant_id=identity.tenant_id, resource_id=citation_id),
            request_id=request_id,
        )
        context = identity.tenant_context
        with self._database.transaction(context) as session:
            bundle = EvidenceBundleRepository(session, context).get(bundle_id)
        if (
            bundle is None
            or bundle.status != "CONFIRMED"
            or bundle.context_kind != "INCIDENT_DRAFT"
            or bundle.draft_id is None
            or bundle.asset_id is None
        ):
            raise DiagnosisEvidenceResolutionError("diagnosis_evidence_binding_invalid")

        self._authorizer.require(
            identity,
            Action.READ_ASSET,
            ResourceContext(
                tenant_id=identity.tenant_id,
                resource_id=bundle.asset_id,
                asset_id=bundle.asset_id,
            ),
            request_id=request_id,
        )

        with self._database.transaction(context) as session:
            current_bundle = EvidenceBundleRepository(session, context).get(bundle_id)
            result = session.scalar(
                select(RecognitionResultRecord).where(
                    RecognitionResultRecord.tenant_id == context.tenant_id,
                    RecognitionResultRecord.bundle_id == bundle_id,
                    RecognitionResultRecord.result_id == result_id,
                )
            )
            if (
                current_bundle is None
                or current_bundle.status != "CONFIRMED"
                or current_bundle.version != bundle.version
                or result is None
            ):
                raise DiagnosisEvidenceResolutionError("diagnosis_evidence_binding_invalid")
            corrections = EvidenceBundleRepository(session, context).list_corrections(bundle_id)
            reference = _evidence_ref(current_bundle, result)
            if reference["citation_id"] != citation_id:
                raise DiagnosisEvidenceResolutionError("diagnosis_evidence_reference_invalid")
            item = _resolve_item(
                current_bundle,
                {result.result_id: result},
                corrections,
                reference,
                current_bundle.version,
            )

        return RecognitionCitationView(
            citation_id=item.citation_id,
            title=item.title,
            content_excerpt=item.content,
            source_checksum=current_bundle.source_sha256,
            evidence_bundle_id=current_bundle.bundle_id,
            evidence_version=current_bundle.version,
            recognition_result_id=result.result_id,
            result_type=result.result_type,
            source_id=str(item.citation["source_id"]),
            media_id=current_bundle.media_id,
            result_hash=str(item.citation["result_hash"]),
            source_frame_id=(
                str(item.citation["source_frame_id"])
                if item.citation.get("source_frame_id") is not None
                else None
            ),
            finding_id=(
                str(item.citation["finding_id"])
                if item.citation.get("finding_id") is not None
                else None
            ),
        )


def build_evidence_refs(
    session: Session,
    context: TenantContext,
    bundle: EvidenceBundleRecord,
) -> tuple[dict[str, Any], ...]:
    repository = EvidenceBundleRepository(session, context)
    results = repository.list_results(bundle.bundle_id)
    corrections = repository.list_corrections(bundle.bundle_id)
    return tuple(
        _evidence_ref(bundle, result)
        for result in results
        if _result_is_authorized(result, corrections)
    )


class DiagnosisEvidenceResolver:
    """Resolve only confirmed, tenant-bound recognition rows named by a manifest."""

    def resolve(
        self,
        database: Database,
        context: TenantContext,
        manifest: dict[str, Any],
    ) -> AgentEvidenceContext:
        bundle_id = manifest.get("evidence_bundle_id")
        expected_version = manifest.get("evidence_version")
        if not isinstance(bundle_id, str) or not isinstance(expected_version, int):
            raise DiagnosisEvidenceResolutionError("diagnosis_manifest_evidence_binding_invalid")
        raw_refs = manifest.get("evidence_refs")
        with database.transaction(context) as session:
            bundle = EvidenceBundleRepository(session, context).get(bundle_id)
            if (
                bundle is None
                or bundle.status != "CONFIRMED"
                or bundle.version != expected_version
            ):
                raise DiagnosisEvidenceResolutionError("diagnosis_evidence_binding_invalid")
            refs = (
                build_evidence_refs(session, context, bundle)
                if raw_refs is None
                else _validated_refs(raw_refs)
            )
            if raw_refs is not None and manifest.get("evidence_refs_hash") != _refs_hash(refs):
                raise DiagnosisEvidenceResolutionError("diagnosis_manifest_evidence_hash_invalid")
            corrections = EvidenceBundleRepository(session, context).list_corrections(bundle_id)
            results = {
                result.result_id: result
                for result in EvidenceBundleRepository(session, context).list_results(bundle_id)
            }
            items = tuple(
                _resolve_item(bundle, results, corrections, ref, expected_version)
                for ref in refs
            )
        return AgentEvidenceContext(items)


def _validated_refs(raw_refs: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(raw_refs, list) or any(not isinstance(item, dict) for item in raw_refs):
        raise DiagnosisEvidenceResolutionError("diagnosis_manifest_evidence_refs_invalid")
    return tuple(dict(item) for item in raw_refs)


def _refs_hash(refs: tuple[dict[str, Any], ...]) -> str:
    canonical = json.dumps(list(refs), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return sha256(canonical.encode()).hexdigest()


def _evidence_ref(
    bundle: EvidenceBundleRecord,
    result: RecognitionResultRecord,
) -> dict[str, Any]:
    source_id = _source_id(result)
    return {
        "citation_id": f"recognition:{bundle.bundle_id}:{result.result_id}",
        "evidence_bundle_id": bundle.bundle_id,
        "evidence_version": bundle.version,
        "recognition_result_id": result.result_id,
        "result_type": result.result_type,
        "ordinal": result.ordinal,
        "media_id": bundle.media_id,
        "source_sha256": bundle.source_sha256,
        "source_id": source_id,
        "result_hash": canonical_sha256(result.payload),
    }


def _resolve_item(
    bundle: EvidenceBundleRecord,
    results: dict[str, RecognitionResultRecord],
    corrections: list[RecognitionCorrectionRecord],
    ref: dict[str, Any],
    expected_version: int,
) -> AgentEvidenceItem:
    result_id = ref.get("recognition_result_id")
    result = results.get(result_id) if isinstance(result_id, str) else None
    if result is None or result.bundle_id != bundle.bundle_id:
        raise DiagnosisEvidenceResolutionError("diagnosis_evidence_result_missing")
    if not _result_is_authorized(result, corrections):
        raise DiagnosisEvidenceResolutionError("diagnosis_evidence_not_authorized")
    actual = _evidence_ref(bundle, result)
    if any(ref.get(key) != actual[key] for key in actual):
        raise DiagnosisEvidenceResolutionError("diagnosis_evidence_reference_mismatch")
    if ref.get("evidence_version") != expected_version:
        raise DiagnosisEvidenceResolutionError("diagnosis_evidence_version_mismatch")
    content = _content(result.result_type, _effective_payload(result, corrections))
    citation = {
        "citation_id": actual["citation_id"],
        "evidence_kind": "RECOGNITION",
        "evidence_bundle_id": bundle.bundle_id,
        "evidence_version": bundle.version,
        "recognition_result_id": result.result_id,
        "result_type": result.result_type,
        "source_id": actual["source_id"],
        "media_id": bundle.media_id,
        "source_sha256": bundle.source_sha256,
        "result_hash": actual["result_hash"],
    }
    source_frame_id = result.payload.get("source_frame_id")
    if source_frame_id is not None:
        citation["source_frame_id"] = str(source_frame_id)
    if result.result_type == "VISUAL_FINDING":
        citation["finding_id"] = str(result.payload["finding_id"])
    return AgentEvidenceItem(
        citation_id=actual["citation_id"],
        kind="RECOGNITION",
        title=_title(result.result_type, result.payload),
        content=content,
        content_checksum=canonical_sha256({"content": content}),
        source_checksum=bundle.source_sha256,
        citation=citation,
    )


def _result_is_authorized(
    result: RecognitionResultRecord,
    corrections: list[RecognitionCorrectionRecord],
) -> bool:
    payload = result.payload
    target_type = {
        "OCR_BLOCK": "OCR_BLOCK",
        "ASR_SEGMENT": "ASR_SEGMENT",
        "ENTITY": "ENTITY",
        "VISUAL_FINDING": "FINDING",
        "VIDEO_EVENT": "VIDEO_EVENT",
        "QR_CODE": "QR_CODE",
    }.get(result.result_type)
    source_field = _SOURCE_FIELDS.get(result.result_type)
    source_id = payload.get(source_field) if source_field else None
    if not isinstance(source_id, str):
        return False
    latest = _latest_correction(corrections, target_type, source_id)
    if latest is not None and latest.disposition == "REJECTED":
        return False
    if result.result_type == "ENTITY":
        return payload.get("validation_status") == "VALID" or (
            latest is not None and bool(latest.corrected_value)
        )
    return True


def _latest_correction(
    corrections: list[RecognitionCorrectionRecord],
    target_type: str | None,
    target_id: str,
) -> RecognitionCorrectionRecord | None:
    if target_type is None:
        return None
    matches = [
        item
        for item in corrections
        if item.target_type == target_type and item.target_id == target_id
    ]
    return matches[-1] if matches else None


def _effective_payload(
    result: RecognitionResultRecord,
    corrections: list[RecognitionCorrectionRecord],
) -> dict[str, Any]:
    payload = dict(result.payload)
    target_type = {
        "OCR_BLOCK": "OCR_BLOCK",
        "ASR_SEGMENT": "ASR_SEGMENT",
        "ENTITY": "ENTITY",
        "QR_CODE": "QR_CODE",
    }.get(result.result_type)
    source_field = _SOURCE_FIELDS.get(result.result_type)
    source_id = payload.get(source_field) if source_field else None
    if target_type is None or not isinstance(source_id, str):
        return payload
    correction = _latest_correction(corrections, target_type, source_id)
    if correction is not None and correction.corrected_value:
        field = "value" if result.result_type == "ENTITY" else "text"
        payload[field] = correction.corrected_value
    return payload


def _source_id(result: RecognitionResultRecord) -> str:
    field = _SOURCE_FIELDS.get(result.result_type)
    value = result.payload.get(field) if field else None
    if not isinstance(value, str) or not value.strip():
        raise DiagnosisEvidenceResolutionError("diagnosis_evidence_source_id_missing")
    return value


def _content(result_type: str, payload: dict[str, Any]) -> str:
    for field in ("text", "description", "value", "label"):
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            return value[:2_000]
    source_id = payload.get(_SOURCE_FIELDS.get(result_type, ""), "")
    return f"{result_type} {source_id}"[:2_000]


def _title(result_type: str, payload: dict[str, Any]) -> str:
    label = payload.get("label")
    if result_type == "VISUAL_FINDING" and isinstance(label, str) and label.strip():
        return f"Visual finding: {label[:160]}"
    return f"Recognition evidence: {result_type}"
