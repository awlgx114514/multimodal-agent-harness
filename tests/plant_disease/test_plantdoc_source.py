import json
from hashlib import sha256
from pathlib import Path

import pytest

from industrial_ops_agent.plant_disease.dataset import (
    IMPORT_VERSION,
    PlantDocDataset,
    read_plantdoc,
    select_cases,
)

REPOSITORY = Path(__file__).resolve().parents[2]
REVISION = "4730a233a555b30ee98e0879c63ad25d82407455"
ARCHIVE = (
    REPOSITORY
    / "artifacts"
    / "plant_disease"
    / "upstream"
    / REVISION
    / f"PlantDoc-Object-Detection-Dataset-{REVISION}.zip"
)


@pytest.fixture(scope="module")
def dataset() -> PlantDocDataset:
    return read_plantdoc(ARCHIVE)


def test_official_source_preserves_multiple_boxes_and_provenance(dataset: PlantDocDataset) -> None:
    image = next(
        item
        for item in dataset.images
        if item.split == "TRAIN" and item.filename == "cherry-tree-leaves-and-fruits.jpg"
    )

    assert dataset.revision == REVISION
    assert dataset.archive_sha256 == (
        "45811ced89d3e40fac185dbe56eb7935745aad34c5c1402d937f0281eae0d813"
    )
    assert dataset.license_id == "CC-BY-4.0"
    assert dataset.license_sha256 == (
        "95df2e9564862e51d69683a899b6dcc8218d577057bdf67322880769ff85f29e"
    )
    assert len(dataset.images) == 2581
    assert sum(len(item.findings) for item in dataset.images) == 8921
    assert (image.width, image.height, image.plant_species) == (350, 300, "Cherry")
    assert len(image.findings) == 4
    assert image.findings[0].label == "Cherry leaf"
    assert image.findings[0].bbox_pixels == (198, 77, 299, 252)
    assert image.findings[0].source_annotation_id.endswith("/train_labels.csv#row=2")
    assert image.findings[0].original_annotation["xmin"] == "198"
    assert "confidence" not in image.findings[0].original_annotation
    assert image.original_xml is not None
    assert "<xmin>198</xmin>" in image.original_xml
    assert image.image_sha256 is not None
    assert len(image.image_sha256) == 64


def test_sampling_retains_original_findings_and_unique_real_images(
    dataset: PlantDocDataset,
) -> None:
    cases = select_cases(dataset, sample_count=600, seed="plant_disease_gold_v1")
    repeated = select_cases(dataset, sample_count=600, seed="plant_disease_gold_v1")

    assert len(cases) == 600
    assert len({item.image_sha256 for item in cases}) == 600
    assert [item.source_image_id for item in cases] == [item.source_image_id for item in repeated]
    assert len({finding.label for item in cases for finding in item.findings}) == 29
    assert all(item.valid for item in cases)
    assert all(item.findings for item in cases)
    assert all(item in dataset.images for item in cases)


def test_invalid_original_dimensions_are_preserved_and_excluded(dataset: PlantDocDataset) -> None:
    invalid = next(
        item for item in dataset.images
        if item.split == "TRAIN" and item.filename == "2f73110f80014a25a53f9551c94bf164.png.jpg"
    )
    assert (invalid.width, invalid.height) == (0, 0)
    assert invalid.findings[0].bbox_pixels == (58, 92, 525, 386)
    assert invalid.findings[0].original_annotation["width"] == "0"
    assert "annotation_dimensions_invalid" in invalid.issues
    assert not invalid.valid
    assert invalid not in select_cases(dataset, sample_count=600, seed="plant_disease_gold_v1")


def test_selected_regions_preserve_pixel_ground_truth(dataset: PlantDocDataset) -> None:
    for image in select_cases(dataset, sample_count=600, seed="plant_disease_gold_v1"):
        for finding in image.findings:
            region = finding.normalized_region(image.width, image.height)
            xmin, ymin, xmax, ymax = finding.bbox_pixels
            assert set(region) == {"x", "y", "width", "height"}
            assert region["x"] == xmin / image.width
            assert region["y"] == ymin / image.height
            assert region["width"] == (xmax - xmin) / image.width
            assert region["height"] == (ymax - ymin) / image.height
            assert 0 <= region["x"] < region["x"] + region["width"] <= 1
            assert 0 <= region["y"] < region["y"] + region["height"] <= 1


def test_source_reference_preserves_query_characters(dataset: PlantDocDataset) -> None:
    image = next(
        item for item in dataset.images
        if item.split == "TEST" and item.filename == "1421_0.jpeg?itok=FMtmgePj.jpg"
    )
    assert "1421_0.jpeg%3Fitok%3DFMtmgePj.jpg" in image.source_image_id
    assert image.archive_member.endswith("/1421_0.jpeg?itok=FMtmgePj.jpg")


def test_candidate_export_preserves_source_and_requires_review(dataset: PlantDocDataset) -> None:
    from industrial_ops_agent.plant_disease.dataset import export_candidates

    output = (
        REPOSITORY / "artifacts" / "plant_disease" / "test-candidates"
        / IMPORT_VERSION / "plant_disease_gold_v1-600"
    )
    cases = select_cases(dataset, sample_count=600, seed="plant_disease_gold_v1")
    first = export_candidates(dataset, cases, output=output, seed="plant_disease_gold_v1")
    repeated = export_candidates(dataset, cases, output=output, seed="plant_disease_gold_v1")
    assert first == repeated
    manifest = json.loads((output / "manifest.json").read_bytes())
    assert manifest["review_status"] == "PENDING_REVIEW"
    assert manifest["formal_suite_id"] is None
    assert manifest["sample_count"] == 600
    assert manifest["source"]["license"] == "CC-BY-4.0"
    assert len(manifest["cases"]) == 600
    for case in manifest["cases"]:
        content = (output / case["image_file"]).read_bytes()
        assert sha256(content).hexdigest() == case["image_sha256"]
        assert len(case["expected_findings"]) == len(case["findings"])
        assert "confidence" not in case["expected_findings"][0]
        assert case["original_xml"]
    conflicts = [
        image for image in manifest["source_quality"]["excluded"]
        if image["filename"] == "2015070295153021.jpg"
    ]
    assert len(conflicts) == 2
    assert all(image["original_xml"] and image["findings"] for image in conflicts)


def test_conflicting_source_annotations_are_preserved_and_excluded(
    dataset: PlantDocDataset,
) -> None:
    versions = tuple(
        image for image in dataset.images if image.filename == "2015070295153021.jpg"
    )
    assert {image.split for image in versions} == {"TRAIN", "TEST"}
    assert len({image.image_sha256 for image in versions}) == 1
    annotations = {
        tuple((finding.label, finding.bbox_pixels) for finding in image.findings)
        for image in versions
    }
    assert len(annotations) == 2
    assert all("duplicate_image_annotations_disagree" in image.issues for image in versions)
    cases = select_cases(dataset, sample_count=600, seed="plant_disease_gold_v1")
    assert all(image not in cases for image in versions)
