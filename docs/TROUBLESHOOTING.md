# Troubleshooting: What we fixed

This doc records fixes applied so the API and workers run reliably after `podman compose up -d` (or with local Postgres).

---

## 1. PostgreSQL: "role \"taskqueue\" does not exist"

**Cause:** The API was connecting to a Postgres that didn’t have the `taskqueue` role. Often that’s **local Homebrew Postgres** on port 5432 instead of the compose container.

**Fixes applied:**

- **Backend loads `.env` from project root**
  In `backend/src/taskqueue/config.py`, `load_dotenv()` now looks for `.env` in:
  - project root (parent of `backend/`),
  - `backend/`,
  - current working directory.
  So a single `.env` in the project root is used when you run `cd backend && python -m taskqueue.api.server`.

- **Create the role in the Postgres you actually use**
  If you use **local Postgres** (e.g. Homebrew), create the role and DB once (Mac superuser is often your username, not `postgres`):

  ```bash
  psql -h 127.0.0.1 -p 5432 -U $(whoami) -d postgres -c "CREATE ROLE taskqueue WITH LOGIN PASSWORD 'taskqueue_secret';" -c "CREATE DATABASE taskqueue OWNER taskqueue;" -c "GRANT ALL PRIVILEGES ON DATABASE taskqueue TO taskqueue;"
  ```

  If you use **only the compose Postgres**, stop local Postgres so the container can bind to 5432 (e.g. `brew services stop postgresql`), then `podman compose up -d`. See [docs/POSTGRES_SETUP.md](POSTGRES_SETUP.md).

---

## 2. API: "Address already in use" (metrics port)

**Cause:** The API’s Prometheus metrics server defaults to port **9090**. With `podman compose up -d`, the Prometheus container also uses 9090, so the API failed to bind.

**Fix applied:**

- In `backend/src/taskqueue/api/server.py`, if binding to the configured metrics port fails with “Address already in use”, the server tries the next ports (9090, 9091, …) up to 5 times and uses the first free one. It also cleans up (closes DB, Redis, Kafka) and exits with a clear message if no port is free.

**Optional:** Set a dedicated port for the API in `.env` so it doesn’t clash with compose Prometheus or the worker:

```bash
PROMETHEUS_PORT=9095
```

---

## 3. Worker: "Address already in use" (metrics port)

**Cause:** The worker defaults to metrics port **9091**. If the API had already bound to 9091 (after falling back from 9090), the worker failed to start.

**Fixes applied:**

- **Workers load `.env` from project root**
  In `workers/src/worker/config.py`, `load_dotenv()` now loads from project root and `workers/` (same pattern as the backend), so `PROMETHEUS_PORT` in the root `.env` is used when you run `cd workers && PYTHONPATH=src python -m worker.run`.

- **Worker metrics port fallback**
  In `workers/src/worker/run.py`, if the configured metrics port is in use, the worker tries the next ports (up to 5 attempts) and starts the metrics server on the first available port.

**Optional:** In project root `.env`, give the worker its own port:

```bash
# API can use 9095, worker use 9096 (or leave unset and let fallback work)
PROMETHEUS_PORT=9096
```

(If you run multiple workers, either use one metrics port per process or a single shared port with proper scraping config.)

---

## 4. Quick reference: run order

1. Start infrastructure: `podman compose up -d` (or `./compose.sh up -d`).
2. Ensure `.env` is in the **project root** with at least `POSTGRES_*`, and optionally `PROMETHEUS_PORT` for API/worker.
3. Start API: `cd backend && pip install -e . && python -m taskqueue.api.server`
4. Start worker(s): `cd workers && pip install -r requirements.txt && PYTHONPATH=src python -m worker.run`
5. Start dashboard: `cd dashboard && npm install && npm run dev`

If you use local Postgres, create the `taskqueue` role once (see section 1). If you use only compose Postgres, stop local Postgres first so the container can use 5432.

---

## 5. Worker: Kafka "Topic not available" / "GroupCoordinatorNotAvailableError"

**Cause:** The worker connects to Kafka at `KAFKA_BOOTSTRAP_SERVERS` (default `localhost:9092`). Those messages mean Kafka isn’t running or isn’t reachable from the host.

**What to do:**

1. **Start infrastructure first** (from the project root):

   ```bash
   podman compose up -d
   # or
   ./compose.sh up -d
   ```

2. **Wait 30–60 seconds** for Zookeeper and Kafka to be fully up (Kafka depends on Zookeeper).
3. **Check that Kafka is listening** on the host:

   ```bash
   nc -zv localhost 9092
   # or
   podman ps   # ensure kafka (and zookeeper) containers are running
   ```

4. **Start the worker again:**

   ```bash
   cd workers && PYTHONPATH=src python -m worker.run
   ```

**Changes made in the worker:**

- The worker **retries connecting to Kafka** up to 12 times (every 5s after a 15s timeout). If Kafka never becomes reachable, it exits with a clear message instead of logging errors forever.
- **Kafka client log level** is set to WARNING so you no longer get spammed with repeated "Topic not available" / "GroupCoordinatorNotAvailableError" lines; you’ll see one "Kafka not ready, retrying" per attempt instead.
- A **startup hint** is printed: if Kafka isn’t up, start `podman compose up -d`, wait ~30s, then run the worker again.

If you run **without** compose (e.g. Kafka on another host), set in `.env`:

```bash
KAFKA_BOOTSTRAP_SERVERS=your-kafka-host:9092
```

---

## 6. No data in Prometheus / Grafana

**Cause:** Prometheus runs inside a container and scrapes the **API** and **workers** on the host. If the API/workers use the default metrics ports (9090/9091), they clash with the Prometheus container (which uses 9090), and Prometheus is configured to scrape fixed ports (9095 and 9096) so the host processes must listen there.

**What to do:**

1. **Use fixed metrics ports** so Prometheus can scrape the host:
   - In the **project root** `.env`, set:

     ```bash
     PROMETHEUS_PORT=9095
     ```

   - Create **workers/.env** with `PROMETHEUS_PORT=9096` (you can copy from `workers/.env.example`).
   Workers load root `.env` then `workers/.env`, so the API gets 9095 and the worker gets 9096.

2. **Restart the API and workers** so they bind to 9095 and 9096. The Prometheus config (`monitoring/prometheus/prometheus.yml`) is set to scrape `host.docker.internal:9095` (API) and `:9096` (workers).

3. **Restart Prometheus** if you changed its config or compose (e.g. `podman compose up -d` again). The compose file adds `extra_hosts: host.docker.internal:host-gateway` so that the Prometheus container can reach the host (needed on Linux).

4. **Check scrape targets:** In Prometheus, open **Status → Targets**. You should see:
   - `taskqueue-api` (host.docker.internal:9095) — **UP**
   - `taskqueue-workers` (host.docker.internal:9096) — **UP**
   If either is **DOWN**, the API or worker isn’t running, or it’s not listening on 9095/9096 (check the log line “Prometheus metrics” / “Worker starting … metrics_port=…”).

5. **Generate some traffic** so there are metrics to show: submit a few tasks from the dashboard or run `python3 scripts/scale_test.py --count 5`. Then in Prometheus **Graph** try `taskqueue_tasks_submitted_total` or `rate(taskqueue_tasks_completed_total[5m])`. In Grafana, open the **Task Queue** dashboard; it should show data once scrapes are UP and tasks have run.

**If Prometheus targets stay DOWN (e.g. on Linux Podman):** The scrape config uses `host.docker.internal`. On Docker Desktop (Mac/Windows) that often works. On Linux Podman it may not resolve. Options: (a) Use your machine’s IP (e.g. `192.168.x.x`) in `monitoring/prometheus/prometheus.yml` instead of `host.docker.internal` for the API and worker targets. (b) Or run Prometheus on the host (no container) and point it at `localhost:9095` and `localhost:9096`.

**If Grafana shows data for Queue depth / Task latency / Tasks completed but "No Data" for Tasks submitted, Submit rate, and API P99:** Those three come from the **API**; the others come from the **worker**. So Prometheus is scraping the worker but not the API. In Prometheus, open **Status → Targets** and check **taskqueue-api**: it must be **UP**. If it is DOWN, the Prometheus container can’t reach the API. Ensure (1) the API is running, (2) the API is listening on **9095** (set `PROMETHEUS_PORT=9095` in the project root `.env`), (3) in `monitoring/prometheus/prometheus.yml` the API target uses an address the container can reach (e.g. your host IP instead of `host.docker.internal` on Linux/Podman). Restart the API and then Prometheus if you changed the config.

---

## 7. Podman: "host containers internal IP address is empty" on `compose up`

**Cause:** Adding `extra_hosts: host.docker.internal:host-gateway` to the Prometheus service made Podman resolve the host so the container could reach the host. On some Podman setups (e.g. rootless, or older versions), `host-gateway` is not available and container creation fails.

**Fix:** The compose file no longer adds that entry, so `podman compose up -d` should succeed. If Prometheus then can’t reach the API/workers (targets DOWN), see section 6 above: use your host IP in `prometheus.yml` or run Prometheus on the host.
