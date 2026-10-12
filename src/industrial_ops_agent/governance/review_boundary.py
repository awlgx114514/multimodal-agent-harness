"""Domain-neutral subject locking and review/disclosure boundary protocol."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import NoReturn, Protocol

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from industrial_ops_agent.auth.identity import IdentityContext
from industrial_ops_agent.domain.json import strict_document_digest
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import SubjectRecord
from industrial_ops_agent.persistence.tenant import TenantContext


class ReviewBoundaryConflict(Exception):
    """A policy implementation denied a guarded source operation."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class DisclosureRequest:
    """Opaque source and exposed-resource identifiers for a policy implementation."""

    source_type: str
    source_ids: tuple[str, ...]
    resource_type: str
    resource_id: str


class ReviewBoundary(Protocol):
    """Policy-owned guarded source access used by reusable application services."""

    @contextmanager
    def guarded_read(
        self,
        database: Database,
        identity: IdentityContext,
        request: DisclosureRequest,
        *,
        request_id: str,
    ) -> Iterator[Session]: ...

    def record_disclosure(
        self,
        session: Session,
        identity: IdentityContext,
        request: DisclosureRequest,
        *,
        request_id: str,
    ) -> None: ...

    def deny(self, reason: str) -> NoReturn: ...


def lock_subject(
    session: Session,
    identity: IdentityContext | TenantContext,
    *,
    lineage_write: bool = False,
) -> SubjectRecord:
    """Lock a verified subject; this never grants authorization."""
    subject = session.scalar(
        select(SubjectRecord)
        .where(
            SubjectRecord.tenant_id == identity.tenant_id,
            SubjectRecord.subject_id == identity.subject_id,
        )
        .with_for_update()
    )
    if subject is None or subject.status != "active":
        raise ReviewBoundaryConflict("subject_unavailable")
    if session.get_bind().dialect.name == "postgresql":
        digest = strict_document_digest(
            {"schema": "review-boundary-subject-lock-v1", "tenant": identity.tenant_id}
        )
        key = int(digest.removeprefix("sha256:")[:16], 16)
        if key >= 2**63:
            key -= 2**64
        query = (
            "SELECT pg_advisory_xact_lock(:key)"
            if lineage_write
            else "SELECT pg_advisory_xact_lock_shared(:key)"
        )
        session.execute(text(query), {"key": key})
    return subject
