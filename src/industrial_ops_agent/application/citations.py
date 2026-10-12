"""Resolve report citations through their owning domain boundary."""

from __future__ import annotations

from dataclasses import dataclass

from industrial_ops_agent.auth.errors import AuthorizationDenied
from industrial_ops_agent.auth.identity import IdentityContext
from industrial_ops_agent.auth.policy import Authorizer
from industrial_ops_agent.industrial_recognition.diagnosis_evidence import (
    DiagnosisEvidenceResolutionError,
    RecognitionCitationResolver,
    RecognitionCitationView,
)
from industrial_ops_agent.knowledge.models import CitationView as KnowledgeCitationView
from industrial_ops_agent.knowledge.provenance import (
    CitationProvenanceService,
    CitationProvenanceView,
)
from industrial_ops_agent.knowledge.service import KnowledgeNotVisible
from industrial_ops_agent.persistence.database import Database


class CitationNotVisible(LookupError):
    """The citation is absent or not authorized for the current identity."""


@dataclass(frozen=True, slots=True)
class CitationResolution:
    source_type: str
    citation: KnowledgeCitationView | RecognitionCitationView
    provenance: CitationProvenanceView | None

    def expert_reference(self) -> dict[str, object]:
        if isinstance(self.citation, RecognitionCitationView):
            reference: dict[str, object] = {
                "citation_id": self.citation.citation_id,
                "evidence_kind": "RECOGNITION",
                "evidence_bundle_id": self.citation.evidence_bundle_id,
                "evidence_version": self.citation.evidence_version,
                "recognition_result_id": self.citation.recognition_result_id,
                "result_type": self.citation.result_type,
                "source_id": self.citation.source_id,
                "media_id": self.citation.media_id,
                "source_sha256": self.citation.source_checksum,
                "result_hash": self.citation.result_hash,
            }
            if self.citation.source_frame_id is not None:
                reference["source_frame_id"] = self.citation.source_frame_id
            if self.citation.finding_id is not None:
                reference["finding_id"] = self.citation.finding_id
            return reference

        return {
            "citation_id": self.citation.citation_id,
            "chunk_id": self.citation.chunk_id,
            "document_id": self.citation.document_id,
            "document_version_id": self.citation.document_version_id,
            "document_version": self.citation.document_version,
            "title": self.citation.title,
            "source_checksum": self.citation.source_checksum,
            "content_checksum": self.citation.content_checksum,
            "page_number": self.citation.page_number,
        }


class CitationResolver:
    """Dispatch a citation ID to Knowledge or Industrial Recognition ownership."""

    def __init__(self, database: Database, authorizer: Authorizer) -> None:
        self._knowledge = CitationProvenanceService(database, authorizer)
        self._recognition = RecognitionCitationResolver(database, authorizer)

    def resolve(
        self,
        identity: IdentityContext,
        citation_id: str,
        *,
        request_id: str,
    ) -> CitationResolution:
        if citation_id.startswith("recognition:"):
            try:
                citation = self._recognition.resolve(
                    identity,
                    citation_id,
                    request_id=request_id,
                )
            except (AuthorizationDenied, DiagnosisEvidenceResolutionError) as exc:
                raise CitationNotVisible from exc
            return CitationResolution("RECOGNITION", citation, None)

        try:
            authorized = self._knowledge.get(
                identity,
                citation_id,
                request_id=request_id,
            )
        except KnowledgeNotVisible as exc:
            raise CitationNotVisible from exc
        return CitationResolution(
            "KNOWLEDGE",
            authorized.citation,
            authorized.provenance,
        )


__all__ = ["CitationNotVisible", "CitationResolution", "CitationResolver"]
