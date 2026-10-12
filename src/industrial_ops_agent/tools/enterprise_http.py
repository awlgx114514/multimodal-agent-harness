"""Strict read-only HTTP adapter for enterprise Diagnosis facts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from json import JSONDecodeError
from typing import Any, Protocol, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from industrial_ops_agent.secrets import SecretValue
from industrial_ops_agent.tools.authority import attest_tool_fact, authoritative_source
from industrial_ops_agent.tools.contracts import (
    EnterpriseToolError,
    ToolTransportBinding,
)

_MAX_RESPONSE_BYTES = 64 * 1024
_ModelT = TypeVar("_ModelT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class EnterpriseHttpResponse:
    status_code: int
    body: bytes


class EnterpriseHttpTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any] | None,
        timeout_seconds: float,
    ) -> EnterpriseHttpResponse: ...


class EnterpriseTransportUnavailable(RuntimeError):
    pass


class UrllibEnterpriseHttpTransport:
    """One-request transport that does not retain credentials or response bodies."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any] | None,
        timeout_seconds: float,
    ) -> EnterpriseHttpResponse:
        body = (
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            if payload is not None
            else None
        )
        request_headers = {"Accept": "application/json", **headers}
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        request = Request(url, data=body, headers=request_headers, method=method)  # noqa: S310
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                return EnterpriseHttpResponse(response.status, _bounded_read(response))
        except HTTPError as exc:
            return EnterpriseHttpResponse(exc.code, _bounded_read(exc))
        except (URLError, TimeoutError, OSError) as exc:
            raise EnterpriseTransportUnavailable from exc


class _SourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_record_id: str = Field(min_length=1, max_length=255)
    as_of: datetime

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must include a timezone")
        return value


class _AssetResponse(_SourceRecord):
    model_code: str = Field(min_length=1, max_length=128)
    lifecycle_status: str = Field(min_length=1, max_length=64)


class _WarrantyResponse(_SourceRecord):
    coverage: str = Field(min_length=1, max_length=128)
    valid: bool


class _PartsByAssetResponse(_SourceRecord):
    part_number: str = Field(pattern=r"^[A-Z0-9-]{3,64}$")
    available_quantity: int = Field(ge=0, le=1_000_000)


class _ScheduleAvailabilityResponse(_SourceRecord):
    site_id: str = Field(min_length=1, max_length=255)
    next_available_start: datetime
    next_available_end: datetime
    available_technician_count: int = Field(ge=0, le=10_000)

    @field_validator("next_available_start", "next_available_end")
    @classmethod
    def require_window_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("schedule window must include a timezone")
        return value


class _WorkOrderHistoryResponse(_SourceRecord):
    recent_count: int = Field(ge=0, le=10_000)
    latest_resolution: str | None = Field(default=None, max_length=2_000)


_READONLY_RESPONSE_TYPES: dict[str, type[_SourceRecord]] = {
    "asset.get": _AssetResponse,
    "warranty.get": _WarrantyResponse,
    "parts.availability": _PartsByAssetResponse,
    "schedule.availability": _ScheduleAvailabilityResponse,
    "work_orders.history": _WorkOrderHistoryResponse,
}


class EnterpriseHttpAdapter:
    """Whitelisted read-only operations over one authenticated enterprise gateway."""

    def __init__(
        self,
        base_url: str,
        api_token: SecretValue,
        *,
        timeout_seconds: float = 5.0,
        allow_plain_http: bool = False,
        transport: EnterpriseHttpTransport | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        if not parsed.netloc or parsed.query or parsed.fragment or parsed.username:
            raise ValueError("enterprise tool gateway URL is invalid")
        if parsed.scheme != "https" and not (
            allow_plain_http
            and parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost", "enterprise-tool-gateway"}
        ):
            raise ValueError("enterprise tool gateway must use HTTPS")
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        self._timeout_seconds = timeout_seconds
        self._transport = transport or UrllibEnterpriseHttpTransport()

    def invoke(self, tool_id: str, parameters: dict[str, Any]) -> dict[str, Any]:
        asset_id = quote(str(parameters["asset_id"]), safe="")
        raw_asset_id = str(parameters["asset_id"])
        routes: dict[str, str] = {
            "asset.get": f"/v1/assets/{asset_id}",
            "warranty.get": f"/v1/warranties/by-asset/{asset_id}",
            "parts.availability": (
                f"/v1/parts/availability?{urlencode({'asset_id': raw_asset_id})}"
            ),
            "schedule.availability": (
                f"/v1/schedules/availability?{urlencode({'asset_id': raw_asset_id})}"
            ),
            "work_orders.history": (
                f"/v1/work-orders/history?{urlencode({'asset_id': raw_asset_id})}"
            ),
        }
        try:
            route = routes[tool_id]
        except KeyError as exc:
            raise EnterpriseToolError("enterprise_tool_not_supported") from exc
        response = self._request("GET", route)
        if response.status_code != 200:
            raise EnterpriseToolError("enterprise_tool_http_status")
        try:
            payload = json.loads(response.body)
        except (JSONDecodeError, UnicodeDecodeError) as exc:
            raise EnterpriseToolError("enterprise_tool_response_invalid") from exc
        if not isinstance(payload, dict):
            raise EnterpriseToolError("enterprise_tool_response_invalid")
        return normalize_enterprise_readonly_payload(tool_id, payload)

    def transport_binding(self, tool_id: str) -> ToolTransportBinding:
        if tool_id not in _READONLY_RESPONSE_TYPES:
            raise EnterpriseToolError("enterprise_tool_not_supported")
        return ToolTransportBinding(
            transport="ENTERPRISE_HTTP",
            local_tool_id=tool_id,
            remote_tool_name=tool_id,
            server_id="enterprise-tool-gateway",
            server_version="rest-v1",
        )

    def _request(
        self,
        method: str,
        route: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> EnterpriseHttpResponse:
        headers = {"Authorization": f"Bearer {self._api_token.reveal()}"}
        try:
            return self._transport.request(
                method,
                f"{self._base_url}{route}",
                headers=headers,
                payload=payload,
                timeout_seconds=self._timeout_seconds,
            )
        except EnterpriseTransportUnavailable as exc:
            raise EnterpriseToolError("enterprise_tool_unavailable") from exc


def _decode_model(
    response: EnterpriseHttpResponse,
    model_type: type[_ModelT],
) -> _ModelT:
    if response.status_code != 200:
        raise EnterpriseToolError("enterprise_tool_http_status")
    try:
        payload = json.loads(response.body)
        if not isinstance(payload, dict):
            raise TypeError
        return model_type.model_validate(payload)
    except (JSONDecodeError, UnicodeDecodeError, TypeError, ValidationError) as exc:
        raise EnterpriseToolError("enterprise_tool_response_invalid") from exc


def normalize_enterprise_readonly_payload(
    tool_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Validate an untrusted enterprise payload before authority attestation."""

    try:
        response_type = _READONLY_RESPONSE_TYPES[tool_id]
    except KeyError as exc:
        raise EnterpriseToolError("enterprise_tool_not_supported") from exc
    try:
        model = response_type.model_validate(payload)
    except ValidationError as exc:
        raise EnterpriseToolError("enterprise_tool_response_invalid") from exc
    return attest_tool_fact(
        tool_id,
        {
            **model.model_dump(mode="json"),
            "source": authoritative_source(tool_id, "enterprise"),
        },
        profile="enterprise",
    )


def _bounded_read(response: Any) -> bytes:
    body = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(body) > _MAX_RESPONSE_BYTES:
        raise EnterpriseToolError("enterprise_tool_response_too_large")
    return body
