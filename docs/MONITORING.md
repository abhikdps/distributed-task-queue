# Prometheus, Grafana, and Loki

Start the monitoring stack with the rest of infrastructure:

```bash
# From project root
podman compose up -d
# or: docker compose up -d   or   ./compose.sh up -d
```

**So Prometheus and Grafana show data:** The API and workers must run on the **host** and expose metrics on ports **9095** (API) and **9096** (workers). Prometheus (in the container) scrapes those. Set in **project root** `.env`: `PROMETHEUS_PORT=9095`. Create **workers/.env** with: `PROMETHEUS_PORT=9096`. Restart the API and workers. If you see no data, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) section 6.

---

## Prometheus

**URL:** <http://localhost:9090>

**What it is:** Time-series metrics store. It scrapes the API and workers periodically and stores counters/histograms (task counts, latencies, queue depth).

**What to look for:**

1. **Status → Targets** (top menu: **Status** → **Targets**)
   You should see **three jobs**: `prometheus`, `taskqueue-api`, and `taskqueue-workers`. The task queue is the last two. Check that `taskqueue-api` and `taskqueue-workers` are **UP**.
   - If you **only see `prometheus`**: the config file may not be loaded. Check **Status → Configuration** and confirm the **scrape_configs** section includes jobs named `taskqueue-api` and `taskqueue-workers`. Ensure compose is using `./monitoring/prometheus/prometheus.yml` (volume mount in docker-compose.yml).
   - If `taskqueue-api` / `taskqueue-workers` appear but are **DOWN**: the Prometheus container can’t reach the host (e.g. on Linux Podman `host.docker.internal` doesn’t resolve). Use your host’s IP in `monitoring/prometheus/prometheus.yml` instead of `host.docker.internal` (see [TROUBLESHOOTING](TROUBLESHOOTING.md) section 6).

2. **Graph / Query**
   Run PromQL queries, for example:
   - **Submit rate:** `rate(taskqueue_tasks_submitted_total[5m])` — tasks submitted per second by queue.
   - **Completion rate:** `rate(taskqueue_tasks_completed_total[5m])` — tasks completed per second (by queue and status).
   - **Queue depth:** `taskqueue_queue_depth` — current pending/queued count by queue.
   - **Task latency P99:**
     `histogram_quantile(0.99, sum(rate(taskqueue_task_latency_seconds_bucket[5m])) by (le, queue))`
     — 99th percentile task execution time in seconds.
   - **API latency P99:**
     `histogram_quantile(0.99, sum(rate(taskqueue_api_request_duration_seconds_bucket[5m])) by (le, method))`
     — 99th percentile gRPC call duration.

Use the **Graph** tab to plot one or more of these over time.

---

## Grafana

**URL:** <http://localhost:3000>
(If the Next.js dashboard also uses port 3000, start one of them on a different port, e.g. `npm run dev` with `PORT=3001` for the app dashboard.)

**Login:** `admin` / `admin` (change password when prompted).

**What it is:** Dashboards and exploration over Prometheus (and optionally Loki). The project ships a **Task Queue** dashboard that uses the same metrics.

**What to look for:**

1. **Connections → Data sources**
   You should see **Prometheus** (default) and **Loki**. Prometheus URL is `http://prometheus:9090` (from inside Docker). If the dashboard shows “No data”, check that Prometheus targets are UP and that the API/workers are running so metrics exist.

2. **Dashboards → Task Queue**
   Open the pre-built **Task Queue** dashboard. Set the time range (top right) to **Last 1 hour** (or more); the dashboard default is 1 hour. If you see **No data**: (a) generate traffic (submit tasks from the app or run `python3 scripts/scale_test.py --count 10`), (b) ensure Prometheus targets are UP (Status → Targets in Prometheus), (c) in Grafana **Explore** choose the Prometheus datasource and run `sum(taskqueue_tasks_submitted_total)` to confirm Prometheus has the metrics. The dashboard shows:
   - **Tasks submitted (total)** — cumulative submissions.
   - **Submit rate (1h)** — submissions per second over the last hour.
   - **Queue depth** — current pending/queued tasks.
   - **API P99 latency (s)** — 99th percentile gRPC request duration.
   - **Task latency P99** — graph of task execution time by queue.
   - **Tasks completed (total)** — cumulative completions (from workers).

3. **Explore**
   Choose the **Prometheus** datasource and run the same PromQL queries as in Prometheus (e.g. `taskqueue_queue_depth`, or the `histogram_quantile` expressions above) for ad‑hoc checks.

---

## Loki

**URL:** <http://localhost:3100>
(Loki exposes an HTTP API; you normally query it from Grafana, not in a browser.)

**What it is:** Log aggregation store. Grafana can query Loki for log lines and show them next to metrics/traces.

**How application logs get to Loki:** The OpenTelemetry collector is configured with a **logs pipeline**: the API and workers send logs via **OTLP** (HTTP) to the collector; the collector exports them to Loki. So you need to:

1. **Start the stack** (compose includes the collector and Loki).
2. **Set the OTLP endpoint** so the API and workers export logs. In your **project root `.env`** (or in the environment when running the API/workers), set:

   ```bash
   OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
   ```

   (Use `http://localhost:4318` when the API/workers run on the host and the collector is in Docker; the collector exposes OTLP HTTP on 4318.) The API uses `OTEL_SERVICE_NAME=taskqueue-api` (or leave default); the worker uses the same endpoint and will appear as `taskqueue-worker` if you set that name when calling `setup_logging`.)
3. **Restart the API and workers** so they load the OTLP log exporter and start sending logs.

**What to look for in Grafana:**

- In **Grafana → Explore**, select the **Loki** datasource and set the time range (e.g. **Last 1 hour**).
- **Discover labels:** The exact label names depend on the collector’s Loki exporter. Use the **Label browser** (next to the query field) to see which labels exist (e.g. `job`, `level`, `exporter`, or `service_name` / `service.name` if resource attributes are mapped). Or run a broad query to see all log streams:

  ```logql
  {}
  ```

  If you see streams, click one and check the labels in the log line or in the label dropdowns.
- **Query by service:** If the exporter exposes the OTLP resource attribute `service.name` as a label, try (with or without the dot):
  - `{service_name="taskqueue-api"}` or `{service.name="taskqueue-api"}`
  - `{service_name="taskqueue-worker"}` or `{service.name="taskqueue-worker"}`
- **Filter by text:** Once you have a working stream selector, add a filter, e.g.:
  - `|= "Task completed"` or `|= "error"` or `|= "ERROR"`.
- **No logs at all?** Check: (1) `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` is set and API/workers were restarted, (2) you’ve generated some activity (submit a task, run the worker), (3) the otel-collector container is running and its logs pipeline has no errors.

---

## Quick reference

| Tool       | URL                     | Purpose                                                                    |
|------------|-------------------------|----------------------------------------------------------------------------|
| Prometheus | <http://localhost:9090> | Scrape and query metrics (API + workers).                                  |
| Grafana    | <http://localhost:3000> | Dashboards (Task Queue) and Explore (Prometheus + Loki).                   |
| Loki       | <http://localhost:3100> | Log storage; query from Grafana Explore (logs need to be shipped to Loki). |

**Useful metrics:** `taskqueue_tasks_submitted_total`, `taskqueue_tasks_completed_total`, `taskqueue_queue_depth`, `taskqueue_task_latency_seconds`, `taskqueue_api_request_duration_seconds`.
