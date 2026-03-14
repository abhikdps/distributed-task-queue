"use client";

import { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

interface Sample {
  time: string;
  pending?: number;
  completed?: number;
}

export function MetricsCharts() {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [stats, setStats] = useState<{ pending_count?: number; completed_today?: number } | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch("/api/stats");
        if (res.ok) {
          const data = await res.json();
          setStats(data);
          setSamples((prev) => {
            const next = [
              ...prev.slice(-59),
              {
                time: new Date().toLocaleTimeString("en-US", { hour12: false }),
                pending: data.pending_count ?? 0,
                completed: data.completed_today ?? 0,
              },
            ];
            return next;
          });
        }
      } catch (_) {}
    };
    fetchStats();
    const t = setInterval(fetchStats, 2000);
    return () => clearInterval(t);
  }, []);

  if (samples.length < 2) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
        <h2 className="mb-4 text-lg font-medium text-zinc-200">Metrics (live)</h2>
        <p className="text-zinc-500">Collecting samples…</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
      <h2 className="mb-4 text-lg font-medium text-zinc-200">Metrics (live)</h2>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={samples}>
            <defs>
              <linearGradient id="pending" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="completed" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="time" stroke="#71717a" fontSize={10} />
            <YAxis stroke="#71717a" fontSize={10} />
            <Tooltip
              contentStyle={{ backgroundColor: "#27272a", border: "1px solid #3f3f46" }}
              labelStyle={{ color: "#a1a1aa" }}
            />
            <Area type="monotone" dataKey="pending" stroke="#f59e0b" fillOpacity={1} fill="url(#pending)" name="Pending" />
            <Area type="monotone" dataKey="completed" stroke="#10b981" fillOpacity={1} fill="url(#completed)" name="Completed today" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-zinc-500">
        Pending and completed (today) — polling every 2s. For full metrics use Grafana (Prometheus + Loki).
      </p>
    </div>
  );
}
