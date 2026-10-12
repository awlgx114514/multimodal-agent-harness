"""Remove the retired GraphRAG / Neo4j projection surface."""

from __future__ import annotations

from alembic import op

revision: str = "0092_remove_graphrag_neo4j"
down_revision: str | None = "0091_remove_predictive_maintenance"
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Drop graph children before their release parent and graph-only audit data."""

    for table_name in (
        "knowledge_graph_extraction_jobs",
        "knowledge_graph_evaluations",
        "knowledge_graph_edges",
        "knowledge_graph_nodes",
        "knowledge_graph_releases",
    ):
        op.drop_table(table_name)
    with op.batch_alter_table("knowledge_index_activations") as batch_op:
        batch_op.drop_column("revoked_graph_release_ids")


def downgrade() -> None:
    raise NotImplementedError("0092_remove_graphrag_neo4j is forward-only")
