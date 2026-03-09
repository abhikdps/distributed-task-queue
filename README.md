# Distributed Task Queue

A highly available task queue system with **priority scheduling**, **retry logic**, and **real-time monitoring**. Designed for **10M+ tasks/day**, **zero downtime**, and **sub-ms P99** latency.

## Architecture

```mermaid
flowchart TB
  subgraph clients["Clients"]
    Dashboard["Dashboard (Next.js)"]
    CLI["gRPC / HTTP clients"]
  end

  subgraph api["API (Python)"]
    Backend["Backend API (gRPC :50051, HTTP :8080)"]
  end

  subgraph data["Data plane"]
    Postgres[(PostgreSQL)]
    Redis[(Redis)]
    Kafka[Apache Kafka]
  end

  subgraph workers["Workers"]
    W1["Worker 1"]
    W2["Worker 2"]
    WN["Worker N"]
  end

  subgraph observability["Observability (optional)"]
    OTEL["OTEL Collector"]
    Prom["Prometheus"]
    Loki[(Loki)]
    Grafana["Grafana"]
  end

  Dashboard -->|"/api/*"| Backend
  CLI --> Backend
  Backend --> Postgres
  Backend --> Redis
  Backend -->|enqueue| Kafka
  Kafka --> W1 & W2 & WN
  W1 & W2 & WN --> Postgres
  W1 & W2 & WN --> Redis

  Backend -.->|metrics, logs| OTEL
  W1 & W2 & WN -.->|metrics, logs| OTEL
  OTEL --> Prom
  OTEL --> Loki
  Prom --> Grafana
  Loki --> Grafana
```

- **API:** Python gRPC service (task submission, status, scheduling)
- **Broker:** Apache Kafka (task distribution, priority queues)
- **Primary DB:** PostgreSQL (task metadata, state, history)
- **Cache:** Redis (hot path cache, rate limits, deduplication)
- **Workers:** Python Kafka consumers, orchestrated on Kubernetes
- **Monitoring:** Prometheus + Grafana + OpenTelemetry (tracing) + Loki (logs)
