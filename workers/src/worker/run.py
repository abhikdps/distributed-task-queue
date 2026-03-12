import asyncio
from prometheus_client import start_http_server

from .config import config
from .consumer import run_consumer
from .logging import setup_logging, get_logger

logger = get_logger("worker.run")


def main() -> None:
    setup_logging("taskqueue-worker")
    metrics_port = config.prometheus_port
    for attempt in range(5):
        try:
            start_http_server(metrics_port)
            break
        except OSError as e:
            if "Address already in use" in str(e) or getattr(e, "errno", None) == 48:
                metrics_port += 1
                if attempt == 4:
                    raise SystemExit(
                        "Metrics port in use. Set PROMETHEUS_PORT to a free port (e.g. 9096) in .env"
                    ) from e
            else:
                raise
    logger.info("Worker starting", concurrency=config.worker_concurrency, metrics_port=metrics_port)
    logger.info(
        "Connecting to Kafka",
        bootstrap=config.kafka_bootstrap_servers,
        hint="If Kafka is not up, start infrastructure: podman compose up -d, wait ~30s, then run worker again.",
    )
    asyncio.run(run_consumer())


if __name__ == "__main__":
    main()
