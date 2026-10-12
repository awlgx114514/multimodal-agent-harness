from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from unittest import TestCase

from industrial_ops_agent.media.models import MediaObject, ScanState
from industrial_ops_agent.object_store.keys import (
    ObjectZone,
    application_object_key,
)
from industrial_ops_agent.persistence.tenant import TenantContext


class ApplicationMediaOwnershipTests(TestCase):
    def test_public_source_image_has_application_owned_canonical_media_keys(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        manifest_path = (
            repository
            / "artifacts"
            / "plant_disease"
            / "candidates"
            / "plantdoc-source-v2"
            / "plant_disease_gold_v1-600"
            / "manifest.json"
        )
        case = json.loads(manifest_path.read_text(encoding="utf-8"))["cases"][0]
        image_path = manifest_path.parent / case["image_file"]
        content = image_path.read_bytes()
        image_hash = sha256(content).hexdigest()
        context = TenantContext(tenant_id="plant-demo", subject_id="subject-uploader")
        quarantine = application_object_key(
            context,
            ObjectZone.QUARANTINE,
            application_id="plant-disease",
            application_context_id=image_hash,
            media_id=f"media-{image_hash[:32]}",
        )
        clean = application_object_key(
            context,
            ObjectZone.CLEAN,
            application_id="plant-disease",
            application_context_id=image_hash,
            media_id=f"media-{image_hash[:32]}",
        )
        media = MediaObject.create(
            media_id=f"media-{image_hash[:32]}",
            tenant_id=context.tenant_id,
            application_id="plant-disease",
            application_context_id=image_hash,
            quarantine_key=quarantine.value,
            content_hash=image_hash,
            declared_mime="image/jpeg",
            detected_mime="image/jpeg",
            size_bytes=len(content),
            occurred_at=datetime.now(UTC),
        )
        clean_media = media.complete_scan(
            state=ScanState.CLEAN,
            clean_key=clean.value,
            occurred_at=datetime.now(UTC),
        )

        self.assertIsNone(media.draft_id)
        self.assertEqual(media.application_id, "plant-disease")
        self.assertEqual(media.application_context_id, image_hash)
        self.assertEqual(clean_media.clean_key, clean.value)
