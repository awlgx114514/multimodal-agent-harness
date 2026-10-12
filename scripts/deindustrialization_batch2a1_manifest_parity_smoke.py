"""Application-level Batch 2A.1 parity audit for persisted recognition evidence.

This is intentionally a production-service smoke: it invokes RecognitionService
and DiagnosisService against production SQLAlchemy records, then reopens the
stored bundle and diagnosis manifest.  It does not import the FastAPI app.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, cast

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from industrial_ops_agent.agent.contracts import (
    DIAGNOSIS_AGENT_PROMPT_ID,
    DIAGNOSIS_GRAPH_VERSION,
    DIAGNOSIS_READONLY_TOOLS,
)
from industrial_ops_agent.agent.diagnosis_runtime import DiagnosisRuntime
from industrial_ops_agent.application.diagnoses import DiagnosisService, DiagnosisWorkflowInput
from industrial_ops_agent.application.incidents import RecognitionService
from industrial_ops_agent.auth.identity import IdentityContext, Role
from industrial_ops_agent.auth.policy import Authorizer
from industrial_ops_agent.industrial_recognition.diagnosis_evidence import (
    DiagnosisEvidenceResolutionError,
    DiagnosisEvidenceResolver,
)
from industrial_ops_agent.industrial_recognition.evidence import FindingDisposition
from industrial_ops_agent.model_gateway.service import ResolvedModel
from industrial_ops_agent.multimodal.models import BoundingBox, OcrBlock, VisualFinding
from industrial_ops_agent.multimodal.processor import MultimodalProcessor
from industrial_ops_agent.multimodal.providers import OcrProviderResult, VlmProviderResult
from industrial_ops_agent.object_store.keys import TenantObjectKey, clean_object_key
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    AssetRecord,
    Base,
    DiagnosisRunRecord,
    IncidentDraftRecord,
    IncidentRecord,
    IndexReleaseRecord,
    MediaObjectRecord,
    RecognitionRunRecord,
    SubjectRecord,
    TenantRecord,
)
from industrial_ops_agent.persistence.tenant import TenantContext
from industrial_ops_agent.prompting.registry import default_prompt_registry

TENANT_ID = "tenant-batch2a1"
SUBJECT_ID = "subject-batch2a1"
ASSET_ID = "asset-batch2a1"
DRAFT_ID = "draft-batch2a1"
MEDIA_ID = "media-batch2a1"
RECOGNITION_RUN_ID = "recognition-batch2a1"
INCIDENT_ID = "incident-batch2a1"
INDEX_RELEASE_ID = "index-batch2a1"


class _AuditSink:
    def record(self, **_: Any) -> None:
        return None


class _Store:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    async def put(self, _: TenantContext, key: TenantObjectKey, content: bytes) -> None:
        self.values[key.value] = content

    async def get(self, _: TenantContext, key: TenantObjectKey) -> bytes | None:
        return self.values.get(key.value)

    async def delete(self, _: TenantContext, key: TenantObjectKey) -> None:
        self.values.pop(key.value, None)


class _Ocr:
    async def recognize(
        self,
        _: bytes,
        *,
        mime_type: str,
        tenant_id: str,
        subject_id: str,
        trace_id: str,
        source_id: str,
        business_run_id: str | None = None,
    ) -> OcrProviderResult:
        del mime_type, tenant_id, subject_id, trace_id, source_id, business_run_id
        return OcrProviderResult(
            blocks=(
                OcrBlock(
                    block_id="ocr-alarm-42",
                    page_number=1,
                    text="ALARM-42",
                    bbox=BoundingBox(0.1, 0.1, 0.2, 0.1),
                    confidence=0.98,
                ),
            ),
            processor_version="ocr-batch2a1",
        )


class _Vlm:
    async def inspect(
        self,
        _: bytes,
        *,
        mime_type: str,
        instruction: str,
        tenant_id: str,
        subject_id: str,
        trace_id: str,
        source_id: str,
        business_run_id: str | None = None,
    ) -> VlmProviderResult:
        del mime_type, tenant_id, subject_id, trace_id, source_id, business_run_id
        assert "PUMP-X100" in instruction
        return VlmProviderResult(
            findings=(
                VisualFinding(
                    finding_id="finding-indicator",
                    label="indicator_light",
                    bbox=BoundingBox(0.3, 0.2, 0.1, 0.1),
                    confidence=0.91,
                    evidence_level="candidate",
                    model_release_id="vlm-batch2a1",
                    description="red indicator is visible",
                ),
            ),
            processor_version="vlm-batch2a1",
        )


@dataclass
class _Dispatcher:
    commands: list[DiagnosisWorkflowInput] = field(default_factory=list)

    async def dispatch(self, command: DiagnosisWorkflowInput) -> None:
        self.commands.append(command)

    async def cancel(self, _: str) -> None:
        return None


class _Resolver:
    def resolve(self, _: TenantContext, alias: str) -> ResolvedModel:
        assert alias == "industrial-diagnosis"
        prompt = default_prompt_registry().get(DIAGNOSIS_AGENT_PROMPT_ID)
        return ResolvedModel(
            alias=alias,
            release_id="model-release-batch2a1",
            manifest_hash="manifest-batch2a1",
            endpoint_url="https://model.invalid",
            runtime_profile="runtime-batch2a1",
            multimodal_model_ids={"ocr": "ocr-batch2a1", "vlm": "vlm-batch2a1"},
            deployment_id="deployment-batch2a1",
            diagnosis_binding={
                "agent_graph_id": DIAGNOSIS_GRAPH_VERSION,
                "prompt_bundle_id": DIAGNOSIS_AGENT_PROMPT_ID,
                "prompt_bundle": {"content_hash": prompt.content_hash},
                "retrieval": {"index_release_id": INDEX_RELEASE_ID},
                "tool_registry": {name: "1.0.0" for name in DIAGNOSIS_READONLY_TOOLS},
            },
        )


def _identity() -> IdentityContext:
    now = datetime.now(UTC)
    return IdentityContext(
        subject_id=SUBJECT_ID,
        oidc_subject=SUBJECT_ID,
        tenant_id=TENANT_ID,
        roles=frozenset({Role.AFTER_SALES_ENGINEER}),
        asset_ids=frozenset({ASSET_ID}),
        site_ids=frozenset({"site-batch2a1"}),
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
    )


def _database() -> Database:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Database.from_engine(engine)


async def _seed(database: Database, store: _Store) -> None:
    context = TenantContext(TENANT_ID, SUBJECT_ID)
    content = b"batch2a1-clean-image"
    now = datetime.now(UTC)
    key = clean_object_key(context, DRAFT_ID, MEDIA_ID)
    await store.put(context, key, content)
    with database.transaction(context) as session:
        session.add(
            TenantRecord(
                id=TENANT_ID,
                status="ACTIVE",
                display_name="Batch 2A.1",
                version=1,
            )
        )
        session.add(
            SubjectRecord(
                subject_id=SUBJECT_ID,
                tenant_id=TENANT_ID,
                oidc_issuer="https://issuer.invalid",
                oidc_subject=SUBJECT_ID,
                display_name="Batch 2A.1 engineer",
                email=None,
                status="active",
                version=1,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            AssetRecord(
                asset_id=ASSET_ID,
                tenant_id=TENANT_ID,
                source_system="synthetic",
                source_record_id=ASSET_ID,
                as_of=now,
                model_code="PUMP-X100",
                display_name="Batch 2A.1 pump",
                serial_number=None,
                lifecycle_status="IN_SERVICE",
                version=1,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            IncidentDraftRecord(
                draft_id=DRAFT_ID,
                tenant_id=TENANT_ID,
                asset_id=ASSET_ID,
                author_subject_id=SUBJECT_ID,
                description="Indicator alarm observed.",
                version=1,
                status="DRAFT",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            MediaObjectRecord(
                media_id=MEDIA_ID,
                tenant_id=TENANT_ID,
                draft_id=DRAFT_ID,
                quarantine_key=key.value.replace("/clean/", "/quarantine/"),
                clean_key=key.value,
                content_hash=sha256(content).hexdigest(),
                declared_mime="image/jpeg",
                detected_mime="image/jpeg",
                size_bytes=len(content),
                scan_state="CLEAN",
                scan_version=1,
                content_credential_status="ABSENT",
                content_credential_report=None,
                content_credential_digest=None,
                content_credential_inspected_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            RecognitionRunRecord(
                recognition_run_id=RECOGNITION_RUN_ID,
                tenant_id=TENANT_ID,
                draft_id=DRAFT_ID,
                media_id=MEDIA_ID,
                context_kind="INCIDENT_DRAFT",
                requested_by_subject_id=None,
                workflow_id="recognition-batch2a1",
                status="QUEUED",
                processor_profile="batch2a1",
                evidence_bundle_id=None,
                failure_reason=None,
                version=1,
                created_at=now,
                updated_at=now,
            )
        )


async def _verify() -> tuple[dict[str, Any], dict[str, Any]]:
    database = _database()
    store = _Store()
    identity = _identity()
    try:
        await _seed(database, store)
        recognition = RecognitionService(database, Authorizer(cast(Any, _AuditSink())))
        produced = await recognition.process(
            identity,
            RECOGNITION_RUN_ID,
            object_store=store,
            processor=MultimodalProcessor(_Ocr(), _Vlm()),
            request_id="request-batch2a1-recognition",
        )
        reloaded = recognition.get_evidence(
            identity, DRAFT_ID, request_id="request-batch2a1-reload"
        )
        assert reloaded.bundle_id == produced.bundle_id
        assert reloaded.version == produced.version == 1
        assert (reloaded.tenant_id, reloaded.draft_id, reloaded.asset_id, reloaded.media_id) == (
            TENANT_ID,
            DRAFT_ID,
            ASSET_ID,
            MEDIA_ID,
        )
        assert reloaded.source_sha256 == produced.source_sha256
        assert reloaded.processor_versions == produced.processor_versions
        assert [(item.block_id, item.text, item.confidence) for item in reloaded.ocr_blocks] == [
            ("ocr-alarm-42", "ALARM-42", 0.98)
        ]
        assert [
            (item.finding_id, item.label, item.confidence) for item in reloaded.visual_findings
        ] == [("finding-indicator", "indicator_light", 0.91)]
        assert reloaded.visual_findings[0].bbox == produced.visual_findings[0].bbox
        assert reloaded.status.value == "READY_FOR_CONFIRMATION"
        assert reloaded.automation_eligible is False

        confirmed = recognition.confirm(
            identity,
            DRAFT_ID,
            bundle_id=reloaded.bundle_id,
            corrections={},
            finding_dispositions={"finding-indicator": FindingDisposition.ACCEPTED},
            expected_version=1,
            request_id="request-batch2a1-confirm",
        )
        persisted = recognition.get_evidence(
            identity, DRAFT_ID, request_id="request-batch2a1-confirm-reload"
        )
        assert persisted.status.value == confirmed.status.value == "CONFIRMED"
        assert persisted.automation_eligible is True
        assert persisted.automatic_diagnosis_eligible is True

        now = datetime.now(UTC)
        with database.transaction(identity.tenant_context) as session:
            session.add(
                IncidentRecord(
                    incident_id=INCIDENT_ID,
                    tenant_id=TENANT_ID,
                    asset_id=ASSET_ID,
                    source_draft_id=DRAFT_ID,
                    evidence_bundle_id=persisted.bundle_id,
                    reporter_subject_id=SUBJECT_ID,
                    description="Indicator alarm observed.",
                    severity=None,
                    category=None,
                    responsible_queue=None,
                    information_due_at=None,
                    escalation_responsible_subject_id=None,
                    status="TRIAGED",
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                IndexReleaseRecord(
                    release_id=INDEX_RELEASE_ID,
                    tenant_id=TENANT_ID,
                    name="batch2a1",
                    version=1,
                    status="PUBLISHED",
                    is_active=True,
                    content_checksum="checksum-batch2a1",
                    created_by_subject_id=SUBJECT_ID,
                    published_by=SUBJECT_ID,
                    published_at=now,
                    activation_version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
        dispatcher = _Dispatcher()
        result = await DiagnosisService(
            database,
            Authorizer(cast(Any, _AuditSink())),
            dispatcher,
            model_resolver=cast(Any, _Resolver()),
        ).start(
            identity,
            INCIDENT_ID,
            expected_version=1,
            idempotency_key="batch2a1",
            request_id="request-batch2a1-diagnosis",
        )
        assert result.created is True
        assert len(dispatcher.commands) == 1
        with database.transaction(identity.tenant_context) as session:
            diagnosis = session.get(DiagnosisRunRecord, result.run.diagnosis_run_id)
            assert diagnosis is not None
            manifest = dict(diagnosis.manifest)
        assert manifest["evidence_bundle_id"] == persisted.bundle_id
        assert manifest["evidence_version"] == persisted.version
        assert manifest["index_release_id"] == INDEX_RELEASE_ID
        assert manifest["agent_graph_version"] == DIAGNOSIS_GRAPH_VERSION
        assert manifest["prompt_bundle"] == DIAGNOSIS_AGENT_PROMPT_ID
        resolved = DiagnosisEvidenceResolver().resolve(
            database,
            identity.tenant_context,
            manifest,
        )
        assert [item.kind for item in resolved.items] == ["RECOGNITION", "RECOGNITION"]
        assert {item.citation["source_id"] for item in resolved.items} == {
            "ocr-alarm-42",
            "finding-indicator",
        }
        assert all(
            item.citation["evidence_bundle_id"] == persisted.bundle_id for item in resolved.items
        )
        runtime = DiagnosisRuntime(
            database,
            dispatcher.commands[0],
            {
                "manifest": manifest,
                "query_text": "Indicator alarm observed.",
                "asset_id": ASSET_ID,
                "device_model": "PUMP-X100",
                "device_family": None,
                "diagnosis_run_id": result.run.diagnosis_run_id,
            },
            model_gateway=cast(Any, object()),
            tool_gateway=None,
            model_alias="industrial-diagnosis",
            timeout_seconds=90.0,
            memory_reader=cast(Any, object()),
            evidence_resolver=DiagnosisEvidenceResolver(),
        )
        state = await runtime.load()
        assert {item["kind"] for item in state["evidence"]} == {"RECOGNITION"}
        state["decision"] = {
            "report": {
                "status": "COMPLETED",
                "conclusion": "Indicator alarm confirmed.",
                "citation_ids": [item["citation_id"] for item in state["evidence"]],
                "contradictions": [],
                "missing_information": [],
                "next_checks": [],
                "confidence": 0.91,
            }
        }
        final_state = await runtime.finish(state)
        assert any(
            citation.get("finding_id") == "finding-indicator"
            and citation["source_id"] == "finding-indicator"
            for citation in final_state["report"]["citations"]
        )
        tampered = dict(manifest)
        tampered["evidence_refs"] = [dict(manifest["evidence_refs"][0])]
        tampered["evidence_refs"][0]["source_sha256"] = "tampered"
        try:
            DiagnosisEvidenceResolver().resolve(database, identity.tenant_context, tampered)
        except DiagnosisEvidenceResolutionError:
            pass
        else:
            raise AssertionError("tampered evidence reference was accepted")
        return manifest, {
            "bundle_id": persisted.bundle_id,
            "finding_ids": [item.finding_id for item in persisted.visual_findings],
            "ocr_ids": [item.block_id for item in persisted.ocr_blocks],
        }
    finally:
        database.dispose()


def main() -> int:
    manifest, evidence = asyncio.run(_verify())
    assert len(manifest["evidence_refs"]) == 2
    print("DEINDUSTRIALIZATION_BATCH2A1_PERSISTENCE_AND_MANIFEST_PASS")
    print(f"BATCH2A1_EVIDENCE_RESOLVER_PASS bundle_id={evidence['bundle_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
