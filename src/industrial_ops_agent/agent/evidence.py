"""Domain-neutral evidence items shared by the diagnosis Agent runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

EvidenceKind = Literal["RECOGNITION", "KNOWLEDGE"]


@dataclass(frozen=True, slots=True)
class AgentEvidenceItem:
    """One authorized item that can be cited by an Agent execution."""

    citation_id: str
    kind: EvidenceKind
    title: str
    content: str
    content_checksum: str
    source_checksum: str
    citation: dict[str, Any]

    def __post_init__(self) -> None:
        if (
            not self.citation_id.strip()
            or self.kind not in {"RECOGNITION", "KNOWLEDGE"}
            or not self.title.strip()
            or not self.content_checksum.strip()
            or not self.source_checksum.strip()
            or self.citation.get("citation_id") != self.citation_id
        ):
            raise ValueError("agent evidence item is invalid")

    def as_dict(self) -> dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "kind": self.kind,
            "title": self.title,
            "content": self.content,
            "content_checksum": self.content_checksum,
            "source_checksum": self.source_checksum,
            "citation": dict(self.citation),
        }

    def citation_payload(self) -> dict[str, Any]:
        return dict(self.citation)

    @classmethod
    def from_knowledge(cls, evidence: Any) -> AgentEvidenceItem:
        citation = dict(evidence.citation_payload())
        return cls(
            citation_id=evidence.citation_id,
            kind="KNOWLEDGE",
            title=evidence.title,
            content=evidence.content,
            content_checksum=evidence.content_checksum,
            source_checksum=evidence.source_checksum,
            citation=citation,
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> AgentEvidenceItem:
        return cls(
            citation_id=str(value["citation_id"]),
            kind=value["kind"],
            title=str(value["title"]),
            content=str(value["content"]),
            content_checksum=str(value["content_checksum"]),
            source_checksum=str(value["source_checksum"]),
            citation=dict(value["citation"]),
        )


@dataclass(frozen=True, slots=True)
class AgentEvidenceContext:
    """The authorized evidence set, retaining source kind for citation handling."""

    items: tuple[AgentEvidenceItem, ...]

    @property
    def recognition(self) -> tuple[AgentEvidenceItem, ...]:
        return tuple(item for item in self.items if item.kind == "RECOGNITION")

    @property
    def knowledge(self) -> tuple[AgentEvidenceItem, ...]:
        return tuple(item for item in self.items if item.kind == "KNOWLEDGE")

    def as_dicts(self) -> list[dict[str, Any]]:
        return [item.as_dict() for item in self.items]


class AgentEvidenceResolver(Protocol):
    """Composition-root supplied resolver for a diagnosis manifest."""

    def resolve(
        self, database: Any, context: Any, manifest: dict[str, Any]
    ) -> AgentEvidenceContext:
        ...
