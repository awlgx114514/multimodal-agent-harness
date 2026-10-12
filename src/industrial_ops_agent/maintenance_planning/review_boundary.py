"""Maintenance Planning implementation of the reusable review boundary."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import NoReturn

from sqlalchemy.orm import Session

from industrial_ops_agent.auth.identity import IdentityContext
from industrial_ops_agent.governance.review_boundary import (
    DisclosureRequest,
    ReviewBoundaryConflict,
)
from industrial_ops_agent.persistence.database import Database

from .review_isolation import (
    ReviewIsolationConflict,
    draft_read_transaction,
    record_disclosure,
    record_draft_disclosure,
    record_incident_disclosure,
)


class MaintenanceReviewBoundary:
    """Translate opaque boundary requests into Maintenance Planning policy calls."""

    @contextmanager
    def guarded_read(
        self,
        database: Database,
        identity: IdentityContext,
        request: DisclosureRequest,
        *,
        request_id: str,
    ) -> Iterator[Session]:
        if request.source_type != "draft" or len(request.source_ids) != 1:
            self.deny("guarded_read_source_unsupported")
        with draft_read_transaction(
            database,
            identity,
            request.source_ids[0],
            request_id=request_id,
        ) as session:
            yield session

    def record_disclosure(
        self,
        session: Session,
        identity: IdentityContext,
        request: DisclosureRequest,
        *,
        request_id: str,
    ) -> None:
        if request.source_type == "draft" and len(request.source_ids) == 1:
            record_draft_disclosure(
                session,
                identity,
                request.source_ids[0],
                request_id=request_id,
            )
            return
        if request.source_type == "incident":
            record_incident_disclosure(
                session,
                identity,
                request.source_ids,
                resource_kind=request.resource_type,
                resource_id=request.resource_id,
                request_id=request_id,
            )
            return
        if request.source_type == "diagnosis":
            record_disclosure(
                session,
                identity,
                request.source_ids,
                resource_kind=request.resource_type,
                resource_id=request.resource_id,
                request_id=request_id,
            )
            return
        self.deny("disclosure_source_unsupported")

    def deny(self, reason: str) -> NoReturn:
        raise ReviewIsolationConflict(reason)


__all__ = ["MaintenanceReviewBoundary", "ReviewBoundaryConflict"]
