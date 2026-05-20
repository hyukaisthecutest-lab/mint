from __future__ import annotations
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from prometheus_client import Counter, Histogram, REGISTRY
from app.core.config import settings

# ── OpenTelemetry ─────────────────────────────────────────────────────────────

def setup_tracing() -> trace.Tracer:
    resource = Resource({SERVICE_NAME: "mint-backend"})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.OTEL_ENDPOINT, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("mint")

tracer: trace.Tracer = trace.get_tracer("mint")  # replaced after setup_tracing()

# ── Prometheus metrics ────────────────────────────────────────────────────────

agent_requests = Counter(
    "mint_agent_requests_total",
    "Total chat requests",
    ["voice_mode"],
)
agent_blocked = Counter(
    "mint_agent_guardrail_blocked_total",
    "Requests blocked by guardrail",
)
agent_errors = Counter(
    "mint_agent_errors_total",
    "Agent errors by step",
    ["step"],
)
agent_duration = Histogram(
    "mint_agent_duration_seconds",
    "Latency per agent step",
    ["step"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30],
)
tool_calls = Counter(
    "mint_agent_tool_calls_total",
    "Tool calls by name and outcome",
    ["tool", "success"],
)
token_usage = Counter(
    "mint_agent_tokens_total",
    "LLM tokens consumed",
    ["type"],
)
