#!/usr/bin/env python3
"""
Scale test for the task queue: submit many tasks and optionally wait for completion.

By default each task gets a distinct payload: {"scale_test": true, "index": 0..count-1}
so you can see payloads in the dashboard/API. Use --payload '{"your":"json"}' to use
one payload for all tasks.

Uses one TCP connection per worker (HTTP keep-alive) to avoid ephemeral port exhaustion
(Errno 49) when submitting very large counts.

Usage:
  python3 scripts/scale_test.py --count 500 --concurrency 20
  python3 scripts/scale_test.py --count 200 --concurrency 10 --wait
  python3 scripts/scale_test.py --count 100000 --concurrency 10

Requires: backend running (default http://localhost:8080), workers running.
Uses only Python stdlib.
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection, HTTPSConnection, HTTPException

DEFAULT_BASE = "http://localhost:8080"
TERMINAL = frozenset({"SUCCESS", "FAILED", "CANCELLED"})


def _submit_batch(
    host: str,
    port: int,
    use_https: bool,
    path: str,
    queue: str,
    indices: list[int],
    use_indexed_payload: bool,
    payload_template: str,
    priority: int,
    timeout: float,
) -> tuple[list[str], list[str]]:
    """Submit a batch of tasks over a single persistent connection. Returns (task_ids, errors)."""
    task_ids: list[str] = []
    errors: list[str] = []
    conn_class = HTTPSConnection if use_https else HTTPConnection
    conn = conn_class(host, port, timeout=timeout)
    try:
        for i in indices:
            payload = json.dumps({"scale_test": True, "index": i}) if use_indexed_payload else payload_template
            body = json.dumps({"queue": queue, "payload": payload, "priority": priority}).encode("utf-8")
            try:
                conn.request("POST", path, body, headers={"Content-Type": "application/json"})
                resp = conn.getresponse()
                data = resp.read()
                if resp.status == 200:
                    out = json.loads(data.decode())
                    tid = out.get("task_id")
                    if tid:
                        task_ids.append(tid)
                else:
                    errors.append(f"HTTP {resp.status}")
            except (OSError, HTTPException, json.JSONDecodeError) as e:
                errors.append(str(e))
                try:
                    conn.close()
                except Exception:
                    pass
                conn = conn_class(host, port, timeout=timeout)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return task_ids, errors


def _partition(count: int, concurrency: int) -> list[list[int]]:
    """Split indices 0..count-1 into concurrency chunks."""
    chunks: list[list[int]] = [[] for _ in range(concurrency)]
    for i in range(count):
        chunks[i % concurrency].append(i)
    return chunks


def fetch_tasks(base_url: str, limit: int = 500) -> list[dict]:
    """GET /api/tasks and return list of task dicts."""
    url = f"{base_url.rstrip('/')}/api/tasks?limit={limit}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
        return data.get("tasks") or []


def main() -> None:
    p = argparse.ArgumentParser(description="Scale test: submit tasks and optionally wait for completion.")
    p.add_argument("--base-url", default=DEFAULT_BASE, help=f"API base URL (default {DEFAULT_BASE})")
    p.add_argument("--count", type=int, default=100, help="Number of tasks to submit (default 100)")
    p.add_argument("--concurrency", type=int, default=10, help="Concurrent submit requests (default 10)")
    p.add_argument("--queue", default="default", help="Queue name (default default)")
    p.add_argument(
        "--payload",
        default="",
        help='Payload JSON for all tasks; if empty, each task gets {"scale_test":true,"index":i}',
    )
    p.add_argument("--priority", type=int, default=5, help="Priority (default 5)")
    p.add_argument("--wait", action="store_true", help="Wait for all tasks to complete and report latency")
    p.add_argument(
        "--poll-interval", type=float, default=1.0, help="Seconds between status polls when --wait (default 1)"
    )
    p.add_argument("--poll-timeout", type=float, default=300.0, help="Max seconds to wait for completion (default 300)")
    args = p.parse_args()

    base = args.base_url.rstrip("/")
    parsed = urllib.parse.urlparse(base)
    use_https = parsed.scheme == "https"
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if use_https else 80)
    path = (parsed.path.rstrip("/") or "") + "/api/submit"

    print(f"Submitting {args.count} tasks to {base} (concurrency={args.concurrency}, queue={args.queue}) ...")

    task_ids: list[str] = []
    errors: list[str] = []
    start_submit = time.perf_counter()
    use_indexed_payload = not args.payload.strip()
    chunks = _partition(args.count, args.concurrency)

    def run_batch(chunk: list[int]) -> tuple[list[str], list[str]]:
        return _submit_batch(
            host=host,
            port=port,
            use_https=use_https,
            path=path,
            queue=args.queue,
            indices=chunk,
            use_indexed_payload=use_indexed_payload,
            payload_template=args.payload,
            priority=args.priority,
            timeout=30.0,
        )

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        for tids, errs in ex.map(run_batch, chunks):
            task_ids.extend(tids)
            errors.extend(errs)

    submit_elapsed = time.perf_counter() - start_submit
    ok = len(task_ids)
    print(f"Submitted {ok}/{args.count} tasks in {submit_elapsed:.2f}s")
    if ok:
        print(f"  Submit throughput: {ok / submit_elapsed:.1f} tasks/s")
    if errors:
        print(f"  Errors: {len(errors)} (sample: {errors[:3]})")

    if not task_ids:
        print("No tasks submitted. Check backend is running and --base-url.")
        sys.exit(1)

    if not args.wait:
        print("Done (use --wait to wait for completion and see latency).")
        return

    # Poll until all terminal or timeout
    ids_set = set(task_ids)
    deadline = time.monotonic() + args.poll_timeout
    completed: dict[str, dict] = {}

    while ids_set and time.monotonic() < deadline:
        time.sleep(args.poll_interval)
        tasks = fetch_tasks(base, limit=max(500, len(task_ids)))
        for t in tasks:
            tid = t.get("task_id")
            if tid in ids_set and t.get("status") in TERMINAL:
                completed[tid] = t
                ids_set.discard(tid)
        if not ids_set:
            break
        print(f"  Waiting: {len(ids_set)}/{len(task_ids)} still in progress ...")

    if ids_set:
        print(f"Timeout: {len(ids_set)} tasks did not reach terminal state")
    else:
        print(f"All {len(completed)} tasks completed.")

    # Latency from created_at / completed_at if available (milliseconds in API)
    latencies_ms: list[float] = []
    for t in completed.values():
        created = t.get("created_at") or 0
        completed_ts = t.get("completed_at") or 0
        if completed_ts and created:
            latencies_ms.append((completed_ts - created))

    if latencies_ms:
        latencies_ms.sort()
        n = len(latencies_ms)
        p50 = latencies_ms[n // 2]
        p95 = latencies_ms[int(n * 0.95)] if n >= 20 else latencies_ms[-1]
        print(f"  Latency (created → completed): median={p50:.0f}ms, p95={p95:.0f}ms, n={n}")
    status_counts: dict[str, int] = {}
    for t in completed.values():
        s = t.get("status", "?")
        status_counts[s] = status_counts.get(s, 0) + 1
    print(f"  Status: {status_counts}")


if __name__ == "__main__":
    main()
