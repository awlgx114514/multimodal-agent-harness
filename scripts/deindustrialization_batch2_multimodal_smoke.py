"""Structural contract smoke for the Batch 2 multimodal boundary."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MULTIMODAL = ROOT / "src" / "industrial_ops_agent" / "multimodal"


def _names(path: Path) -> set[str]:
    return {
        node.name
        for node in ast.parse(path.read_text(encoding="utf-8")).body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }


def main() -> None:
    models = MULTIMODAL / "models.py"
    processor = MULTIMODAL / "processor.py"
    required = {"PerceptionResult"}
    missing = required - _names(models)
    if missing:
        raise AssertionError(f"generic multimodal contracts missing: {sorted(missing)}")
    if "EvidenceBundle" in _names(models):
        raise AssertionError("generic multimodal models still own EvidenceBundle")
    for path in (models, processor, MULTIMODAL / "providers.py", MULTIMODAL / "video.py"):
        source = path.read_text(encoding="utf-8")
        if "asset_model" in source:
            raise AssertionError(f"{path.relative_to(ROOT)} still requires asset_model")
    print("DEINDUSTRIALIZATION_BATCH2_MULTIMODAL_PASS")


if __name__ == "__main__":
    main()
