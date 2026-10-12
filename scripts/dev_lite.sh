#!/usr/bin/env bash
set -euo pipefail

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
cd "$root"

runtime=${M1_CONTAINER_CLI:-docker}
runtime_env=${M1_RUNTIME_ENV_FILE:-.env.m1.local}
compose_file=compose.lite.yaml

fail() {
  echo "M1 Lite: $*" >&2
  exit 3
}

validate_runtime_env_path() {
  [[ "$runtime_env" != /* ]] || fail "runtime environment path must stay inside the repository"
  case "/$runtime_env/" in
    */../*) fail "runtime environment path must stay inside the repository" ;;
  esac
}

require_runtime() {
  command -v "$runtime" >/dev/null 2>&1 || fail "container runtime '$runtime' is required"
  "$runtime" compose version >/dev/null 2>&1 || fail "container runtime must provide the Compose plugin"
}

generate_runtime_env() {
  validate_runtime_env_path
  if [[ -e "$runtime_env" ]]; then
    [[ -f "$runtime_env" && ! -L "$runtime_env" ]] || fail "runtime environment path is unsafe"
  fi
  umask 077
  python3 - "$runtime_env" <<'PY'
from __future__ import annotations

import secrets
import sys
from pathlib import Path
from urllib.parse import quote

target = Path(sys.argv[1])
if target.is_absolute() or ".." in target.parts:
    raise SystemExit("runtime environment path must stay inside the repository")

def value(size: int = 32) -> str:
    return secrets.token_urlsafe(size)

if target.exists():
    raw_lines = target.read_text(encoding="utf-8").splitlines()
    lines = dict(
        line.split("=", 1)
        for line in raw_lines
        if line and not line.startswith("#") and "=" in line
    )
else:
    postgres_password = value()
    lines = {
        "M1_COMPOSE_PROJECT_NAME": "industrial-ops-m1",
        "M1_WEB_PORT": "3000",
        "M1_KEYCLOAK_PORT": "8080",
        "POSTGRES_DB": "industrial_ops",
        "POSTGRES_USER": "m1_db_admin",
        "POSTGRES_PASSWORD": postgres_password,
        "MINIO_ROOT_USER": "m1_minio",
        "MINIO_ROOT_PASSWORD": value(),
        "KEYCLOAK_ADMIN": "m1_admin",
        "KEYCLOAK_ADMIN_PASSWORD": value(),
        "M1_DEMO_USER_PASSWORD": value(18),
        "VAULT_DEV_ROOT_TOKEN_ID": value(),
        "IOAP_OIDC_CLIENT_SECRET": value(),
        "IOAP_NEXTAUTH_SECRET": value(48),
        "IOAP_ENTERPRISE_MCP_CLIENT_SECRET": value(),
    }

required = ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
if any(not lines.get(key) for key in required):
    raise SystemExit("existing runtime environment lacks PostgreSQL bootstrap values")

lines.setdefault("IOAP_ENTERPRISE_TOOLS_ENABLED", "false")

for key in (
    "IOAP_ENTERPRISE_TOOL_GATEWAY_TOKEN",
    "IOAP_FSM_ASSIGNMENT_PROVIDER_API_TOKEN",
    "IOAP_FSM_ASSIGNMENT_WEBHOOK_SECRET",
    "IOAP_SANDBOX_CONTROL_TOKEN",
    "IOAP_MODEL_GATEWAY_API_KEY",
):
    lines.setdefault(key, value())

runtime_user = lines.setdefault("M1_POSTGRES_RUNTIME_USER", "m1_runtime")
runtime_password = lines.setdefault("M1_POSTGRES_RUNTIME_PASSWORD", value())
database = quote(lines["POSTGRES_DB"], safe="")
admin_user = quote(lines["POSTGRES_USER"], safe="")
admin_password = quote(lines["POSTGRES_PASSWORD"], safe="")
app_user = quote(runtime_user, safe="")
app_password = quote(runtime_password, safe="")
lines["IOAP_MIGRATION_DATABASE_URL"] = (
    f"postgresql+psycopg://{admin_user}:{admin_password}@postgres:5432/{database}"
)
lines["IOAP_DATABASE_URL"] = (
    f"postgresql+psycopg://{app_user}:{app_password}@postgres:5432/{database}"
)

target.write_text(
    "".join(f"{key}={item}\n" for key, item in lines.items()),
    encoding="utf-8",
)
target.chmod(0o600)
PY
  echo "M1 runtime environment is current: $runtime_env"
}

compose() {
  M1_RUNTIME_ENV_FILE="$runtime_env" \
    "$runtime" compose --env-file "$runtime_env" -f "$compose_file" "$@"
}

ensure_vault_runtime() {
  compose up --detach --wait vault-runtime-manager
}

sandbox_cli() {
  compose exec -T enterprise-sandbox python -m industrial_ops_agent.sandbox.cli "$@"
}

require_sandbox_runtime() {
  require_runtime
  validate_runtime_env_path
  [[ -f "$runtime_env" ]] || fail "run init first"
}


verify_postgres_rls() {
  compose run --rm --no-deps -T api python - <<'PY'
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from industrial_ops_agent.config import get_settings
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.persistence.models import TENANT_TABLE_NAMES
from industrial_ops_agent.secrets import SecretName, build_secret_provider

tenant_a = "tenant-m1-demo"
tenant_b = "tenant-m1-rls-probe"
asset_a = "asset-m1-pump"
asset_b = "asset-m1-rls-probe"
database_url = build_secret_provider(get_settings()).get(SecretName.DATABASE_URL)
database = Database(database_url.reveal())

try:
    with database.engine.begin() as connection:
        role = connection.execute(
            text(
                "SELECT current_user, rolsuper, rolbypassrls "
                "FROM pg_roles WHERE rolname = current_user"
            )
        ).one()
        assert role.rolsuper is False, "application database role is a superuser"
        assert role.rolbypassrls is False, "application database role can bypass RLS"

        table_rows = {
            row.table_name: row
            for row in connection.execute(
                text(
                    "SELECT c.relname AS table_name, "
                    "c.relrowsecurity AS rls_enabled, "
                    "c.relforcerowsecurity AS rls_forced "
                    "FROM pg_class AS c "
                    "JOIN pg_namespace AS n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = current_schema() "
                    "AND c.relkind IN ('r', 'p')"
                )
            ).mappings()
        }
        policy_rows = {
            (row.table_name, row.policy_name): row
            for row in connection.execute(
                text(
                    "SELECT tablename AS table_name, policyname AS policy_name, "
                    "qual, with_check "
                    "FROM pg_policies WHERE schemaname = current_schema()"
                )
            ).mappings()
        }
        for table_name in sorted(TENANT_TABLE_NAMES):
            table = table_rows.get(table_name)
            assert table is not None, f"tenant table is missing: {table_name}"
            assert table.rls_enabled is True, f"RLS is disabled: {table_name}"
            assert table.rls_forced is True, f"RLS is not forced: {table_name}"
            policy_name = f"{table_name}_tenant_isolation"[:63]
            policy = policy_rows.get((table_name, policy_name))
            assert policy is not None, f"tenant policy is missing: {policy_name}"
            assert "app.tenant_id" in (policy.qual or ""), (
                f"tenant policy USING clause is invalid: {policy_name}"
            )
            assert "app.tenant_id" in (policy.with_check or ""), (
                f"tenant policy WITH CHECK clause is invalid: {policy_name}"
            )

        connection.execute(text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": tenant_b})
        connection.execute(
            text(
                "INSERT INTO tenants (id, status) VALUES (:tenant, 'active') "
                "ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status"
            ),
            {"tenant": tenant_b},
        )
        connection.execute(text("DELETE FROM assets WHERE asset_id = :asset"), {"asset": asset_b})
        connection.execute(
            text(
                "INSERT INTO assets "
                "(asset_id, tenant_id, source_system, source_record_id, version) "
                "VALUES (:asset, :tenant, 'rls-probe', 'rls-probe', 1)"
            ),
            {"asset": asset_b, "tenant": tenant_b},
        )

    with database.engine.begin() as connection:
        connection.execute(text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": tenant_a})
        assert connection.scalar(
            text("SELECT count(*) FROM assets WHERE asset_id = :asset"), {"asset": asset_a}
        ) == 1, "same-tenant asset is unavailable"
        assert connection.scalar(
            text("SELECT count(*) FROM assets WHERE asset_id = :asset"), {"asset": asset_b}
        ) == 0, "cross-tenant asset is visible"
        assert connection.execute(
            text("UPDATE assets SET version = version + 1 WHERE asset_id = :asset"),
            {"asset": asset_b},
        ).rowcount == 0, "cross-tenant asset is mutable"
        savepoint = connection.begin_nested()
        try:
            connection.execute(
                text(
                    "INSERT INTO assets "
                    "(asset_id, tenant_id, source_system, source_record_id, version) "
                    "VALUES ('asset-m1-cross-tenant-write', :tenant, 'rls-probe', 'cross-write', 1)"
                ),
                {"tenant": tenant_b},
            )
        except DBAPIError:
            savepoint.rollback()
        else:
            savepoint.rollback()
            raise AssertionError("cross-tenant insert bypassed RLS")

    with database.engine.begin() as connection:
        connection.execute(text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": tenant_b})
        connection.execute(text("DELETE FROM assets WHERE asset_id = :asset"), {"asset": asset_b})
        connection.execute(text("DELETE FROM tenants WHERE id = :tenant"), {"tenant": tenant_b})
finally:
    database.dispose()

print("M1_POSTGRES_RLS_OK")
PY
}

case "${1:-}" in
  doctor)
    require_runtime
    command -v python3 >/dev/null 2>&1 || fail "python3 is required"
    command -v curl >/dev/null 2>&1 || fail "curl is required"
    echo "M1 Lite prerequisites are available."
    ;;
  init)
    generate_runtime_env
    ;;
  up)
    generate_runtime_env
    M1_CONTAINER_CLI="$runtime" M1_RUNTIME_ENV_FILE="$runtime_env" \
      "$root/scripts/real_model_business_loop.sh" up
    ;;
  verify)
    generate_runtime_env
    M1_CONTAINER_CLI="$runtime" M1_RUNTIME_ENV_FILE="$runtime_env" \
      "$root/scripts/real_model_business_loop.sh" verify
    ;;
  verify-rls)
    require_runtime
    generate_runtime_env
    ensure_vault_runtime
    compose up --build --detach --wait seed
    verify_postgres_rls
    ;;
  sandbox-status)
    require_sandbox_runtime
    sandbox_cli status
    ;;
  sandbox-reset)
    require_sandbox_runtime
    sandbox_cli reset
    ;;
  sandbox-fault)
    require_sandbox_runtime
    [[ $# -eq 4 ]] || fail "usage: sandbox-fault <provider> <mode> <remaining>"
    sandbox_cli fault "$2" "$3" "$4"
    ;;
  sandbox-clear-fault)
    require_sandbox_runtime
    [[ $# -eq 2 ]] || fail "usage: sandbox-clear-fault <provider>"
    sandbox_cli clear-fault "$2"
    ;;
  candidate-rollout)
    [[ -x .venv/bin/python ]] || fail "run uv sync before candidate-rollout"
    PYTHONPATH=src .venv/bin/python -B \
      -m industrial_ops_agent.simulation.enterprise_candidate_rollout_cli run \
      --repo-root "$root"
    ;;
  simulated-closure)
    "$0" sandbox-verify
    [[ -x .venv/bin/python ]] || fail "run uv sync before simulated-closure"
    "$0" project-assurance
    PYTHONPATH=src .venv/bin/python -B \
      -m industrial_ops_agent.simulation.vlm_enterprise_staging_cli adopt \
      --repo-root "$root"
    "$0" candidate-rollout
    PYTHONPATH=src .venv/bin/python -B \
      -m industrial_ops_agent.simulation.closure_cli \
      --repo-root "$root"
    "$0" enterprise-adoption
    ;;
  project-assurance)
    [[ -x .venv/bin/python ]] || fail "run uv sync before project-assurance"
    PYTHONPATH=src .venv/bin/python -B \
      -m industrial_ops_agent.simulation.project_assurance_lab_cli run \
      --repo-root "$root"
    ;;
  project-assurance-verify)
    [[ -x .venv/bin/python ]] || fail "run uv sync before project-assurance-verify"
    PYTHONPATH=src .venv/bin/python -B \
      -m industrial_ops_agent.simulation.project_assurance_lab_cli verify \
      --repo-root "$root"
    ;;
  enterprise-adoption)
    [[ -x .venv/bin/python ]] || fail "run uv sync before enterprise-adoption"
    PYTHONPATH=src .venv/bin/python -B \
      -m industrial_ops_agent.simulation.enterprise_project_adoption_cli adopt \
      --repo-root "$root"
    ;;
  status)
    require_runtime
    validate_runtime_env_path
    [[ -f "$runtime_env" ]] || fail "run init first"
    compose ps
    ;;
  logs)
    require_runtime
    validate_runtime_env_path
    [[ -f "$runtime_env" ]] || fail "run init first"
    compose logs --tail=200 "${@:2}"
    ;;
  down)
    validate_runtime_env_path
    [[ -f "$runtime_env" ]] || fail "run init first"
    M1_CONTAINER_CLI="$runtime" M1_RUNTIME_ENV_FILE="$runtime_env" \
      "$root/scripts/real_model_business_loop.sh" down
    ;;
  clean)
    require_runtime
    validate_runtime_env_path
    [[ -f "$runtime_env" ]] || fail "run init first"
    compose down --volumes --remove-orphans
    ;;
  *)
    echo "usage: scripts/dev_lite.sh <doctor|init|up|verify|verify-rls|sandbox-status|sandbox-reset|sandbox-fault|sandbox-clear-fault|candidate-rollout|simulated-closure|project-assurance|project-assurance-verify|enterprise-adoption|status|logs|down|clean>" >&2
    exit 2
    ;;
esac
