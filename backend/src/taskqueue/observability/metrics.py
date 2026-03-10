from prometheus_client import Counter, Histogram, Gauge

metrics = {
    "tasks_submitted_total": Counter(
        "taskqueue_tasks_submitted_total",
        "Total tasks submitted",
        ["queue"],
    ),
    "tasks_completed_total": Counter(
        "taskqueue_tasks_completed_total",
        "Total tasks completed",
        ["queue", "status"],
    ),
    "task_latency_seconds": Histogram(
        "taskqueue_task_latency_seconds",
        "Task processing latency",
        ["queue"],
        buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    ),
    "api_request_duration_seconds": Histogram(
        "taskqueue_api_request_duration_seconds",
        "gRPC request duration",
        ["method"],
        buckets=(0.0001, 0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1),
    ),
    "queue_depth": Gauge(
        "taskqueue_queue_depth",
        "Current pending/queued task count",
        ["queue"],
    ),
}
