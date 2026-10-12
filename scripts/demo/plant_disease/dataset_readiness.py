from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from industrial_ops_agent.plant_disease.dataset import (
    IMPORT_VERSION,
    REVISION,
    export_candidates,
    read_plantdoc,
    select_cases,
)


def main() -> None:
    repository = Path(__file__).resolve().parents[3]
    artifacts = repository / "artifacts" / "plant_disease"
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("readiness", "prepare-candidates"))
    parser.add_argument(
        "--archive", type=Path,
        default=(
            artifacts / "upstream" / REVISION
            / f"PlantDoc-Object-Detection-Dataset-{REVISION}.zip"
        ),
    )
    parser.add_argument("--sample-count", type=int, default=600)
    parser.add_argument("--seed", default="plant_disease_gold_v1")
    args = parser.parse_args()
    dataset = read_plantdoc(args.archive)
    cases = select_cases(dataset, sample_count=args.sample_count, seed=args.seed)
    result: dict[str, object] = {
        "SOURCE_READINESS": "PASS",
        "GOLD_STATUS": "NOT_APPROVED",
        "source_revision": dataset.revision,
        "archive_sha256": dataset.archive_sha256,
        "license": dataset.license_id,
        "source_image_records": len(dataset.images),
        "source_findings": sum(len(image.findings) for image in dataset.images),
        "valid_image_records": sum(image.valid for image in dataset.images),
        "quality_issues": dict(Counter(
            issue for image in dataset.images for issue in image.issues
        )),
        "candidate_count": len(cases),
        "candidate_findings": sum(len(image.findings) for image in cases),
        "candidate_classes": dict(sorted(Counter(
            finding.label for image in cases for finding in image.findings
        ).items())),
    }
    if args.command == "prepare-candidates":
        output = artifacts / "candidates" / IMPORT_VERSION / f"{args.seed}-{args.sample_count}"
        if not output.resolve().is_relative_to((artifacts / "candidates").resolve()):
            raise ValueError("plantdoc_candidate_output_outside_artifact_directory")
        result["manifest_sha256"] = export_candidates(
            dataset, cases, output=output, seed=args.seed
        )
        result["output"] = str(output.resolve())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
