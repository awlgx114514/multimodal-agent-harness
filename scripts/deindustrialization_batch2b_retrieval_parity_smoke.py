"""Verify generic applicability preserves the frozen retrieval result sets."""

from __future__ import annotations

from deindustrialization_batch2b_retrieval_baseline import (
    NOW,
    RELEASE_ID,
    SUBJECT_ID,
    TENANT_ID,
    RetrievalQuery,
    _capture,
    _database,
    _seed,
)

from industrial_ops_agent.industrial_recognition.knowledge_applicability import (
    industrial_applicability,
)


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
            "matching_family_and_model": industrial_applicability("pump", "X100"),
            "family_match_model_mismatch": industrial_applicability("pump", "X999"),
            "missing_family_model_match": industrial_applicability(None, "X100"),
        }
        expected = {
            "matching_family_and_model": (
                [
                    "chunk-family",
                    "chunk-global",
                    "chunk-model",
                    "chunk-role-acl",
                    "chunk-subject-acl",
                ],
                5,
            ),
            "family_match_model_mismatch": (
                ["chunk-family", "chunk-global", "chunk-role-acl", "chunk-subject-acl"],
                4,
            ),
            "missing_family_model_match": (
                ["chunk-global", "chunk-role-acl", "chunk-subject-acl"],
                3,
            ),
        }
        for name, applicability in cases.items():
            result = _capture(
                database,
                RetrievalQuery(**common, applicability=applicability),
            )
            chunk_ids, count = expected[name]
            assert result["final_chunk_ids"] == chunk_ids
            assert result["final_citation_ids"] == [
                item.replace("chunk-", "citation-") for item in chunk_ids
            ]
            assert result["candidate_counts"] == {
                "fused": count,
                "returned": count,
                "sparse": count,
                "vector": count,
            }
        print("DEINDUSTRIALIZATION_BATCH2B_RETRIEVAL_PARITY_PASS")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
