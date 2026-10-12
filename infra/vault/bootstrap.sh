#!/bin/sh
set -eu
umask 077

: "${VAULT_ADDR:?VAULT_ADDR is required}"
: "${VAULT_TOKEN:?VAULT_TOKEN is required}"
: "${IOAP_DATABASE_URL:?IOAP_DATABASE_URL is required}"
: "${IOAP_OIDC_CLIENT_SECRET:?IOAP_OIDC_CLIENT_SECRET is required}"
: "${IOAP_MINIO_ACCESS_KEY:?IOAP_MINIO_ACCESS_KEY is required}"
: "${IOAP_MINIO_SECRET_KEY:?IOAP_MINIO_SECRET_KEY is required}"
: "${IOAP_NEXTAUTH_SECRET:?IOAP_NEXTAUTH_SECRET is required}"
if [ "${IOAP_ENTERPRISE_TOOLS_ENABLED:-false}" = "true" ]; then
  : "${IOAP_ENTERPRISE_TOOL_GATEWAY_TOKEN:?enterprise tool gateway token is required}"
fi

until vault status >/dev/null 2>&1; do
  sleep 1
done

if ! vault secrets list -format=json | grep -q '"secret/"'; then
  vault secrets enable -path=secret kv-v2 >/dev/null
fi

label_studio_api_token=${IOAP_LABEL_STUDIO_API_TOKEN:-}
model_gateway_api_key=${IOAP_MODEL_GATEWAY_API_KEY:-}
enterprise_tool_gateway_token=${IOAP_ENTERPRISE_TOOL_GATEWAY_TOKEN:-}
enterprise_mcp_client_secret=${IOAP_ENTERPRISE_MCP_CLIENT_SECRET:-}
opensearch_password=${IOAP_OPENSEARCH_PASSWORD:-}
secret_json=/vault/runtime/m1-runtime-secrets.json
token_file=/vault/runtime/vault-token
nextauth_file=/vault/runtime/nextauth-secret
token_tmp="${token_file}.tmp.$$"
nextauth_tmp="${nextauth_file}.tmp.$$"
trap 'rm -f "$secret_json" "$token_tmp" "$nextauth_tmp"' EXIT HUP INT TERM
printf '%s\\n' "{\\"database_url\\":\\"$IOAP_DATABASE_URL\\",\\"oidc_client_secret\\":\\"$IOAP_OIDC_CLIENT_SECRET\\",\\"minio_access_key\\":\\"$IOAP_MINIO_ACCESS_KEY\\",\\"minio_secret_key\\":\\"$IOAP_MINIO_SECRET_KEY\\",\\"nextauth_secret\\":\\"$nextauth_secret\\",\\"label_studio_api_token\\":\\"$label_studio_api_token\\",\\"model_gateway_api_key\\":\\"$model_gateway_api_key\\",\\"enterprise_tool_gateway_token\\":\\"$enterprise_tool_gateway_token\\",\\"enterprise_mcp_client_secret\\":\\"$enterprise_mcp_client_secret\\",\\"opensearch_password\\":\\"$opensearch_password\\"}" > "$secret_json"
vault kv put -mount=secret industrial-ops/m1 "@$secret_json" >/dev/null
rm -f "$secret_json"

vault policy write m1-api /vault/config/m1-api.hcl >/dev/null
app_token=$(vault token create -field=token -policy=m1-api -period=24h)
printf '%s' "$app_token" > "$token_tmp"
printf '%s' "$IOAP_NEXTAUTH_SECRET" > "$nextauth_tmp"
chown 10001:10001 "$token_tmp" "$nextauth_tmp"
chmod 0400 "$token_tmp" "$nextauth_tmp"
mv -f "$token_tmp" "$token_file"
mv -f "$nextauth_tmp" "$nextauth_file"
trap - EXIT HUP INT TERM
echo "Vault M1 policy and runtime injection files are ready."
