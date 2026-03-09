import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parent.parent.parent.parent
_backend_dir = Path(__file__).resolve().parent.parent.parent
for _d in (_project_root, _backend_dir, Path.cwd()):
    _env = _d / ".env"
    if _env.exists():
        load_dotenv(_env, override=True)


@dataclass(frozen=True)
class Config:
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    kafka_topic_tasks: str = os.getenv("KAFKA_TOPIC_TASKS", "taskqueue.tasks")
    kafka_topic_dlq: str = os.getenv("KAFKA_TOPIC_DLQ", "taskqueue.dlq")

    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_user: str = os.getenv("POSTGRES_USER", "taskqueue")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "taskqueue_secret")
    postgres_db: str = os.getenv("POSTGRES_DB", "taskqueue")

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    grpc_host: str = os.getenv("GRPC_HOST", "0.0.0.0")
    grpc_port: int = int(os.getenv("GRPC_PORT", "50051"))

    otel_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    otel_service_name: str = os.getenv("OTEL_SERVICE_NAME", "taskqueue-api")
    prometheus_port: int = int(os.getenv("PROMETHEUS_PORT", "9090"))


config = Config()
