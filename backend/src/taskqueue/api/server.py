from grpc import aio as grpc_aio  # type: ignore[import-untyped]
from prometheus_client import start_http_server as prometheus_start
from aiohttp import web
import asyncio

from .servicer import TaskQueueServicer
from .http_api import create_app as create_http_app
from taskqueue.proto.gen import taskqueue_pb2_grpc
from ..db import init_pool, close_pool, create_tables
from ..cache import init_redis, close_redis
from ..broker import init_producer, close_producer
from ..config import config
from ..observability.logging import setup_logging, get_logger

logger = get_logger("api.server")
HTTP_PORT = 8080


def _hint_infra() -> str:
    return (
        "Start infrastructure first: docker compose up -d  (or: podman compose up -d)\n"
        "See docs/POSTGRES_SETUP.md to use project Postgres or create user/db in your own."
    )


async def serve() -> None:
    setup_logging("taskqueue-api")
    try:
        await init_pool()
    except Exception as e:
        logger.exception("PostgreSQL connection failed")
        raise SystemExit(f"PostgreSQL unavailable: {e}\n{_hint_infra()}") from e
    try:
        await init_redis()
    except Exception as e:
        await close_pool()
        logger.exception("Redis connection failed")
        raise SystemExit(f"Redis unavailable: {e}\n{_hint_infra()}") from e
    try:
        await create_tables()
    except Exception as e:
        await close_pool()
        await close_redis()
        logger.exception("DB init failed")
        raise SystemExit(f"DB init failed: {e}") from e
    try:
        await init_producer()
    except Exception as e:
        await close_pool()
        await close_redis()
        logger.exception("Kafka connection failed")
        raise SystemExit(f"Kafka unavailable: {e}\n{_hint_infra()}") from e

    metrics_port = config.prometheus_port
    for attempt in range(5):
        try:
            prometheus_start(metrics_port)
            logger.info("Prometheus metrics", port=metrics_port)
            break
        except OSError as e:
            if "Address already in use" in str(e) or e.errno == 48:
                metrics_port += 1
                if attempt == 4:
                    await close_producer()
                    await close_redis()
                    await close_pool()
                    raise SystemExit(
                        f"Metrics port {config.prometheus_port}-{metrics_port - 1} in use. "
                        "Set PROMETHEUS_PORT=9095 (or free port) in .env"
                    ) from e
            else:
                raise

    server = grpc_aio.server()
    taskqueue_pb2_grpc.add_TaskQueueServiceServicer_to_server(TaskQueueServicer(), server)
    server.add_insecure_port(f"{config.grpc_host}:{config.grpc_port}")
    await server.start()
    logger.info("gRPC server listening", host=config.grpc_host, port=config.grpc_port)

    http_app = create_http_app()
    runner = web.AppRunner(http_app)
    await runner.setup()
    http_site = web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
    await http_site.start()
    logger.info("HTTP API (dashboard)", port=HTTP_PORT)

    try:
        await server.wait_for_termination()
    finally:
        await runner.cleanup()
        await server.stop(None)
        await close_producer()
        await close_redis()
        await close_pool()
        logger.info("Shutdown complete")


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
