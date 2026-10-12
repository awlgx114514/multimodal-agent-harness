"""Add generic applicability to knowledge document versions.

The legacy device columns remain for compatibility.  Runtime retrieval uses
only the generic key/value object populated by this revision.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0088_knowledge_generic_applicability"
down_revision: str | None = "0087_agent_run_independent_ownership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _applicability(families: Any, models: Any) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    family_values = _as_list(families)
    model_values = _as_list(models)
    if family_values:
        result["equipment.family"] = family_values
    if model_values:
        result["equipment.model"] = model_values
    return result


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column(
        "knowledge_document_versions",
        sa.Column("applicability", sa.JSON(), nullable=True),
    )
    versions = sa.table(
        "knowledge_document_versions",
        sa.column("document_version_id", sa.String()),
        sa.column("device_families", sa.JSON()),
        sa.column("device_models", sa.JSON()),
        sa.column("applicability", sa.JSON()),
    )
    rows = bind.execute(
        sa.select(
            versions.c.document_version_id,
            versions.c.device_families,
            versions.c.device_models,
        )
    )
    for row in rows:
        bind.execute(
            versions.update()
            .where(versions.c.document_version_id == row.document_version_id)
            .values(applicability=_applicability(row.device_families, row.device_models))
        )
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("knowledge_document_versions") as batch:
            batch.alter_column("applicability", nullable=False)
    else:
        op.alter_column("knowledge_document_versions", "applicability", nullable=False)


def downgrade() -> None:
    op.drop_column("knowledge_document_versions", "applicability")
