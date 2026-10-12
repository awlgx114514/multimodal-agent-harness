from __future__ import annotations

import unittest

from industrial_ops_agent.config import ModelGatewayAuthMode, Settings
from industrial_ops_agent.model_gateway.openai import (
    OpenAiCompatibleTransport,
    build_authorization_headers,
)
from industrial_ops_agent.model_gateway.service import ModelTransportError


class ModelGatewayTransportAuthTests(unittest.TestCase):
    def test_none_mode_does_not_add_an_authorization_header(self) -> None:
        headers = build_authorization_headers("none", None)

        self.assertEqual(headers, {"Content-Type": "application/json"})

    def test_bearer_mode_requires_a_secret(self) -> None:
        with self.assertRaises(ModelTransportError):
            build_authorization_headers("bearer", None)

    def test_bearer_mode_adds_the_secret_header(self) -> None:
        headers = build_authorization_headers("bearer", "local-test-secret")

        self.assertEqual(
            headers,
            {
                "Authorization": "Bearer local-test-secret",
                "Content-Type": "application/json",
            },
        )

    def test_unknown_mode_fails_at_transport_construction(self) -> None:
        with self.assertRaises(ValueError):
            OpenAiCompatibleTransport(None, auth_mode="infer-from-endpoint")

    def test_gateway_auth_mode_is_explicit_configuration(self) -> None:
        settings = Settings(model_gateway_auth_mode="none")

        self.assertIs(settings.model_gateway_auth_mode, ModelGatewayAuthMode.NONE)
