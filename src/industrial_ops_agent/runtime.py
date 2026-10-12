"""Runtime dependency assembly kept outside the import-safe OpenAPI application."""

from __future__ import annotations

import asyncio
import socket
from hashlib import sha256
from urllib.request import urlopen

from fastapi import FastAPI
from minio import Minio
from sqlalchemy import text
from temporalio.contrib.opentelemetry import OpenTelemetryInterceptor

from industrial_ops_agent import __version__
from industrial_ops_agent.agent.tool_catalog import diagnosis_tool_registry
from industrial_ops_agent.api.app import create_app
from industrial_ops_agent.assurance.service import AssuranceService
from industrial_ops_agent.auth.oidc import JwksSigningKeyProvider, OidcVerifier
from industrial_ops_agent.auth.opa import OpaPolicyClient
from industrial_ops_agent.auth.policy import Authorizer
from industrial_ops_agent.cache.redis import RedisTenantCache
from industrial_ops_agent.config import Settings, get_settings
from industrial_ops_agent.data_governance.dlp import PresidioDlpProcessor
from industrial_ops_agent.data_pipeline.lineage import OpenLineageEmitter
from industrial_ops_agent.data_pipeline.service import DatasetPipelineService
from industrial_ops_agent.data_pipeline.storage import MinioDatasetStore
from industrial_ops_agent.enterprise_assets import EnterpriseProjectAdoptionService
from industrial_ops_agent.experiments.mlflow import MlflowRestTracker
from industrial_ops_agent.external_search.provider import TavilyExternalSearchProvider
from industrial_ops_agent.gpu_operations import GpuOperationsService
from industrial_ops_agent.labeling.label_studio import LazyLabelStudioAdapter
from industrial_ops_agent.maintenance_planning import (
    GovernedMaintenancePlanningBindingResolver,
    MaintenancePlanningActivationService,
    ProductionMaintenancePlanningBindingResolver,
)
from industrial_ops_agent.maintenance_planning.temporal import (
    LazyTemporalMaintenancePlanningDispatcher,
)
from industrial_ops_agent.model_gateway.service import EnvironmentAwareModelResolver
from industrial_ops_agent.multimodal.realtime_transcripts import RealtimeTranscriptService
from industrial_ops_agent.multimodal.transcription import (
    OpenAiCompatibleTranscriptionTransport,
    TranscriptionGateway,
)
from industrial_ops_agent.object_store.minio import MinioTenantObjectStore
from industrial_ops_agent.observability import HttpMetrics
from industrial_ops_agent.operations import OperationsService, PrometheusHttpReader
from industrial_ops_agent.orchestration.workflows import (
    LazyTemporalClient,
    LazyTemporalDiagnosisDispatcher,
    LazyTemporalKnowledgeDeletionDispatcher,
    LazyTemporalKnowledgeIndexEvaluationDispatcher,
    LazyTemporalKnowledgeIngestionDispatcher,
    LazyTemporalKnowledgeSearchRebuildDispatcher,
    LazyTemporalRecognitionDispatcher,
)
from industrial_ops_agent.persistence.database import Database
from industrial_ops_agent.recovery.service import RecoveryService
from industrial_ops_agent.runtime_metrics import (
    KnowledgeEmbeddingOnlineMetrics,
    KnowledgeRerankerOnlineMetrics,
)
from industrial_ops_agent.search_profiles.embedding import (
    HttpKnowledgeEmbedder,
    ProductionEmbeddingResolver,
)
from industrial_ops_agent.search_profiles.reranker import (
    HttpKnowledgeReranker,
    ProductionRerankerResolver,
)
from industrial_ops_agent.search_profiles.store import OpenSearchStore
from industrial_ops_agent.secrets import SecretName, build_secret_provider
from industrial_ops_agent.security.emergency_access import DatabaseEmergencyGrantPolicy
from industrial_ops_agent.security_audit import build_persistent_security_auditor
from industrial_ops_agent.telemetry import configure_telemetry
from industrial_ops_agent.tools.diagnosis_composition import build_diagnosis_tool_gateway
from industrial_ops_agent.tools.factory import build_enterprise_adapters


def create_runtime_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    enterprise_project_adoption_service = (
        EnterpriseProjectAdoptionService(
            resolved.enterprise_project_repo_root,
            acceptance_path=resolved.enterprise_project_adoption_path,
            cache_seconds=resolved.enterprise_project_adoption_cache_seconds,
        )
        if resolved.enterprise_project_adoption_enabled
        else None
    )
    telemetry = configure_telemetry(resolved)
    provider = build_secret_provider(resolved)
    database_url = provider.get(SecretName.DATABASE_URL)
    minio_access_key = provider.get(SecretName.MINIO_ACCESS_KEY)
    minio_secret_key = provider.get(SecretName.MINIO_SECRET_KEY)
    audit_hash_key = provider.get(SecretName.OIDC_CLIENT_SECRET)
    database = Database(database_url.reveal())
    cache = RedisTenantCache.from_url(resolved.redis_url)
    minio_client = Minio(
        resolved.minio_endpoint,
        access_key=minio_access_key.reveal(),
        secret_key=minio_secret_key.reveal(),
        secure=resolved.minio_secure,
    )
    object_store = MinioTenantObjectStore(minio_client, resolved.minio_bucket)
    dataset_store = MinioDatasetStore(minio_client, resolved.dataset_bucket)
    audit_key = sha256(b"industrial-ops-audit-v1\0" + audit_hash_key.reveal().encode()).digest()
    auditor = build_persistent_security_auditor(database, hash_key=audit_key)
    authorizer = Authorizer(
        auditor,
        OpaPolicyClient(
            resolved.opa_decision_url,
            timeout_seconds=resolved.opa_timeout_seconds,
        ),
        DatabaseEmergencyGrantPolicy(database),
    )
    tool_registry = diagnosis_tool_registry(
        enterprise_tools_enabled=resolved.enterprise_tools_enabled
    )
    enterprise_adapters = build_enterprise_adapters(resolved, provider, tool_registry)
    tool_gateway = build_diagnosis_tool_gateway(
        database,
        authorizer,
        readonly=enterprise_adapters.readonly,
        enterprise_tools_enabled=resolved.enterprise_tools_enabled,
    )
    verifier = OidcVerifier(
        issuer=resolved.oidc_issuer,
        audience=resolved.oidc_audience,
        signing_keys=JwksSigningKeyProvider(resolved.oidc_jwks_url),
    )
    temporal = LazyTemporalClient(
        resolved.temporal_address,
        interceptors=(OpenTelemetryInterceptor(add_temporal_spans=True),)
        if resolved.otel_enabled
        else (),
    )
    recognition_dispatcher = LazyTemporalRecognitionDispatcher(
        temporal,
        resolved.temporal_task_queue,
    )
    knowledge_ingestion_dispatcher = LazyTemporalKnowledgeIngestionDispatcher(
        temporal,
        resolved.temporal_task_queue,
    )
    knowledge_deletion_dispatcher = LazyTemporalKnowledgeDeletionDispatcher(
        temporal,
        resolved.temporal_task_queue,
    )
    knowledge_index_evaluation_dispatcher = LazyTemporalKnowledgeIndexEvaluationDispatcher(
        temporal,
        resolved.temporal_task_queue,
    )
    knowledge_search_rebuild_dispatcher = LazyTemporalKnowledgeSearchRebuildDispatcher(
        temporal,
        resolved.temporal_task_queue,
    )
    maintenance_planning_dispatcher = LazyTemporalMaintenancePlanningDispatcher(
        temporal,
        resolved.temporal_task_queue,
    )
    diagnosis_dispatcher = LazyTemporalDiagnosisDispatcher(
        temporal,
        resolved.temporal_task_queue,
    )
    dlp_processor = PresidioDlpProcessor()
    label_studio_adapter = LazyLabelStudioAdapter(
        base_url=resolved.label_studio_url,
        secret_provider=provider,
        project_key=resolved.label_studio_project_key,
        project_id=resolved.label_studio_project_id,
        timeout_seconds=resolved.label_studio_timeout_seconds,
    )
    dataset_pipeline = DatasetPipelineService(
        database,
        dataset_store,
        OpenLineageEmitter(
            url=resolved.openlineage_url,
            namespace=resolved.openlineage_namespace,
        ),
        code_version=__version__,
        media_store=MinioDatasetStore(minio_client, resolved.minio_bucket),
    )
    experiment_tracker = MlflowRestTracker(
        resolved.mlflow_tracking_url,
        timeout_seconds=resolved.mlflow_timeout_seconds,
    )
    model_resolver = EnvironmentAwareModelResolver(
        database, resolved.model_gateway_required_environment
    )
    maintenance_planning_base_resolver = (
        ProductionMaintenancePlanningBindingResolver(
            database,
            model_resolver,
            model_alias=resolved.maintenance_planning_model_alias,
        )
        if model_resolver is not None and resolved.multi_agent_planning_enabled
        else None
    )
    maintenance_planning_binding_resolver = (
        GovernedMaintenancePlanningBindingResolver(
            maintenance_planning_base_resolver,
            MaintenancePlanningActivationService(database),
            target_environment=(
                "PRODUCTION" if resolved.environment.value == "production" else "PROJECT_STAGING"
            ),
        )
        if maintenance_planning_base_resolver is not None
        else None
    )
    realtime_transcript_service = None
    if model_resolver is not None:
        model_gateway_key = (
            provider.get(SecretName.MODEL_GATEWAY_API_KEY)
            if resolved.model_gateway_auth_mode.value == "bearer"
            else None
        )
        realtime_transcript_service = RealtimeTranscriptService(
            database,
            authorizer,
            TranscriptionGateway(
                database,
                model_resolver,
                OpenAiCompatibleTranscriptionTransport(
                    model_gateway_key.reveal() if model_gateway_key is not None else None,
                    auth_mode=resolved.model_gateway_auth_mode.value,
                    allow_plain_http=resolved.environment.value in {"local", "test"},
                ),
            ),
            model_alias=resolved.realtime_asr_model_alias,
            timeout_seconds=resolved.realtime_asr_timeout_seconds,
            hotwords=(),
        )
    prometheus_reader = PrometheusHttpReader(
        resolved.prometheus_url,
        timeout_seconds=resolved.prometheus_timeout_seconds,
        ca_file=resolved.prometheus_ca_file,
        token_file=resolved.prometheus_token_file,
    )
    recovery_service = RecoveryService(
        database,
        authorizer,
        enforce_release_gate=resolved.environment.value == "production",
    )
    operations_service = OperationsService(
        prometheus_reader,
        recovery_gate=recovery_service,
        recovery_tenant_id=resolved.deployment_controller_tenant_id,
    )
    gpu_operations_service = GpuOperationsService(database, prometheus_reader)
    assurance_service = AssuranceService(database, authorizer, operations_service)
    http_metrics = HttpMetrics()
    knowledge_search_store = None
    if resolved.knowledge_search_profiles_enabled:
        opensearch_password = (
            provider.get(SecretName.OPENSEARCH_PASSWORD).reveal()
            if resolved.opensearch_username is not None
            else None
        )
        knowledge_search_store = OpenSearchStore(
            url=resolved.opensearch_url,
            index_prefix=resolved.opensearch_index_prefix,
            username=resolved.opensearch_username,
            password=opensearch_password,
            ca_certs=resolved.opensearch_ca_file,
            timeout_seconds=resolved.opensearch_timeout_seconds,
        )
    knowledge_reranker = None
    knowledge_embedder = None
    external_search_provider = None
    if knowledge_search_store is not None and model_resolver is not None:
        model_gateway_key = provider.get(SecretName.MODEL_GATEWAY_API_KEY)
        knowledge_reranker = HttpKnowledgeReranker(
            ProductionRerankerResolver(database),
            api_key=model_gateway_key.reveal(),
            timeout_seconds=resolved.reranker_inference_timeout_seconds,
            allow_plain_http=resolved.environment.value in {"local", "test"},
            metrics=KnowledgeRerankerOnlineMetrics(http_metrics.registry),
        )
        knowledge_embedder = HttpKnowledgeEmbedder(
            ProductionEmbeddingResolver(database),
            api_key=model_gateway_key.reveal(),
            timeout_seconds=resolved.embedding_inference_timeout_seconds,
            allow_plain_http=resolved.environment.value in {"local", "test"},
            metrics=KnowledgeEmbeddingOnlineMetrics(http_metrics.registry),
        )
    if resolved.external_search_enabled:
        external_search_provider = TavilyExternalSearchProvider(
            endpoint=resolved.tavily_search_url,
            api_key=provider.get(SecretName.TAVILY_API_KEY),
            timeout_seconds=resolved.tavily_timeout_seconds,
            project_id=resolved.tavily_project_id,
        )

    async def database_ready() -> bool:
        def probe() -> bool:
            with database.engine.connect() as connection:
                return bool(connection.scalar(text("SELECT 1")) == 1)

        return await asyncio.to_thread(probe)

    async def object_store_ready() -> bool:
        return await asyncio.to_thread(minio_client.bucket_exists, resolved.minio_bucket)

    async def oidc_ready() -> bool:
        def probe() -> bool:
            with urlopen(resolved.oidc_jwks_url, timeout=2.0) as response:  # noqa: S310
                return bool(response.status == 200)

        return await asyncio.to_thread(probe)

    async def temporal_ready() -> bool:
        host, port = resolved.temporal_address.rsplit(":", maxsplit=1)

        def probe() -> bool:
            with socket.create_connection((host, int(port)), timeout=2.0):
                return True

        return await asyncio.to_thread(probe)

    async def search_ready() -> bool:
        return knowledge_search_store is not None and await asyncio.to_thread(
            knowledge_search_store.ping
        )

    readiness_checks = {
        "database": database_ready,
        "object_store": object_store_ready,
        "oidc": oidc_ready,
        "redis": cache.ping,
        "temporal": temporal_ready,
    }
    if knowledge_search_store is not None:
        readiness_checks["opensearch"] = search_ready

    app = create_app(
        resolved,
        readiness_checks=readiness_checks,
        oidc_verifier=verifier,
        security_auditor=auditor,
        database=database,
        authorizer=authorizer,
        object_store=object_store,
        tool_gateway=tool_gateway,
        recognition_dispatcher=recognition_dispatcher,
        knowledge_ingestion_dispatcher=knowledge_ingestion_dispatcher,
        knowledge_deletion_dispatcher=knowledge_deletion_dispatcher,
        knowledge_index_evaluation_dispatcher=knowledge_index_evaluation_dispatcher,
        knowledge_search_rebuild_dispatcher=knowledge_search_rebuild_dispatcher,
        maintenance_planning_dispatcher=maintenance_planning_dispatcher,
        maintenance_planning_binding_resolver=maintenance_planning_binding_resolver,
        diagnosis_dispatcher=diagnosis_dispatcher,
        dlp_processor=dlp_processor,
        label_studio_adapter=label_studio_adapter,
        dataset_pipeline=dataset_pipeline,
        dataset_store=dataset_store,
        experiment_tracker=experiment_tracker,
        model_resolver=model_resolver,
        realtime_transcript_service=realtime_transcript_service,
        operations_service=operations_service,
        gpu_operations_service=gpu_operations_service,
        recovery_service=recovery_service,
        assurance_service=assurance_service,
        enterprise_project_adoption_service=enterprise_project_adoption_service,
        knowledge_search_store=knowledge_search_store,
        knowledge_reranker=knowledge_reranker,
        knowledge_embedder=knowledge_embedder,
        external_search_provider=external_search_provider,
        http_metrics=http_metrics,
    )
    app.state.secret_provider = provider
    app.state.tenant_cache = cache

    async def close_runtime_dependencies() -> None:
        await cache.close()
        if knowledge_reranker is not None:
            knowledge_reranker.close()
        if knowledge_embedder is not None:
            knowledge_embedder.close()
        prometheus_reader.close()
        if knowledge_search_store is not None:
            knowledge_search_store.close()
        database.dispose()
        telemetry.shutdown()

    app.router.add_event_handler("shutdown", close_runtime_dependencies)
    return app
