"""Bounded Prometheus metrics exported by non-HTTP worker processes."""

from __future__ import annotations

from datetime import UTC, datetime

from prometheus_client import CollectorRegistry, Counter, Histogram


class InferenceMetrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry(auto_describe=True)
        self.requests = Counter(
            "ioap_inference_requests_total",
            "Version-resolved model inference requests.",
            ("model_alias", "status"),
            registry=self.registry,
        )
        self.duration = Histogram(
            "ioap_inference_request_duration_seconds",
            "End-to-end model gateway duration in seconds.",
            ("model_alias",),
            registry=self.registry,
        )
        self.tokens = Counter(
            "ioap_inference_tokens_total",
            "Model tokens admitted through the production gateway.",
            ("model_alias", "direction"),
            registry=self.registry,
        )

    def observe(
        self,
        *,
        model_alias: str,
        status: str,
        seconds: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        self.requests.labels(model_alias=model_alias, status=status).inc()
        self.duration.labels(model_alias=model_alias).observe(seconds)
        if prompt_tokens:
            self.tokens.labels(model_alias=model_alias, direction="input").inc(prompt_tokens)
        if completion_tokens:
            self.tokens.labels(model_alias=model_alias, direction="output").inc(completion_tokens)


class EventConsumerMetrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry(auto_describe=True)
        self.events = Counter(
            "ioap_core_events_total",
            "Core feedback events by controlled processing disposition.",
            ("consumer", "disposition"),
            registry=self.registry,
        )
        self.freshness = Histogram(
            "ioap_cdc_event_freshness_seconds",
            "Elapsed time from domain-event occurrence to consumer visibility.",
            ("consumer",),
            registry=self.registry,
        )

    def observe(
        self,
        *,
        consumer: str,
        disposition: str,
        occurred_at: datetime | None,
        observed_at: datetime | None = None,
    ) -> None:
        self.events.labels(consumer=consumer, disposition=disposition).inc()
        if occurred_at is not None:
            now = observed_at or datetime.now(UTC)
            self.freshness.labels(consumer=consumer).observe(
                max(0.0, (now - occurred_at.astimezone(UTC)).total_seconds())
            )


class RerankerRuntimeMetrics:
    """GPU CrossEncoder runtime evidence without high-cardinality query labels."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry(auto_describe=True)
        self.requests = Counter(
            "ioap_reranker_runtime_requests_total",
            "CrossEncoder reranking requests by immutable release and result.",
            ("release_id", "status"),
            registry=self.registry,
        )
        self.duration = Histogram(
            "ioap_reranker_runtime_latency_seconds",
            "CrossEncoder reranking latency in seconds.",
            ("release_id",),
            registry=self.registry,
        )
        self.candidates = Histogram(
            "ioap_reranker_runtime_candidate_count",
            "Authorized candidates scored by the CrossEncoder.",
            ("release_id",),
            registry=self.registry,
            buckets=(1, 2, 4, 8, 12, 20, 32, 50),
        )

    def observe(
        self,
        *,
        release_id: str,
        status: str,
        seconds: float,
        candidate_count: int,
    ) -> None:
        self.requests.labels(release_id=release_id, status=status).inc()
        self.duration.labels(release_id=release_id).observe(max(0.0, seconds))
        self.candidates.labels(release_id=release_id).observe(max(0, candidate_count))


class EmbeddingRuntimeMetrics:
    """GPU SentenceTransformer runtime evidence."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry(auto_describe=True)
        self.requests = Counter(
            "ioap_embedding_runtime_requests_total",
            "Embedding runtime requests by immutable release and result.",
            ("release_id", "status"),
            registry=self.registry,
        )
        self.duration = Histogram(
            "ioap_embedding_runtime_latency_seconds",
            "Embedding runtime latency in seconds.",
            ("release_id",),
            registry=self.registry,
        )
        self.items = Histogram(
            "ioap_embedding_runtime_item_count",
            "Texts vectorized by the production Embedding runtime.",
            ("release_id",),
            registry=self.registry,
            buckets=(1, 2, 4, 8, 16, 32, 64),
        )

    def observe(
        self,
        *,
        release_id: str,
        status: str,
        seconds: float,
        item_count: int,
    ) -> None:
        self.requests.labels(release_id=release_id, status=status).inc()
        self.duration.labels(release_id=release_id).observe(max(0.0, seconds))
        self.items.labels(release_id=release_id).observe(max(0, item_count))


class KnowledgeRerankerOnlineMetrics:
    """API-side success and explicit RRF fallback evidence."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self.requests = Counter(
            "ioap_knowledge_reranker_requests_total",
            "Knowledge reranking attempts by release and result.",
            ("release_id", "status"),
            registry=registry,
        )
        self.duration = Histogram(
            "ioap_knowledge_reranker_latency_seconds",
            "End-to-end production Reranker latency in seconds.",
            ("release_id",),
            registry=registry,
        )
        self.fallbacks = Counter(
            "ioap_knowledge_reranker_fallbacks_total",
            "Knowledge queries explicitly degraded to RRF order.",
            ("release_id", "reason"),
            registry=registry,
        )

    def observe(
        self,
        *,
        release_id: str,
        status: str,
        seconds: float,
        reason: str | None = None,
    ) -> None:
        self.requests.labels(release_id=release_id, status=status).inc()
        self.duration.labels(release_id=release_id).observe(max(0.0, seconds))
        if reason is not None:
            self.fallbacks.labels(release_id=release_id, reason=reason).inc()


class KnowledgeEmbeddingOnlineMetrics:
    """API-side index/query vectorization evidence."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self.requests = Counter(
            "ioap_knowledge_embedding_requests_total",
            "Knowledge embedding requests by release and result.",
            ("release_id", "status"),
            registry=registry,
        )
        self.duration = Histogram(
            "ioap_knowledge_embedding_latency_seconds",
            "End-to-end production Embedding latency in seconds.",
            ("release_id",),
            registry=registry,
        )
        self.items = Counter(
            "ioap_knowledge_embedding_items_total",
            "Knowledge texts vectorized by release and result.",
            ("release_id", "status"),
            registry=registry,
        )
        self.failures = Counter(
            "ioap_knowledge_embedding_failures_total",
            "Embedding failures that block rebuilds or degrade queries to sparse recall.",
            ("release_id", "reason"),
            registry=registry,
        )

    def observe(
        self,
        *,
        release_id: str,
        status: str,
        seconds: float,
        item_count: int,
        reason: str | None = None,
    ) -> None:
        self.requests.labels(release_id=release_id, status=status).inc()
        self.duration.labels(release_id=release_id).observe(max(0.0, seconds))
        self.items.labels(release_id=release_id, status=status).inc(max(0, item_count))
        if reason is not None:
            self.failures.labels(release_id=release_id, reason=reason).inc()
