import time
from typing import Tuple

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import REGISTRY, Counter, Gauge, Histogram
from prometheus_client.openmetrics.exposition import (CONTENT_TYPE_LATEST, generate_latest)
from starlette.middleware.base import (BaseHTTPMiddleware, RequestResponseEndpoint)
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR
from starlette.types import ASGIApp

# ... (Métricas se mantienen igual) ...
INFO = Gauge("fastapi_app_info", "FastAPI application information.", ["app_name"])
REQUESTS = Counter("fastapi_requests_total", "Total requests.", ["method", "path", "app_name"])
RESPONSES = Counter("fastapi_responses_total", "Total responses.", ["method", "path", "status_code", "app_name"])
REQUESTS_PROCESSING_TIME = Histogram("fastapi_requests_duration_seconds", "Processing time.", ["method", "path", "app_name"])
EXCEPTIONS = Counter("fastapi_exceptions_total", "Total exceptions.", ["method", "path", "exception_type", "app_name"])
REQUESTS_IN_PROGRESS = Gauge("fastapi_requests_in_progress", "Requests in progress.", ["method", "path", "app_name"])

class PrometheusMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, app_name: str = "fastapi-app") -> None:
        super().__init__(app)
        self.app_name = app_name
        INFO.labels(app_name=self.app_name).inc()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method
        path, is_handled_path = self.get_path(request)

        if not is_handled_path:
            return await call_next(request)

        REQUESTS_IN_PROGRESS.labels(method=method, path=path, app_name=self.app_name).inc()
        REQUESTS.labels(method=method, path=path, app_name=self.app_name).inc()
        before_time = time.perf_counter()
        
        status_code = HTTP_500_INTERNAL_SERVER_ERROR
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            EXCEPTIONS.labels(method=method, path=path, exception_type=type(e).__name__, app_name=self.app_name).inc()
            raise e from None
        finally:
            after_time = time.perf_counter()
            duration = after_time - before_time
            
            # FIX: Garantizar que capturamos el trace_id incluso en el bloque finally
            span = trace.get_current_span()
            span_context = span.get_span_context()
            trace_id = trace.format_trace_id(span_context.trace_id) if span_context.is_valid else ""

            # Observación con Exemplar para correlación métrica -> traza
            REQUESTS_PROCESSING_TIME.labels(method=method, path=path, app_name=self.app_name).observe(
                duration, exemplar={'TraceID': trace_id}
            )
            
            RESPONSES.labels(method=method, path=path, status_code=status_code, app_name=self.app_name).inc()
            REQUESTS_IN_PROGRESS.labels(method=method, path=path, app_name=self.app_name).dec()

    @staticmethod
    def get_path(request: Request) -> Tuple[str, bool]:
        for route in request.app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                return route.path, True
        return request.url.path, False

def metrics(request: Request) -> Response:
    return Response(generate_latest(REGISTRY), headers={"Content-Type": CONTENT_TYPE_LATEST})

def setting_otlp(app: ASGIApp, app_name: str, endpoint: str, log_correlation: bool = True) -> None:
    resource = Resource.create(attributes={"service.name": app_name})
    tracer = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer)
    
    # insecure=True para Tempo local
    tracer.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))

    if log_correlation:
        LoggingInstrumentor().instrument(set_logging_format=True)

    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer)

