"""RED/GREEN contract smoke for the predictive-maintenance deletion boundary."""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "industrial_ops_agent"
WEB = ROOT / "web"
AIRFLOW = ROOT / "airflow" / "dags"
DOCKER = ROOT / "docker"

GENERIC_METHODS = {"SFT", "DPO", "PPO", "GRPO"}
PREDICTIVE_MARKERS = (
    "predictive_maintenance",
    "PredictiveMaintenanceService",
    "TelemetryEventInput",
    "ReplaySafeTelemetryConsumer",
    "TimeseriesDetector",
    "RUL",
    "Rul",
    "telemetry_dataset",
    "rul_dataset",
)
PREDICTIVE_TABLES = {
    "telemetry_events",
    "telemetry_stream_states",
    "telemetry_windows",
    "alert_candidates",
    "alert_candidate_decisions",
    "predictive_maintenance_referrals",
    "predictive_outcomes",
    "rul_forecast_candidates",
    "rul_forecast_calibrations",
}


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _airflow_dag_ids() -> set[str]:
    result: set[str] = set()
    for path in AIRFLOW.glob("*.py"):
        tree = ast.parse(_source(path), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "DAG"
            ):
                if node.args and isinstance(node.args[0], ast.Constant):
                    result.add(str(node.args[0].value))
                for keyword in node.keywords:
                    if keyword.arg == "dag_id" and isinstance(keyword.value, ast.Constant):
                        result.add(str(keyword.value.value))
    return result


def _model_table_names() -> set[str]:
    source = _source(SRC / "persistence" / "models.py")
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "__tablename__"
            for target in node.targets
        ):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            names.add(node.value.value)
    return names


def _assert_no_active_kafka_predictive_surface() -> None:
    paths = [
        ROOT / "compose.integration.yaml",
        ROOT / "compose.observability.yaml",
        ROOT / "pyproject.toml",
        ROOT / "infra" / "debezium" / "register.sh",
        ROOT / "infra" / "debezium" / "connectors" / "industrial-ops-outbox.json",
        ROOT / "infra" / "debezium" / "topics" / "ops-work-order-v1.properties",
    ]
    for path in paths:
        source = _source(path).lower()
        assert "ops.telemetry.v1" not in source, f"telemetry topic remains in {path}"
        assert "ops.work-order.v1" not in source, f"work-order topic remains in {path}"
        assert "debezium" not in source, f"Debezium surface remains in {path}"


def main() -> None:
    assert not list((SRC / "predictive_maintenance").glob("*.py"))
    assert not (SRC / "api" / "routes" / "predictive_maintenance.py").exists()
    assert not list((WEB / "app" / "predictive-maintenance").glob("*"))
    assert not list((SRC / "event_worker").glob("*.py"))
    assert not (ROOT / "scripts" / "m3_integration_probe.py").exists()
    assert not (DOCKER / "event-worker.Dockerfile").exists()
    assert not any(DOCKER.glob("*rul*.Dockerfile"))
    assert not any(DOCKER.glob("*timeseries*.Dockerfile"))

    runtime_source = _source(SRC / "runtime.py")
    api_source = _source(SRC / "api" / "app.py")
    training_source = _source(SRC / "training" / "runner.py")
    experiment_source = _source(SRC / "experiments" / "service.py")
    release_source = _source(SRC / "api" / "routes" / "model_releases.py")
    for source_name, source in {
        "runtime.py": runtime_source,
        "api/app.py": api_source,
        "training/runner.py": training_source,
        "experiments/service.py": experiment_source,
        "model_releases.py": release_source,
    }.items():
        for marker in PREDICTIVE_MARKERS:
            assert marker not in source, f"predictive marker remains in {source_name}: {marker}"

    assert not (PREDICTIVE_TABLES & _model_table_names())
    assert {"build_dataset_snapshot", "retention_and_deletion"} <= _airflow_dag_ids()
    assert "build_telemetry_dataset_snapshot" not in _airflow_dag_ids()
    assert "build_rul_dataset_snapshot" not in _airflow_dag_ids()

    generic_training_source = "\n".join(
        _source(path)
        for path in (
            SRC / "training" / "config.py",
            SRC / "training" / "backend.py",
            SRC / "training" / "runner.py",
            SRC / "training" / "__init__.py",
            SRC / "experiments" / "service.py",
            SRC / "runtime_metrics.py",
        )
    )
    assert all(method in generic_training_source for method in GENERIC_METHODS)
    assert "compile_sft_config" in generic_training_source
    assert (SRC / "experiments" / "mlflow.py").is_file()
    assert (SRC / "training" / "reproducible_sandbox.py").is_file()
    assert (SRC / "releases" / "service.py").is_file()
    openapi = json.loads(_source(ROOT / "contracts" / "openapi.json"))
    assert not any(
        any(
            marker in path.lower()
            for marker in (
                "predictive-maintenance",
                "telemetry",
                "alert-candidate",
                "rul-forecast",
            )
        )
        for path in openapi.get("paths", {})
    )
    assert not any(
        any(
            marker in name.lower()
            for marker in (
                "predictive",
                "telemetry",
                "rulforecast",
                "alertcandidate",
                "detectionresponse",
            )
        )
        for name in openapi.get("components", {}).get("schemas", {})
    )
    _assert_no_active_kafka_predictive_surface()
    print("DEINDUSTRIALIZATION_BATCH3D_DELETION_PASS")


if __name__ == "__main__":
    main()
