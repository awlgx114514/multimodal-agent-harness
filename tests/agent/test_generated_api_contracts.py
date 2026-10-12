from __future__ import annotations

import json
import re
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


class GeneratedApiContractTests(TestCase):
    def test_public_source_review_routes_match_generated_contracts(self) -> None:
        routes = {
            "/api/v1/public-evaluation-sources",
            "/api/v1/public-evaluation-sources/{source_id}/manifest",
        }
        openapi = json.loads((ROOT / "contracts/openapi.json").read_text(encoding="utf-8"))
        types = (ROOT / "web/generated/api/schema.d.ts").read_text(encoding="utf-8")

        self.assertTrue(routes.issubset(openapi["paths"]))
        self.assertTrue(all(route in types for route in routes))

    def test_reanalysis_contract_contains_only_current_required_input(self) -> None:
        openapi = json.loads((ROOT / "contracts/openapi.json").read_text(encoding="utf-8"))
        schema = openapi["components"]["schemas"]["ReanalyzeDiagnosisRequest"]
        types = (ROOT / "web/generated/api/schema.d.ts").read_text(encoding="utf-8")

        self.assertEqual(set(schema["properties"]), {"transcript_segment_id"})
        self.assertEqual(schema["required"], ["transcript_segment_id"])
        start = types.index("ReanalyzeDiagnosisRequest: {")
        end = types.index("\n        };", start)
        generated_request = types[start:end]
        self.assertIn("transcript_segment_id", generated_request)
        self.assertNotIn("field_entry_ids", generated_request)
        self.assertNotIn("work_order_id", generated_request)
        self.assertNotIn("work_order_version", generated_request)

    def test_retained_transcript_routes_are_in_openapi_and_generated_types(self) -> None:
        routes = {
            "/api/v1/transcript-streams/{stream_id}/segments",
            "/api/v1/transcripts/{segment_id}/confirmation",
        }
        openapi = json.loads((ROOT / "contracts/openapi.json").read_text(encoding="utf-8"))
        types = (ROOT / "web/generated/api/schema.d.ts").read_text(encoding="utf-8")

        self.assertTrue(routes.issubset(openapi["paths"]))
        self.assertTrue(all(route in types for route in routes))

    def test_citation_response_distinguishes_knowledge_and_recognition(self) -> None:
        openapi = json.loads((ROOT / "contracts/openapi.json").read_text(encoding="utf-8"))
        data = openapi["components"]["schemas"]["CitationEnvelope"]["properties"]["data"]

        self.assertEqual(data["discriminator"]["propertyName"], "source_type")
        self.assertEqual(
            {item["$ref"].rsplit("/", maxsplit=1)[1] for item in data["oneOf"]},
            {"KnowledgeCitationResponse", "RecognitionCitationResponse"},
        )

    def test_frontend_client_types_match_generated_recognition_contract(self) -> None:
        client = (ROOT / "web/lib/api/client.ts").read_text(encoding="utf-8")

        self.assertTrue(
            re.search(
                r"export type FieldQrCodeDecision\s*=\s*IncidentQrCodeDecision;",
                client,
            )
        )
        self.assertNotIn("ExpertRecommendationResponse", client)
