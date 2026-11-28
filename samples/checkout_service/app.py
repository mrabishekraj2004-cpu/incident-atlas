"""Small, instrumented service that emits OTLP traces, metrics, and logs."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", os.getenv("PILOT_SERVICE_NAME", "checkout-service"))
API_BASE = os.getenv("PILOT_API_BASE_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
INGEST_TOKEN = os.getenv("PILOT_INGEST_TOKEN", "")
INCIDENT_ID = os.getenv("PILOT_INCIDENT_ID", "")
EXPORT_HEADERS = {
    "Authorization": f"Bearer {INGEST_TOKEN}",
    "X-Atlas-Incident-Id": INCIDENT_ID,
}

if not INGEST_TOKEN or not INCIDENT_ID:
    raise RuntimeError("Set PILOT_INGEST_TOKEN and PILOT_INCIDENT_ID from a private .env.pilot file")

resource = Resource.create({
    "service.name": SERVICE_NAME,
    "service.namespace": "incident-atlas-pilot",
    "deployment.environment.name": "controlled-exercise",
})
tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
    endpoint=f"{API_BASE}/pilot/ingest/otel/v1/traces", headers=EXPORT_HEADERS
)))
trace.set_tracer_provider(tracer_provider)

metric_exporter = OTLPMetricExporter(
    endpoint=f"{API_BASE}/pilot/ingest/otel/v1/metrics", headers=EXPORT_HEADERS
)
metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=1000)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)

logger_provider = LoggerProvider(resource=resource)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(
    endpoint=f"{API_BASE}/pilot/ingest/otel/v1/logs", headers=EXPORT_HEADERS
)))
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(LoggingHandler(level=logging.INFO, logger_provider=logger_provider))
logging.getLogger("opentelemetry").setLevel(logging.WARNING)
app_logger = logging.getLogger("checkout.exercise")
tracer = trace.get_tracer("incident-atlas.checkout.exercise")
meter = metrics.get_meter("incident-atlas.checkout.exercise")
request_duration = meter.create_histogram(
    f"{SERVICE_NAME}.request.duration",
    unit="ms",
    description="Synthetic checkout request duration for a controlled exercise.",
)
state = {"regression_active": False, "deployment_version": "baseline"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    tracer_provider.shutdown()
    meter_provider.shutdown()
    logger_provider.shutdown()


app = FastAPI(title="Incident Atlas checkout exercise service", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider, meter_provider=meter_provider)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ready", "service": SERVICE_NAME}


@app.get("/checkout")
@app.get("/catalog")
async def checkout(request: Request) -> dict[str, object]:
    began = time.perf_counter()
    version = state["deployment_version"]
    delay_ms = 220 if state["regression_active"] else 28
    await asyncio.sleep(delay_ms / 1000)
    duration_ms = (time.perf_counter() - began) * 1000
    route = request.url.path
    attributes = {"http.route": route, "deployment.version": version, "scenario.synthetic": True}
    request_duration.record(duration_ms, attributes)
    span = trace.get_current_span()
    span.set_attribute("deployment.version", version)
    span.set_attribute("scenario.synthetic", True)
    span.set_attribute("checkout.delay_ms", delay_ms)
    app_logger.info(
        "Synthetic checkout request completed",
        extra={"deployment_version": version, "latency_ms": round(duration_ms, 3), "route": route, "scenario_synthetic": True},
    )
    return {"service": SERVICE_NAME, "route": route, "deployment_version": version, "latency_ms": round(duration_ms, 3), "synthetic": True}


@app.post("/__exercise/activate-regression")
def activate_regression() -> dict[str, object]:
    state["regression_active"] = True
    state["deployment_version"] = "exercise-regression"
    return {"regression_active": True, "deployment_version": state["deployment_version"], "synthetic": True}


@app.post("/__exercise/reset")
def reset_regression() -> dict[str, object]:
    state["regression_active"] = False
    state["deployment_version"] = "baseline"
    return {"regression_active": False, "deployment_version": "baseline", "synthetic": True}


@app.post("/__exercise/flush")
def flush_exports() -> dict[str, object]:
    result = {
        "traces_flushed": tracer_provider.force_flush(timeout_millis=5000),
        "metrics_flushed": meter_provider.force_flush(timeout_millis=5000),
        "logs_flushed": logger_provider.force_flush(timeout_millis=5000),
    }
    if not all(result.values()):
        raise HTTPException(status_code=503, detail="One or more OTLP exporters did not flush.")
    return result
