from __future__ import annotations

import argparse
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="enterprise-sandbox")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("reset")
    fault = commands.add_parser("fault")
    fault.add_argument("provider")
    fault.add_argument("mode", choices=("UNAVAILABLE", "REJECT", "OUTCOME_UNKNOWN", "STALE"))
    fault.add_argument("remaining", type=int)
    commands.add_parser("clear-fault").add_argument("provider")
    commands.add_parser("verify")
    return parser


def _request(method: str, path: str, payload: dict[str, object] | None) -> object:
    token = os.environ.get("IOAP_SANDBOX_CONTROL_TOKEN", "")
    if not token:
        raise RuntimeError("sandbox control credential is not configured")
    base_url = os.environ.get("IOAP_SANDBOX_BASE_URL", "http://127.0.0.1:8090").rstrip("/")
    raw = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(  # noqa: S310 - the container-local endpoint is operator configured
        f"{base_url}{path}",
        data=raw,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310
            return json.loads(response.read())
    except HTTPError as exc:
        raise RuntimeError(f"sandbox control request rejected with HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("sandbox control endpoint unavailable") from exc


def run(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    command: str = args.command
    if command in {"status", "verify"}:
        result = _request("GET", "/sandbox/v1/state", None)
    elif command == "reset":
        result = _request("POST", "/sandbox/v1/reset", {})
    elif command == "fault":
        result = _request(
            "PUT",
            f"/sandbox/v1/faults/{args.provider}",
            {"mode": args.mode, "remaining": args.remaining},
        )
    elif command == "clear-fault":
        result = _request("DELETE", f"/sandbox/v1/faults/{args.provider}", None)
    else:
        raise RuntimeError(f"unsupported sandbox command: {command}")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    run()
