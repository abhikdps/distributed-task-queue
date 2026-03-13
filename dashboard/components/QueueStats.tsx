"use client";

import type { QueueStats as Stats } from "@/app/page";

export function QueueStats({ stats, loading }: { stats: Stats | null; loading: boolean }) {
  if (loading && !stats) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
        <p className="text-zinc-500">Loading queue stats…</p>
      </div>
    );
  }
  if (!stats) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
        <p className="text-zinc-500">No stats (is the API running on :8080?)</p>
      </div>
    );
  }
  const cards = [
    { label: "Pending", value: stats.pending_count, color: "text-amber-400" },
    { label: "Running", value: stats.running_count, color: "text-blue-400" },
    { label: "Completed today", value: stats.completed_today, color: "text-emerald-400" },
    { label: "Failed today", value: stats.failed_today, color: "text-red-400" },
    { label: "P99 latency (ms)", value: stats.p99_latency_ms.toFixed(2), color: "text-zinc-300" },
    { label: "Throughput/s", value: stats.throughput_per_sec.toFixed(2), color: "text-zinc-300" },
  ];
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
      <h2 className="mb-4 text-lg font-medium text-zinc-200">Queue stats</h2>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-6">
        {cards.map(({ label, value, color }) => (
          <div key={label} className="rounded-lg bg-zinc-800/50 p-3">
            <p className="text-xs text-zinc-500">{label}</p>
            <p className={`text-xl font-semibold ${color}`}>{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
