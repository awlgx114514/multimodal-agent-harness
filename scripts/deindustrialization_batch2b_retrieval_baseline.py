"""Freeze the pre-0088 Industrial Diagnosis retrieval behavior."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from industrial_ops_agent.industrial_recognition.knowledge_applicability import (
    industrial_applicability,
)
from industrial_ops_agent.knowledge.embedding import deterministic_embedding
from industrial_ops_agent.knowledge.models import RetrievalQuery
from industrial_ops_agent.knowledge.retrieval import HybridRetriever
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import (
    Base,
    CitationAnchorRecord,
    IndexReleaseRecord,
    KnowledgeChunkRecord,
    KnowledgeDocumentRecord,
    KnowledgeDocumentVersionRecord,
    SubjectRecord,
    TenantRecord,
)
from industrial_ops_agent.persistence.tenant import TenantContext

NOW = datetime(2026, 1, 1, tzinfo=UTC)
TENANT_ID = "tenant-retrieval-baseline"
OTHER_TENANT_ID = "tenant-retrieval-other"
SUBJECT_ID = "subject-retrieval-baseline"
RELEASE_ID = "release-retrieval-baseline"
OTHER_RELEASE_ID = "release-retrieval-other"


def _database() -> Database:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Database.from_engine(engine)


def _seed(database: Database) -> None:
    with database.transaction(TenantContext(TENANT_ID, SUBJECT_ID)) as session:
        session.add(
            TenantRecord(
                id=TENANT_ID,
                status="ACTIVE",
                display_name="Retrieval baseline",
                version=1,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.add(
            TenantRecord(
                id=OTHER_TENANT_ID,
                status="ACTIVE",
                display_name="Other tenant",
                version=1,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.add(
            SubjectRecord(
                subject_id=SUBJECT_ID,
                tenant_id=TENANT_ID,
                oidc_issuer="https://issuer.invalid",
                oidc_subject=SUBJECT_ID,
                display_name="Baseline subject",
                email=None,
                status="active",
                version=1,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        for release_id, tenant_id in (
            (RELEASE_ID, TENANT_ID),
            (OTHER_RELEASE_ID, OTHER_TENANT_ID),
        ):
            session.add(
                IndexReleaseRecord(
                    release_id=release_id,
                    tenant_id=tenant_id,
                    name="baseline",
                    version=1,
                    status="PUBLISHED",
                    is_active=True,
                    content_checksum=f"checksum-{release_id}",
                    created_by_subject_id=SUBJECT_ID,
                    published_by=SUBJECT_ID,
                    published_at=NOW,
                    activation_version=1,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        documents = (
            ("global", [], [], [], "global pump service"),
            ("family", ["pump"], [], [], "pump family service"),
            ("model", ["pump"], ["X100"], [], "pump X100 service"),
            ("model-mismatch", ["pump"], ["X200"], [], "pump X200 service"),
            ("family-mismatch", ["motor"], ["X100"], [], "motor X100 service"),
            ("subject-acl", [], [], [SUBJECT_ID], "subject pump service"),
            ("role-acl", [], [], [], "engineer pump service"),
        )
        for ordinal, (document_key, families, models, acl_subjects, content) in enumerate(
            documents, start=1
        ):
            document_id = f"document-{document_key}"
            version_id = f"version-{document_key}"
            chunk_id = f"chunk-{document_key}"
            citation_id = f"citation-{document_key}"
            checksum = sha256(content.encode()).hexdigest()
            session.add(
                KnowledgeDocumentRecord(
                    tenant_id=TENANT_ID,
                    document_id=document_id,
                    title=document_key,
                    source_uri=f"memory://{document_key}",
                    classification="internal",
                    source_checksum=checksum,
                    current_version=1,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            session.add(
                KnowledgeDocumentVersionRecord(
                    tenant_id=TENANT_ID,
                    document_version_id=version_id,
                    document_id=document_id,
                    version=1,
                    parser_version="baseline",
                    chunker_version="baseline",
                    acl_subject_ids=acl_subjects,
                    acl_roles=["engineer"] if document_key == "role-acl" else [],
                    device_families=families,
                    device_models=models,
                    applicability={
                        **({"equipment.family": families} if families else {}),
                        **({"equipment.model": models} if models else {}),
                    },
                    valid_from=NOW - timedelta(days=1),
                    valid_to=None,
                    source_checksum=checksum,
                    content_checksum=checksum,
                    extracted_text=content,
                    extraction_checksum=checksum,
                    extraction_metadata=None,
                    created_by_subject_id=SUBJECT_ID,
                    reviewed_by_subject_id=SUBJECT_ID,
                    reviewed_at=NOW,
                    state_version=2,
                    status="PUBLISHED",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            session.add(
                KnowledgeChunkRecord(
                    tenant_id=TENANT_ID,
                    chunk_id=chunk_id,
                    document_version_id=version_id,
                    release_id=RELEASE_ID,
                    ordinal=ordinal,
                    content=content,
                    content_checksum=checksum,
                    embedding=deterministic_embedding(content),
                    token_count=len(content.split()),
                )
            )
            session.add(
                CitationAnchorRecord(
                    tenant_id=TENANT_ID,
                    citation_id=citation_id,
                    chunk_id=chunk_id,
                    document_version_id=version_id,
                    anchor_kind="TEXT",
                    page_number=1,
                    bounding_box=None,
                    start_offset=0,
                    end_offset=len(content),
                    excerpt=content,
                    excerpt_checksum=checksum,
                )
            )
        session.flush()


def _capture(database: Database, query: RetrievalQuery) -> dict[str, object]:
    result = HybridRetriever(database).search_with_trace(query)
    return {
        "candidate_counts": {
            "sparse": result.guard.sparse_candidate_count,
            "vector": result.guard.vector_candidate_count,
            "fused": result.guard.fused_candidate_count,
            "returned": result.guard.returned_count,
        },
        "final_chunk_ids": [item.chunk_id for item in result.evidence],
        "final_citation_ids": [item.citation_id for item in result.evidence],
        "citations": [item.citation_payload() for item in result.evidence],
    }


def main() -> None:
    database = _database()
    try:
        _seed(database)
        common = dict(
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            roles=frozenset({"engineer"}),
            release_id=RELEASE_ID,
            query="pump service",
            as_of=NOW,
            limit=12,
        )
        cases = {
            "matching_family_and_model": RetrievalQuery(
                **common,
                applicability=industrial_applicability("pump", "X100"),
            ),
            "family_match_model_mismatch": RetrievalQuery(
                **common,
                applicability=industrial_applicability("pump", "X999"),
            ),
            "missing_family_model_match": RetrievalQuery(
                **common,
                applicability=industrial_applicability(None, "X100"),
            ),
        }
        print(
            json.dumps(
                {name: _capture(database, query) for name, query in cases.items()},
                sort_keys=True,
            )
        )
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
