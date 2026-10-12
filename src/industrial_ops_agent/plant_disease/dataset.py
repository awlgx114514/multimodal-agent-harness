from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from hashlib import file_digest, sha256
from pathlib import Path, PurePosixPath
from urllib.parse import quote
from xml.etree import ElementTree
from zipfile import ZipFile

from PIL import Image

REVISION = "4730a233a555b30ee98e0879c63ad25d82407455"
ARCHIVE_SHA256 = "45811ced89d3e40fac185dbe56eb7935745aad34c5c1402d937f0281eae0d813"
LICENSE_SHA256 = "95df2e9564862e51d69683a899b6dcc8218d577057bdf67322880769ff85f29e"
SOURCE_URL = "https://github.com/pratikkayal/PlantDoc-Object-Detection-Dataset"
IMPORT_VERSION = "plantdoc-source-v2"
ATTRIBUTION = (
    "PlantDoc: A Dataset for Visual Plant Disease Detection; "
    "Davinder Singh, Naman Jain, Pranjali Jain, Pratik Kayal, "
    "Sudhakar Kumawat and Nipun Batra; CC BY 4.0."
)
ANNOTATION_COLUMNS = ("filename", "width", "height", "class", "xmin", "ymin", "xmax", "ymax")
SPECIES_BY_LABEL = {
    "Apple leaf": "Apple",
    "Apple rust leaf": "Apple",
    "Apple Scab Leaf": "Apple",
    "Bell_pepper leaf": "Bell pepper",
    "Bell_pepper leaf spot": "Bell pepper",
    "Blueberry leaf": "Blueberry",
    "Cherry leaf": "Cherry",
    "Corn Gray leaf spot": "Corn",
    "Corn leaf blight": "Corn",
    "Corn rust leaf": "Corn",
    "grape leaf": "Grape",
    "grape leaf black rot": "Grape",
    "Peach leaf": "Peach",
    "Potato leaf": "Potato",
    "Potato leaf early blight": "Potato",
    "Potato leaf late blight": "Potato",
    "Raspberry leaf": "Raspberry",
    "Soyabean leaf": "Soybean",
    "Squash Powdery mildew leaf": "Squash",
    "Strawberry leaf": "Strawberry",
    "Tomato Early blight leaf": "Tomato",
    "Tomato leaf": "Tomato",
    "Tomato leaf bacterial spot": "Tomato",
    "Tomato leaf late blight": "Tomato",
    "Tomato leaf mosaic virus": "Tomato",
    "Tomato leaf yellow virus": "Tomato",
    "Tomato mold leaf": "Tomato",
    "Tomato Septoria leaf spot": "Tomato",
    "Tomato two spotted spider mites leaf": "Tomato",
}


@dataclass(frozen=True, slots=True)
class PlantDocFinding:
    label: str
    bbox_pixels: tuple[int, int, int, int]
    source_annotation_id: str
    original_annotation: dict[str, str]

    def normalized_region(self, width: int, height: int) -> dict[str, float]:
        xmin, ymin, xmax, ymax = self.bbox_pixels
        if not (0 <= xmin < xmax <= width and 0 <= ymin < ymax <= height):
            raise ValueError("plantdoc_bbox_outside_image")
        return {
            "x": xmin / width,
            "y": ymin / height,
            "width": (xmax - xmin) / width,
            "height": (ymax - ymin) / height,
        }


@dataclass(frozen=True, slots=True)
class PlantDocImage:
    source_image_id: str
    archive_member: str
    split: str
    filename: str
    width: int
    height: int
    plant_species: str | None
    species_labels: tuple[str, ...]
    findings: tuple[PlantDocFinding, ...]
    image_sha256: str | None
    image_size_bytes: int | None
    mime_type: str | None
    original_xml: str | None
    xml_sha256: str | None
    issues: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.issues


@dataclass(frozen=True, slots=True)
class PlantDocDataset:
    archive_path: Path
    revision: str
    archive_sha256: str
    license_id: str
    license_sha256: str
    license_text: str
    annotation_sha256: dict[str, str]
    images: tuple[PlantDocImage, ...]


def read_plantdoc(archive_path: Path) -> PlantDocDataset:
    with archive_path.open("rb") as stream:
        archive_hash = file_digest(stream, "sha256").hexdigest()
    if archive_hash != ARCHIVE_SHA256:
        raise ValueError("plantdoc_archive_checksum_mismatch")
    root = f"PlantDoc-Object-Detection-Dataset-{REVISION}"
    images: list[PlantDocImage] = []
    annotation_hashes: dict[str, str] = {}
    with ZipFile(archive_path) as archive:
        members = set(archive.namelist())
        license_bytes = archive.read(f"{root}/LICENSE.txt")
        if sha256(license_bytes).hexdigest() != LICENSE_SHA256:
            raise ValueError("plantdoc_license_checksum_mismatch")
        for split, csv_name in (("TRAIN", "train_labels.csv"), ("TEST", "test_labels.csv")):
            csv_bytes = archive.read(f"{root}/{csv_name}")
            annotation_hashes[csv_name] = sha256(csv_bytes).hexdigest()
            reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))
            if tuple(reader.fieldnames or ()) != ANNOTATION_COLUMNS:
                raise ValueError("plantdoc_annotation_columns_mismatch")
            grouped: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
            for row_number, row in enumerate(reader, start=2):
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("plantdoc_annotation_row_malformed")
                filename = row["filename"]
                if PurePosixPath(filename).name != filename:
                    raise ValueError("plantdoc_image_filename_is_invalid")
                grouped[filename].append((row_number, row))
            for filename, rows in grouped.items():
                images.append(_read_image(archive, members, root, split, filename, csv_name, rows))
    return PlantDocDataset(
        archive_path=archive_path.resolve(),
        revision=REVISION,
        archive_sha256=archive_hash,
        license_id="CC-BY-4.0",
        license_sha256=LICENSE_SHA256,
        license_text=license_bytes.decode("utf-8"),
        annotation_sha256=annotation_hashes,
        images=tuple(_flag_annotation_conflicts(images)),
    )


def _flag_annotation_conflicts(images: list[PlantDocImage]) -> list[PlantDocImage]:
    aliases: dict[str, list[PlantDocImage]] = defaultdict(list)
    for image in images:
        if image.image_sha256 is not None:
            aliases[image.image_sha256].append(image)
    conflicts = {
        content_hash for content_hash, versions in aliases.items()
        if any(
            sorted((finding.label, finding.bbox_pixels) for finding in image.findings)
            != sorted((finding.label, finding.bbox_pixels) for finding in versions[0].findings)
            for image in versions[1:]
        )
    }
    return [
        replace(image, issues=(*image.issues, "duplicate_image_annotations_disagree"))
        if image.image_sha256 in conflicts else image
        for image in images
    ]


def _read_image(
    archive: ZipFile,
    members: set[str],
    root: str,
    split: str,
    filename: str,
    csv_name: str,
    rows: list[tuple[int, dict[str, str]]],
) -> PlantDocImage:
    width, height = int(rows[0][1]["width"]), int(rows[0][1]["height"])
    findings = tuple(
        PlantDocFinding(
            label=row["class"],
            bbox_pixels=(
                int(row["xmin"]), int(row["ymin"]), int(row["xmax"]), int(row["ymax"])
            ),
            source_annotation_id=f"{SOURCE_URL}/blob/{REVISION}/{csv_name}#row={row_number}",
            original_annotation=dict(row),
        )
        for row_number, row in rows
    )
    species = tuple(sorted({SPECIES_BY_LABEL[finding.label] for finding in findings}))
    member = f"{root}/{split}/{filename}"
    issues: list[str] = []
    if width <= 0 or height <= 0:
        issues.append("annotation_dimensions_invalid")
    if any((int(row["width"]), int(row["height"])) != (width, height) for _, row in rows):
        issues.append("annotation_dimensions_disagree")
    if not 1 <= len(findings) <= 100:
        issues.append("finding_count_outside_evaluator_contract")
    identities = [(finding.label, finding.bbox_pixels) for finding in findings]
    if len(set(identities)) != len(identities):
        issues.append("duplicate_annotation")
    if any(
        not (0 <= xmin < xmax <= width and 0 <= ymin < ymax <= height)
        for _, (xmin, ymin, xmax, ymax) in identities
    ):
        issues.append("bbox_outside_image")
    image_hash: str | None = None
    size_bytes: int | None = None
    mime_type: str | None = None
    if member in members:
        image_bytes = archive.read(member)
        image_hash = sha256(image_bytes).hexdigest()
        size_bytes = len(image_bytes)
        with Image.open(io.BytesIO(image_bytes)) as image:
            if image.size != (width, height):
                issues.append("image_dimensions_disagree")
            mime_type = Image.MIME.get(image.format or "")
            if mime_type not in {"image/jpeg", "image/png"}:
                issues.append("image_format_outside_evaluator_contract")
            image.verify()
    else:
        issues.append("source_image_missing")
    xml_member = str(PurePosixPath(member).with_suffix(".xml"))
    original_xml: str | None = None
    xml_hash: str | None = None
    if xml_member in members:
        xml_bytes = archive.read(xml_member)
        original_xml = xml_bytes.decode("utf-8")
        xml_hash = sha256(xml_bytes).hexdigest()
        annotation = ElementTree.fromstring(xml_bytes)
        xml_findings = Counter(
            (
                item.findtext("name"),
                tuple(int(_xml_text(item, f"bndbox/{key}")) for key in (
                    "xmin", "ymin", "xmax", "ymax"
                )),
            )
            for item in annotation.findall("object")
        )
        if xml_findings != Counter(identities):
            issues.append("xml_csv_annotations_disagree")
        if (
            int(_xml_text(annotation, "size/width")),
            int(_xml_text(annotation, "size/height")),
        ) != (width, height):
            issues.append("xml_dimensions_disagree")
    else:
        issues.append("source_xml_missing")
    return PlantDocImage(
        source_image_id=f"{SOURCE_URL}/blob/{REVISION}/{split}/{quote(filename, safe='')}",
        archive_member=member,
        split=split,
        filename=filename,
        width=width,
        height=height,
        plant_species=species[0] if len(species) == 1 else None,
        species_labels=species,
        findings=findings,
        image_sha256=image_hash,
        image_size_bytes=size_bytes,
        mime_type=mime_type,
        original_xml=original_xml,
        xml_sha256=xml_hash,
        issues=tuple(issues),
    )


def _xml_text(annotation: ElementTree.Element, path: str) -> str:
    value = annotation.findtext(path)
    if value is None:
        raise ValueError(f"plantdoc_xml_field_missing:{path}")
    return value


def select_cases(
    dataset: PlantDocDataset, *, sample_count: int, seed: str
) -> tuple[PlantDocImage, ...]:
    if not 600 <= sample_count <= 1000 or not seed.strip():
        raise ValueError("plantdoc_sampling_configuration_is_invalid")
    queues: dict[str, list[PlantDocImage]] = defaultdict(list)
    for image in dataset.images:
        if image.valid:
            for label in {finding.label for finding in image.findings}:
                queues[label].append(image)

    def rank(image: PlantDocImage) -> str:
        return sha256(f"{seed}\0{image.source_image_id}".encode()).hexdigest()

    for queue in queues.values():
        queue.sort(key=rank)
    class_order = sorted(queues, key=lambda label: (len(queues[label]), label))
    selected: list[PlantDocImage] = []
    content_hashes: set[str] = set()
    offsets = dict.fromkeys(class_order, 0)
    while len(selected) < sample_count:
        progress = False
        for label in class_order:
            queue = queues[label]
            offset = offsets[label]
            while offset < len(queue) and queue[offset].image_sha256 in content_hashes:
                offset += 1
            if offset < len(queue):
                image = queue[offset]
                selected.append(image)
                if image.image_sha256 is None:
                    raise ValueError("plantdoc_valid_image_has_no_checksum")
                content_hashes.add(image.image_sha256)
                progress = True
                offset += 1
            offsets[label] = offset
            if len(selected) == sample_count:
                break
        if not progress:
            raise ValueError("plantdoc_insufficient_valid_unique_images")
    return tuple(selected)


def export_candidates(
    dataset: PlantDocDataset,
    cases: tuple[PlantDocImage, ...],
    *,
    output: Path,
    seed: str,
) -> str:
    if cases != select_cases(dataset, sample_count=len(cases), seed=seed):
        raise ValueError("plantdoc_candidate_selection_mismatch")
    records: list[dict[str, object]] = []
    with ZipFile(dataset.archive_path) as archive:
        for image in cases:
            content = archive.read(image.archive_member)
            if sha256(content).hexdigest() != image.image_sha256:
                raise ValueError("plantdoc_image_checksum_mismatch")
            suffix = ".jpg" if image.mime_type == "image/jpeg" else ".png"
            image_file = f"images/{image.image_sha256}{suffix}"
            _write_artifact(output / image_file, content)
            record: dict[str, object] = asdict(image)
            record["image_file"] = image_file
            record["species_origin"] = "derived_from_original_class_label"
            record["expected_findings"] = [
                {
                    "label": finding.label,
                    "region": finding.normalized_region(image.width, image.height),
                }
                for finding in image.findings
            ]
            records.append(record)
    _write_artifact(output / "LICENSE.txt", dataset.license_text.encode("utf-8"))
    manifest = {
        "import_version": IMPORT_VERSION,
        "review_status": "PENDING_REVIEW",
        "formal_suite_id": None,
        "sample_count": len(cases),
        "sampling": {
            "seed": seed,
            "rule": (
                "SHA256(seed + NUL + encoded source image URL), "
                "class round-robin by ascending available image count then original class name; "
                "deduplicate image SHA256; retain all original findings"
            ),
        },
        "source": {
            "dataset": "PlantDoc Object Detection",
            "url": SOURCE_URL,
            "revision": dataset.revision,
            "archive_sha256": dataset.archive_sha256,
            "annotation_sha256": dataset.annotation_sha256,
            "license": dataset.license_id,
            "license_sha256": dataset.license_sha256,
            "attribution": ATTRIBUTION,
            "annotation_scope": "source class-labelled object boxes; lesion extent not asserted",
            "transformations": "deterministic image selection and pixel XYXY to normalized XYWH",
        },
        "source_quality": {
            "image_record_count": len(dataset.images),
            "finding_count": sum(len(image.findings) for image in dataset.images),
            "valid_image_record_count": sum(image.valid for image in dataset.images),
            "excluded": [asdict(image) for image in dataset.images if not image.valid],
        },
        "cases": records,
    }
    content = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    _write_artifact(output / "manifest.json", content)
    return sha256(content).hexdigest()


def _write_artifact(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"plantdoc_existing_artifact_mismatch:{path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(content)
