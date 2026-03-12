from prometheus_client import Counter, Histogram, Gauge

tasks_completed_total = Counter(
    "taskqueue_worker_tasks_completed_total",
    "Tasks completed by workers",
    ["queue", "status"],
)
task_latency_seconds = Histogram(
    "taskqueue_task_latency_seconds",
    "Task processing latency",
    ["queue"],
    buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)
queue_depth = Gauge("taskqueue_queue_depth", "Queue depth", ["queue"])

metrics = {
    "tasks_completed_total": tasks_completed_total,
    "task_latency_seconds": task_latency_seconds,
    "queue_depth": queue_depth,
}
