"""Unified local HTTP peer for the platform's existing enterprise adapters."""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from industrial_ops_agent.sandbox.state import SandboxState

_ASSET_ID = "asset-m1-pump"
_TENANT_ID = "tenant-m1-demo"
_SITE_ID = "site-m1-demo"
_ENGINEER_ID = "subject-m1-engineer"
_CUSTOMER_ID = "customer-m1-demo"
_PART_NUMBER = "BRG-6312-C3"
_PROVIDERS = frozenset({"eam", "wms", "schedule"})
_READ_FAULTS = frozenset({"UNAVAILABLE", "STALE"})


@dataclass(frozen=True, slots=True)
class SandboxSettings:
    """Validated settings with secret fields excluded from representations."""

    enabled: bool
    environment: str
    enterprise_token: str = field(repr=False)
    control_token: str = field(repr=False)
    platform_api_url: str
    tenant_id: str = _TENANT_ID

    @classmethod
    def from_environment(cls) -> SandboxSettings:
        enabled = os.environ.get("IOAP_SANDBOX_ENABLED", "").strip().lower() == "true"
        environment = os.environ.get("IOAP_ENVIRONMENT", "").strip().lower()
        if not enabled:
            raise ValueError("enterprise sandbox must be explicitly enabled")
        if environment not in {"local", "test"}:
            raise ValueError("enterprise sandbox is restricted to local/test environments")

        required = {
            "enterprise_token": "IOAP_ENTERPRISE_TOOL_GATEWAY_TOKEN",
            "control_token": "IOAP_SANDBOX_CONTROL_TOKEN",
            "platform_api_url": "IOAP_SANDBOX_PLATFORM_API_URL",
        }
        values = {name: os.environ.get(key, "").strip() for name, key in required.items()}
        if any(not value for value in values.values()):
            raise ValueError("missing required sandbox secret or endpoint configuration")
        access_tokens = [
            values["enterprise_token"],
            values["control_token"],
        ]
        if len(set(access_tokens)) != len(access_tokens):
            raise ValueError("sandbox provider and control tokens must be distinct")
        return cls(
            enabled=enabled,
            environment=environment,
            enterprise_token=values["enterprise_token"],
            control_token=values["control_token"],
            platform_api_url=values["platform_api_url"].rstrip("/"),
            tenant_id=os.environ.get("IOAP_SANDBOX_TENANT_ID", _TENANT_ID).strip(),
        )


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _FaultRequest(_StrictRequest):
    mode: Literal["UNAVAILABLE", "REJECT", "OUTCOME_UNKNOWN", "STALE"]
    remaining: int = Field(ge=1, le=10)






def create_app(
    settings: SandboxSettings,
    *,
    state: SandboxState | None = None,
) -> FastAPI:
    """Create an explicitly non-production sandbox application."""

    if not settings.enabled or settings.environment not in {"local", "test"}:
        raise ValueError("enterprise sandbox is restricted to local/test environments")
    sandbox_state = state or SandboxState()
    started_at = datetime.now(UTC).replace(microsecond=0)
    application = FastAPI(
        title="Enterprise Integration Sandbox",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.sandbox = sandbox_state
    application.state.classification = "SIMULATED_NON_PRODUCTION"

    @application.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "live", "classification": "SIMULATED_NON_PRODUCTION"}

    @application.get("/health/ready")
    def ready() -> dict[str, str]:
        return {"status": "ready", "classification": "SIMULATED_NON_PRODUCTION"}

    @application.get("/sandbox/v1/state")
    def control_state(request: Request) -> dict[str, object]:
        _require_bearer(request, settings.control_token)
        return sandbox_state.snapshot()

    @application.post("/sandbox/v1/reset")
    def control_reset(request: Request) -> dict[str, object]:
        _require_bearer(request, settings.control_token)
        sandbox_state.reset()
        return sandbox_state.snapshot()

    @application.put("/sandbox/v1/faults/{provider}")
    def control_fault(
        provider: str,
        body: _FaultRequest,
        request: Request,
    ) -> dict[str, object]:
        _require_bearer(request, settings.control_token)
        _require_provider(provider)
        sandbox_state.configure_fault(provider, body.mode, body.remaining)
        return sandbox_state.snapshot()

    @application.delete("/sandbox/v1/faults/{provider}")
    def control_clear_fault(provider: str, request: Request) -> dict[str, object]:
        _require_bearer(request, settings.control_token)
        _require_provider(provider)
        sandbox_state.clear_fault(provider)
        return sandbox_state.snapshot()



    @application.get("/v1/assets/{asset_id}")
    def asset(asset_id: str, request: Request) -> dict[str, object]:
        _require_bearer(request, settings.enterprise_token)
        _require_asset(asset_id)
        return {
            "source_record_id": f"sandbox-eam-{asset_id}",
            "as_of": _time(_read_time(sandbox_state, "eam", started_at)),
            "model_code": "PUMP-X100",
            "lifecycle_status": "ACTIVE",
        }

    @application.get("/v1/warranties/by-asset/{asset_id}")
    def warranty(asset_id: str, request: Request) -> dict[str, object]:
        _require_bearer(request, settings.enterprise_token)
        _require_asset(asset_id)
        return {
            "source_record_id": f"sandbox-warranty-{asset_id}",
            "as_of": _time(_read_time(sandbox_state, "eam", started_at)),
            "coverage": "PARTS_AND_LABOR",
            "valid": True,
        }

    @application.get("/v1/parts/availability")
    def parts_for_asset(request: Request, asset_id: str) -> dict[str, object]:
        _require_bearer(request, settings.enterprise_token)
        _require_asset(asset_id)
        return {
            "source_record_id": f"sandbox-wms-{asset_id}-{_PART_NUMBER}",
            "as_of": _time(_read_time(sandbox_state, "wms", started_at)),
            "part_number": _PART_NUMBER,
            "available_quantity": 24,
        }

    @application.get("/v1/schedules/availability")
    def schedule(request: Request, asset_id: str) -> dict[str, object]:
        _require_bearer(request, settings.enterprise_token)
        _require_asset(asset_id)
        return {
            "source_record_id": f"sandbox-schedule-{asset_id}",
            "as_of": _time(_read_time(sandbox_state, "schedule", started_at)),
            "site_id": _SITE_ID,
            "next_available_start": _time(started_at + timedelta(hours=2)),
            "next_available_end": _time(started_at + timedelta(hours=6)),
            "available_technician_count": 3,
        }

    @application.get("/v1/work-orders/history")
    def work_order_history(request: Request, asset_id: str) -> dict[str, object]:
        _require_bearer(request, settings.enterprise_token)
        _require_asset(asset_id)
        return {
            "source_record_id": f"sandbox-work-order-history-{asset_id}",
            "as_of": _time(_read_time(sandbox_state, "schedule", started_at)),
            "recent_count": 2,
            "latest_resolution": "Bearing replaced and alignment verified",
        }

    @application.get("/v1/parts/{part_number}/availability")
    def part_availability(
        part_number: str,
        request: Request,
        quantity: int = Query(ge=1, le=20),
    ) -> dict[str, object]:
        _require_bearer(request, settings.enterprise_token)
        if part_number != _PART_NUMBER:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "synthetic part not found")
        return {
            "source_record_id": f"sandbox-wms-part-{part_number}",
            "as_of": _time(_read_time(sandbox_state, "wms", started_at)),
            "part_number": part_number,
            "requested_quantity": quantity,
            "available_quantity": 24,
            "available": quantity <= 24,
        }

    # Parts mutation endpoints were removed with Batch 3C.













    return application


def _require_bearer(request: Request, expected_token: str) -> None:
    authorization = request.headers.get("Authorization", "")
    expected = f"Bearer {expected_token}"
    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid provider credential")


def _require_asset(asset_id: str) -> None:
    if asset_id != _ASSET_ID:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "synthetic asset not found")


def _require_context(*, tenant_id: str, asset_id: str, site_id: str) -> None:
    if tenant_id != _TENANT_ID or asset_id != _ASSET_ID or site_id != _SITE_ID:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "synthetic context not found")


def _require_provider(provider: str) -> None:
    if provider not in _PROVIDERS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sandbox provider not found")


def _read_time(state: SandboxState, provider: str, current: datetime) -> datetime:
    fault = state.consume_fault(provider, _READ_FAULTS)
    if fault == "UNAVAILABLE":
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "simulated provider unavailable")
    return current - timedelta(days=2) if fault == "STALE" else current

def _time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


app = create_app(SandboxSettings.from_environment())
