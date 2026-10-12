"""Mechanical Batch 3E surface and dependency smoke checks."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_ROOTS = ("src", "web", "infra", "docker")
FORBIDDEN = re.compile(
    r"graph_rag|graphrag|neo4j|knowledge_graph|graph_extraction|"
    r"realtime[-_]session|realtime-media|webrtc|stun|turn_shared|coturn|aiortc|media-server",
    re.IGNORECASE,
)


def _active_text() -> str:
    chunks: list[str] = []
    for root_name in ACTIVE_ROOTS:
        root = ROOT / root_name
        for path in root.rglob("*"):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or "generated" in path.parts
                or "observability" in path.parts
                or "node_modules" in path.parts
                or ".next" in path.parts
                or path.suffix in {".pyc", ".map"}
            ):
                continue
            chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    for path in (
        ROOT / "pyproject.toml",
        ROOT / ".env.example",
        ROOT / "contracts" / "openapi.json",
    ):
        chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks)


def main() -> None:
    active_text = _active_text()
    forbidden = FORBIDDEN.search(active_text)
    assert forbidden is None, f"retired active surface remains: {forbidden.group(0)}"

    for relative in (
        "src/industrial_ops_agent/graph_rag",
        "src/industrial_ops_agent/realtime_media",
        "src/industrial_ops_agent/multimodal/realtime.py",
        "web/app/ai/knowledge/graph",
        "web/app/portal",
        "web/app/parts",
        "web/app/entitlements",
        "web/app/ops/service-performance",
        "web/components/m3/RealtimeAudioPanel.tsx",
        "compose.realtime.yaml",
        "docker/media-server.Dockerfile",
    ):
        retired_path = ROOT / relative
        assert not retired_path.is_file() and not any(
            child.is_file() and "__pycache__" not in child.parts
            for child in retired_path.rglob("*")
        ), (
            f"retired path remains: {relative}"
        )

    transcript_service = ROOT / "src/industrial_ops_agent/multimodal/realtime_transcripts.py"
    transcript_route = ROOT / "src/industrial_ops_agent/api/routes/realtime.py"
    config = ROOT / "src/industrial_ops_agent/config.py"
    runtime = ROOT / "src/industrial_ops_agent/runtime.py"
    runner = ROOT / "src/industrial_ops_agent/orchestration/runner.py"
    assert "class RealtimeTranscriptService" in transcript_service.read_text(encoding="utf-8")
    assert "agent.user_input.confirmed" in transcript_service.read_text(encoding="utf-8")
    assert "/transcript-streams/{stream_id}/segments" in transcript_route.read_text(
        encoding="utf-8"
    )
    assert "knowledge_search_profiles_enabled: bool = False" in config.read_text(encoding="utf-8")
    assert "RealtimeTranscriptService" in runtime.read_text(encoding="utf-8")
    assert "TranscriptionGateway" in runner.read_text(encoding="utf-8")

    openapi = (ROOT / "contracts" / "openapi.json").read_text(encoding="utf-8")
    assert "/realtime-sessions" not in openapi
    assert "/realtime-transcripts" not in openapi
    assert "knowledge-graphs" not in openapi
    assert "/portal" not in openapi
    assert "/service-entitlements" not in openapi
    assert "/operations/service-performance" not in openapi
    assert "/diagnosis-runs/{diagnosis_run_id}/speech" not in openapi

    retained_paths = [
        path
        for relative in (
            "src/industrial_ops_agent/training",
            "src/industrial_ops_agent/model_gateway/service.py",
            "src/industrial_ops_agent/knowledge/retrieval.py",
        )
        for path in (
            (ROOT / relative).rglob("*")
            if (ROOT / relative).is_dir()
            else [ROOT / relative]
        )
        if path.is_file()
    ]
    retained = " ".join(
        path.read_text(encoding="utf-8", errors="ignore") for path in retained_paths
    )
    assert "SFT" in retained and "DPO" in retained and "PPO" in retained and "GRPO" in retained
    assert "ModelGateway" in retained
    print("DEINDUSTRIALIZATION_BATCH3E_SURFACE_PASS")


if __name__ == "__main__":
    main()
