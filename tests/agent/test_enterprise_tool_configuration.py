from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from unittest import TestCase

from sqlalchemy import create_engine

from industrial_ops_agent.agent.contracts import DIAGNOSIS_AGENT_PROMPT_ID, validate_step
from industrial_ops_agent.agent.diagnosis_runtime import DiagnosisRuntime, build_step_request
from industrial_ops_agent.agent.tool_catalog import diagnosis_tool_registry
from industrial_ops_agent.application.diagnoses import DiagnosisWorkflowInput
from industrial_ops_agent.auth.policy import Authorizer
from industrial_ops_agent.config import EnterpriseToolsMode, Environment, Settings
from industrial_ops_agent.memory_governance.service import MemoryContextReader
from industrial_ops_agent.model_gateway.openai import OpenAiCompatibleTransport
from industrial_ops_agent.model_gateway.service import EnvironmentAwareModelResolver, ModelGateway
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.prompting.registry import default_prompt_registry
from industrial_ops_agent.secrets import EnvironmentSecretProvider, SecretName, SecretReadError
from industrial_ops_agent.security_audit import build_persistent_security_auditor
from industrial_ops_agent.tools.diagnosis_composition import (
    build_diagnosis_readonly_adapter,
    build_diagnosis_tool_gateway,
)
from industrial_ops_agent.tools.enterprise_http import EnterpriseHttpAdapter
from industrial_ops_agent.tools.factory import build_enterprise_adapters


class EnterpriseToolConfigurationTests(TestCase):
    def setUp(self) -> None:
        self.database = Database.from_engine(create_engine("sqlite+pysqlite:///:memory:"))
        self.auditor = build_persistent_security_auditor(
            self.database, hash_key=b"configuration-test"
        )
        self.authorizer = Authorizer(self.auditor)
        self.tool_ids = {
            "asset.get", "warranty.get", "parts.availability",
            "schedule.availability", "work_orders.history",
        }

    def tearDown(self) -> None:
        self.database.dispose()

    def settings(self, *, enabled: bool, url: str = "") -> Settings:
        return Settings(
            environment=Environment.TEST,
            enterprise_tools_enabled=enabled,
            enterprise_tools_mode=EnterpriseToolsMode.HTTP,
            enterprise_tool_gateway_url=url,
        )

    def test_disabled_api_and_worker_composition_require_no_secret_or_url(self) -> None:
        settings = self.settings(enabled=False)
        provider = EnvironmentSecretProvider({})
        registry = diagnosis_tool_registry(
            enterprise_tools_enabled=settings.enterprise_tools_enabled
        )
        api = build_enterprise_adapters(settings, provider, registry)
        worker = build_diagnosis_readonly_adapter(settings, provider)
        self.assertIsNone(api.readonly)
        self.assertIsNone(worker)
        for readonly in (api.readonly, worker):
            gateway = build_diagnosis_tool_gateway(
                self.database, self.authorizer, readonly=readonly,
                enterprise_tools_enabled=settings.enterprise_tools_enabled,
            )
            self.assertEqual(gateway.definitions(), ())
            self.assertEqual(gateway.transport_bindings(), ())
            self.assertEqual(gateway.mcp_server_versions(), {})

    def test_enabled_api_and_worker_use_real_http_adapter_and_full_catalog(self) -> None:
        settings = self.settings(enabled=True, url="https://enterprise.example.com")
        provider = EnvironmentSecretProvider(
            {"IOAP_ENTERPRISE_TOOL_GATEWAY_TOKEN": "constructor-test-token"}
        )
        registry = diagnosis_tool_registry(
            enterprise_tools_enabled=settings.enterprise_tools_enabled
        )
        api = build_enterprise_adapters(settings, provider, registry)
        worker = build_diagnosis_readonly_adapter(settings, provider)
        for readonly in (api.readonly, worker):
            self.assertIsInstance(readonly, EnterpriseHttpAdapter)
            assert isinstance(readonly, EnterpriseHttpAdapter)
            self.assertEqual(readonly._base_url, "https://enterprise.example.com")
            self.assertEqual(
                readonly._api_token, provider.get(SecretName.ENTERPRISE_TOOL_GATEWAY_TOKEN)
            )
            gateway = build_diagnosis_tool_gateway(
                self.database, self.authorizer, readonly=readonly,
                enterprise_tools_enabled=settings.enterprise_tools_enabled,
            )
            self.assertEqual({item.tool_id for item in gateway.definitions()}, self.tool_ids)
            self.assertEqual(len(gateway.transport_bindings()), 5)

    def test_enabled_missing_url_fails_before_reading_token(self) -> None:
        settings = self.settings(enabled=True)
        provider = EnvironmentSecretProvider({})
        with self.assertRaisesRegex(ValueError, "gateway URL"):
            build_enterprise_adapters(settings, provider, diagnosis_tool_registry())
        with self.assertRaisesRegex(ValueError, "gateway URL"):
            build_diagnosis_readonly_adapter(settings, provider)

    def test_enabled_missing_token_fails_in_both_compositions(self) -> None:
        settings = self.settings(enabled=True, url="https://enterprise.example.com")
        provider = EnvironmentSecretProvider({})
        with self.assertRaises(SecretReadError) as api_error:
            build_enterprise_adapters(settings, provider, diagnosis_tool_registry())
        with self.assertRaises(SecretReadError) as worker_error:
            build_diagnosis_readonly_adapter(settings, provider)
        self.assertEqual(api_error.exception.name, SecretName.ENTERPRISE_TOOL_GATEWAY_TOKEN)
        self.assertEqual(worker_error.exception.name, SecretName.ENTERPRISE_TOOL_GATEWAY_TOKEN)

    def test_disabled_staging_does_not_validate_enterprise_endpoint(self) -> None:
        settings = Settings(environment=Environment.STAGING, enterprise_tools_enabled=False,
                            enterprise_tools_mode=EnterpriseToolsMode.HTTP,
                            enterprise_tool_gateway_url="")
        self.assertFalse(settings.use_http_enterprise_tools)

    def test_enablement_uses_existing_ioap_environment_mapping(self) -> None:
        variable = "IOAP_ENTERPRISE_TOOLS_ENABLED"
        previous = os.environ.get(variable)
        try:
            os.environ[variable] = "false"
            disabled = Settings(_env_file=None)
            self.assertFalse(disabled.enterprise_tools_enabled)
            self.assertIsNone(
                build_diagnosis_readonly_adapter(disabled, EnvironmentSecretProvider({}))
            )
            os.environ[variable] = "true"
            enabled = Settings(
                _env_file=None, environment=Environment.TEST,
                enterprise_tool_gateway_url="https://enterprise.example.com",
            )
            self.assertTrue(enabled.enterprise_tools_enabled)
            with self.assertRaises(SecretReadError):
                build_diagnosis_readonly_adapter(enabled, EnvironmentSecretProvider({}))
        finally:
            if previous is None:
                del os.environ[variable]
            else:
                os.environ[variable] = previous

    def test_enabled_auto_uses_real_http_in_local_environment(self) -> None:
        settings = Settings(environment=Environment.LOCAL, enterprise_tools_enabled=True,
                            enterprise_tool_gateway_url="https://enterprise.example.com")
        provider = EnvironmentSecretProvider(
            {"IOAP_ENTERPRISE_TOOL_GATEWAY_TOKEN": "constructor-test-token"}
        )
        self.assertIsInstance(
            build_diagnosis_readonly_adapter(settings, provider), EnterpriseHttpAdapter
        )

    def test_enabled_synthetic_mode_is_rejected(self) -> None:
        settings = Settings(environment=Environment.TEST, enterprise_tools_enabled=True,
                            enterprise_tools_mode=EnterpriseToolsMode.SYNTHETIC,
                            enterprise_tool_gateway_url="https://enterprise.example.com")
        with self.assertRaisesRegex(ValueError, "Synthetic"):
            build_diagnosis_readonly_adapter(settings, EnvironmentSecretProvider({}))

    def test_disabled_model_request_excludes_enterprise_tools_and_allows_final(self) -> None:
        settings = self.settings(enabled=False)
        gateway = build_diagnosis_tool_gateway(
            self.database, self.authorizer,
            readonly=build_diagnosis_readonly_adapter(settings, EnvironmentSecretProvider({})),
            enterprise_tools_enabled=False,
        )
        now = datetime.now(UTC)
        command = DiagnosisWorkflowInput(
            tenant_id="configuration-tenant", subject_id="configuration-subject",
            roles=("after_sales_engineer",), asset_ids=("configuration-asset",), site_ids=(),
            incident_id="configuration-incident", diagnosis_run_id="configuration-diagnosis",
            agent_run_id="configuration-agent", workflow_id="configuration-workflow",
            request_id="configuration-request", oidc_subject="configuration-subject",
            issued_at=now.isoformat(), expires_at=(now + timedelta(minutes=5)).isoformat(),
        )
        prompt = default_prompt_registry().get(DIAGNOSIS_AGENT_PROMPT_ID)
        state = {
            "tool_calls": 0, "tool_facts": [], "tool_failures": [],
            "budget": {"max_tool_calls": 5, "max_tokens": 20000, "max_steps": 5},
            "manifest": {"tool_versions": {item: "1.0.0" for item in self.tool_ids},
                         "prompt_bundle": prompt.prompt_bundle_id,
                         "prompt_bundle_hash": prompt.content_hash,
                         "model_release": "configuration-release",
                         "index_release_id": "configuration-index"},
            "tokens_used": 0, "unknown_token_reservations": 0, "evidence": [],
            "memories": [], "memory_truncations": [], "query_text": "检查设备告警",
            "model_steps": 0, "node_index": 1, "attempt": 1, "trace_id": "configuration-trace",
            "deadline": (now + timedelta(minutes=1)).isoformat(),
            "diagnosis_run_id": command.diagnosis_run_id,
        }
        runtime = DiagnosisRuntime(
            self.database, command, {"manifest": state["manifest"]}, model_gateway=ModelGateway(
                self.database, EnvironmentAwareModelResolver(self.database, "STAGING"),
                OpenAiCompatibleTransport("constructor-test-key"), security_auditor=self.auditor,
            ), tool_gateway=gateway, model_alias=settings.model_gateway_alias,
            timeout_seconds=1, memory_reader=MemoryContextReader(self.database),
        )
        available = runtime._available_tools(state)
        self.assertEqual(available, [])
        request = build_step_request(command, state, model_alias=settings.model_gateway_alias,
                                     timeout_seconds=1, tools=available)
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(json.loads(request.messages[-1]["content"])["available_tools"], {})
        for tool_id in self.tool_ids:
            self.assertNotIn(tool_id, json.dumps(request.response_schema))
        decision = {
            "action": "FINAL", "query": None, "tool_id": None,
            "report": {"status": "COMPLETED", "conclusion": "复核告警来源。",
                       "citation_ids": ["citation-configuration"], "contradictions": [],
                       "missing_information": [], "next_checks": ["检查传感器连接。"],
                       "confidence": 0.7},
        }
        validate_step(decision, ["citation-configuration"], [])
