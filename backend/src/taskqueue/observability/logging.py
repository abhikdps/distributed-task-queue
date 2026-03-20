import logging
import os
import sys

import structlog


def _setup_otlp_log_export(service_name: str) -> None:
    """If OTEL logs endpoint is set, bridge stdlib logging to OTLP so the collector can ship to Loki."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT")
    if not endpoint:
        base = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if not base:
            return
        # Logs use HTTP, collector exposes OTLP HTTP on 4318.
        base = base.replace(":4317", ":4318").rstrip("/")
        endpoint = f"{base}/v1/logs"
    try:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": service_name})
        logger_provider = LoggerProvider(resource=resource)
        set_logger_provider(logger_provider)
        exporter = OTLPLogExporter(endpoint=endpoint)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
        # Accept all levels so INFO/WARNING/ERROR all reach Loki
        handler = LoggingHandler(level=logging.DEBUG, logger_provider=logger_provider)
        logging.getLogger().addHandler(handler)
    except Exception:  # noqa: S110
        pass  # OTLP log export optional


def setup_logging(service_name: str = "taskqueue") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
    _setup_otlp_log_export(service_name)
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    return structlog.get_logger(name)
