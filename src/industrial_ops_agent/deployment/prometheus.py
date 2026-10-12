"""Prometheus/DCGM collector for trusted online release observations."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

import httpx

from industrial_ops_agent.deployment.service import ObservationInput, OnlineDeploymentStage
from industrial_ops_agent.domain import as_utc as _as_utc

QUERY_TEMPLATES: dict[str, str] = {
    "request_count": (
        'sum(increase(ioap_inference_requests_total{release_id="__RELEASE__"}[__WINDOW__s]))'
    ),
    "critical_case_count": (
        'sum(increase(ioap_critical_cases_total{release_id="__RELEASE__"}[__WINDOW__s]))'
    ),
    "cross_tenant_leak_count": (
        'sum(increase(ioap_security_findings_total{release_id="__RELEASE__",finding="cross_tenant_leak"}[__WINDOW__s]))'
    ),
    "unauthorized_side_effect_count": (
        'sum(increase(ioap_security_findings_total{release_id="__RELEASE__",finding="unauthorized_side_effect"}[__WINDOW__s]))'
    ),
    "high_risk_miss_rate": (
        'sum(increase(ioap_high_risk_misses_total{release_id="__RELEASE__"}[__WINDOW__s])) '
        "/ clamp_min(sum(increase(ioap_high_risk_cases_total"
        '{release_id="__RELEASE__"}[__WINDOW__s])), 1)'
    ),
    "task_success_delta": (
        'avg(ioap_task_success_ratio{release_id="__RELEASE__"}) '
        '- avg(ioap_task_success_ratio{release_id="baseline"})'
    ),
    "error_rate": (
        'sum(rate(ioap_inference_requests_total{release_id="__RELEASE__",status="error"}[5m])) '
        "/ clamp_min(sum(rate(ioap_inference_requests_total"
        '{release_id="__RELEASE__"}[5m])), 0.000001)'
    ),
    "p95_latency_ms": (
        "histogram_quantile(0.95, sum(rate(ioap_inference_latency_seconds_bucket"
        '{release_id="__RELEASE__"}[5m])) by (le)) * 1000'
    ),
    "human_edit_rate_delta": (
        'avg(ioap_human_edit_ratio{release_id="__RELEASE__"}) '
        '- avg(ioap_human_edit_ratio{release_id="baseline"})'
    ),
    "wrong_part_rate": (
        'sum(increase(ioap_wrong_part_total{release_id="__RELEASE__"}[__WINDOW__s])) '
        "/ clamp_min(sum(increase(ioap_part_recommendations_total"
        '{release_id="__RELEASE__"}[__WINDOW__s])), 1)'
    ),
    "gpu_xid_error_count": (
        'sum(increase(DCGM_FI_DEV_XID_ERRORS{release_id="__RELEASE__"}[__WINDOW__s]))'
    ),
    "gpu_memory_utilization": (
        'max(DCGM_FI_DEV_FB_USED{release_id="__RELEASE__"} '
        '/ clamp_min(DCGM_FI_DEV_FB_TOTAL{release_id="__RELEASE__"}, 1))'
    ),
    "queue_age_seconds": ('max(ioap_inference_queue_oldest_age_seconds{release_id="__RELEASE__"})'),
}
class PrometheusUnavailable(RuntimeError):
    pass


@dataclass(slots=True)
class PrometheusObservationCollector:
    base_url: str
    bearer_token: str | None = None
    verify: str | bool = True
    timeout_seconds: float = 5.0
    collector_version: str = "prometheus-dcgm-v2"

    def collect(
        self,
        *,
        release_id: str,
        stage: OnlineDeploymentStage,
        window_start: datetime,
        window_end: datetime,
    ) -> ObservationInput:
        start = _as_utc(window_start)
        end = _as_utc(window_end)
        window_seconds = int((end - start).total_seconds())
        if window_seconds < 1 or end > datetime.now(UTC):
            raise ValueError("Prometheus observation window is invalid")
        safe_characters = "abcdefghijklmnopqrstuvwxyz0123456789-_"
        if not release_id or any(character not in safe_characters for character in release_id):
            raise ValueError("release_id is unsafe for a Prometheus label matcher")
        templates = dict(QUERY_TEMPLATES)
        queries = {
            name: template.replace("__RELEASE__", release_id).replace(
                "__WINDOW__", str(window_seconds)
            )
            for name, template in templates.items()
        }
        values = {name: self._query_scalar(query, end) for name, query in queries.items()}
        request_count = _whole_count(values.pop("request_count"), "request_count")
        critical_case_count = _whole_count(values.pop("critical_case_count"), "critical_case_count")
        bundle_hash = _digest_json(queries)
        trace_query_names = [
            "cross_tenant_leak_count",
            "unauthorized_side_effect_count",
            "high_risk_miss_rate",
            "task_success_delta",
            "human_edit_rate_delta",
            "wrong_part_rate",
        ]
        trace_queries = {key: queries[key] for key in trace_query_names}
        return ObservationInput(
            stage=stage,
            window_start=start,
            window_end=end,
            request_count=request_count,
            critical_case_count=critical_case_count,
            metrics=values,
            source_refs={
                "collector_version": self.collector_version,
                "prometheus_endpoint_id": (
                    f"prometheus:{sha256(self.base_url.encode()).hexdigest()[:24]}"
                ),
                "prometheus_query_bundle_hash": f"sha256:{bundle_hash}",
                "trace_query_hash": f"sha256:{_digest_json(trace_queries)}",
            },
        )

    def _query_scalar(self, query: str, at: datetime) -> float:
        headers = (
            {"Authorization": f"Bearer {self.bearer_token}"}
            if self.bearer_token is not None
            else None
        )
        try:
            response = httpx.get(
                f"{self.base_url.rstrip('/')}/api/v1/query",
                params={"query": query, "time": at.isoformat()},
                headers=headers,
                verify=self.verify,
                timeout=httpx.Timeout(self.timeout_seconds),
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise PrometheusUnavailable("prometheus_query_failed") from exc
        try:
            if payload["status"] != "success":
                raise KeyError
            data = payload["data"]
            result_type = data["resultType"]
            if result_type == "scalar":
                raw_value = data["result"][1]
            elif result_type == "vector" and len(data["result"]) == 1:
                raw_value = data["result"][0]["value"][1]
            else:
                raise KeyError
            value = float(raw_value)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise PrometheusUnavailable("prometheus_result_not_scalar") from exc
        if not math.isfinite(value):
            raise PrometheusUnavailable("prometheus_result_not_finite")
        return value


def _whole_count(value: float, field: str) -> int:
    rounded = round(value)
    if value < 0 or abs(value - rounded) > 0.001:
        raise PrometheusUnavailable(f"prometheus_{field}_not_a_count")
    return int(rounded)


def _digest_json(document: Any) -> str:
    return sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
