from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from unittest import TestCase

from industrial_ops_agent.evaluation.public_source import (
    EvaluationSourceContract,
    EvaluationSourceContractError,
)


class PublicEvaluationSourceContractTests(TestCase):
    def setUp(self) -> None:
        self.repository = Path(__file__).resolve().parents[2]
        self.manifest_path = (
            self.repository
            / "artifacts"
            / "plant_disease"
            / "candidates"
            / "plantdoc-source-v2"
            / "plant_disease_gold_v1-600"
            / "manifest.json"
        )
        self.manifest_bytes = self.manifest_path.read_bytes()
        self.manifest = json.loads(self.manifest_bytes)

    def test_accepts_real_plantdoc_candidates_as_pending_generic_source(self) -> None:
        contract = EvaluationSourceContract.from_manifest(
            self.manifest,
            manifest_hash=sha256(self.manifest_bytes).hexdigest(),
            source_bytes=self.manifest_bytes,
        )

        self.assertEqual(contract.contract_version, "public-vlm-evaluation-source-v1")
        self.assertEqual(contract.source_revision, "4730a233a555b30ee98e0879c63ad25d82407455")
        self.assertEqual(contract.sample_count, 600)
        self.assertEqual(contract.review_status, "PENDING_REVIEW")
        self.assertEqual(contract.formal_suite_id, None)
        self.assertTrue(contract.manifest_hash)

    def test_preserves_source_annotation_identity_and_normalized_findings(self) -> None:
        contract = EvaluationSourceContract.from_manifest(
            self.manifest,
            manifest_hash=sha256(self.manifest_bytes).hexdigest(),
            source_bytes=self.manifest_bytes,
        )

        source_case = self.manifest["cases"][0]
        normalized_case = contract.cases[0]
        self.assertEqual(
            normalized_case.expected_findings,
            tuple(source_case["expected_findings"]),
        )
        self.assertEqual(
            normalized_case.source_annotation_ids,
            tuple(finding["source_annotation_id"] for finding in source_case["findings"]),
        )
        self.assertEqual(
            normalized_case.original_annotations,
            tuple(finding["original_annotation"] for finding in source_case["findings"]),
        )

    def test_rejects_changed_manifest_digest(self) -> None:
        with self.assertRaises(EvaluationSourceContractError):
            EvaluationSourceContract.from_manifest(
                self.manifest,
                manifest_hash="0" * 64,
                source_bytes=self.manifest_bytes,
            )

    def test_rejects_candidates_without_pending_review_state(self) -> None:
        altered = dict(self.manifest)
        altered["review_status"] = "APPROVED"

        with self.assertRaises(EvaluationSourceContractError):
            EvaluationSourceContract.from_manifest(
                altered,
                manifest_hash=sha256(self.manifest_bytes).hexdigest(),
                source_bytes=self.manifest_bytes,
            )
