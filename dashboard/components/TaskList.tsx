"use client";

import type { Task } from "@/app/page";

const statusColors: Record<string, string> = {
  PENDING: "bg-zinc-600",
  QUEUED: "bg-amber-600",
  RUNNING: "bg-blue-600",
  SUCCESS: "bg-emerald-600",
  FAILED: "bg-red-600",
  CANCELLED: "bg-zinc-500",
};

function formatTs(ms: number) {
  if (!ms) return "—";
  return new Date(ms).toISOString().replace("T", " ").slice(0, 19);
}

export function TaskList({
  tasks,
  total,
  loading,
  onRefresh,
}: {
  tasks: Task[];
  total: number;
  loading: boolean;
  onRefresh: () => void;
}) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-medium text-zinc-200">Recent tasks ({total})</h2>
        <button
          type="button"
          onClick={onRefresh}
          className="rounded-md bg-zinc-700 px-3 py-1.5 text-sm text-zinc-200 hover:bg-zinc-600"
        >
          Refresh
        </button>
      </div>
      {loading && tasks.length === 0 ? (
        <p className="text-zinc-500">Loading…</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-700 text-zinc-400">
                <th className="pb-2 pr-4">Task ID</th>
                <th className="pb-2 pr-4">Status</th>
                <th className="pb-2 pr-4">Priority</th>
                <th className="pb-2 pr-4">Attempt</th>
                <th className="pb-2 pr-4">Created</th>
                <th className="pb-2 pr-4">Payload</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.task_id} className="border-b border-zinc-800">
                  <td className="py-2 pr-4 font-mono text-xs text-zinc-300">{t.task_id.slice(0, 8)}…</td>
                  <td className="py-2 pr-4">
                    <span className={`inline-block rounded px-2 py-0.5 text-xs ${statusColors[t.status] ?? "bg-zinc-600"}`}>
                      {t.status}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-zinc-400">{t.priority}</td>
                  <td className="py-2 pr-4 text-zinc-400">{t.attempt}/{t.max_retries}</td>
                  <td className="py-2 pr-4 text-zinc-500">{formatTs(t.created_at)}</td>
                  <td className="max-w-[200px] truncate py-2 text-zinc-500">{t.payload}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
