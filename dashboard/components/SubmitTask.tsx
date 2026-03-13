"use client";

import { useState } from "react";

export function SubmitTask({ onSubmitted }: { onSubmitted: () => void }) {
  const [queue, setQueue] = useState("default");
  const [payload, setPayload] = useState('{"hello": "world"}');
  const [priority, setPriority] = useState(5);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ task_id?: string; error?: string } | null>(null);

  const submit = async () => {
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch("/api/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ queue, payload, priority, max_retries: 3 }),
      });
      const data = await res.json();
      if (res.ok) {
        setResult({ task_id: data.task_id });
        onSubmitted();
      } else {
        setResult({ error: data.error || "Failed" });
      }
    } catch (e) {
      setResult({ error: String(e) });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
      <h2 className="mb-4 text-lg font-medium text-zinc-200">Submit task</h2>
      <div className="space-y-3">
        <div>
          <label className="block text-xs text-zinc-500">Queue</label>
          <input
            type="text"
            value={queue}
            onChange={(e) => setQueue(e.target.value)}
            className="mt-1 w-full rounded-md border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-200"
          />
        </div>
        <div>
          <label className="block text-xs text-zinc-500">Payload (JSON)</label>
          <textarea
            value={payload}
            onChange={(e) => setPayload(e.target.value)}
            rows={2}
            className="mt-1 w-full rounded-md border border-zinc-700 bg-zinc-800 px-3 py-2 font-mono text-sm text-zinc-200"
          />
        </div>
        <div>
          <label className="block text-xs text-zinc-500">Priority (0–10)</label>
          <input
            type="number"
            min={0}
            max={10}
            value={priority}
            onChange={(e) => setPriority(Number(e.target.value))}
            className="mt-1 w-24 rounded-md border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-200"
          />
        </div>
        <button
          type="button"
          onClick={submit}
          disabled={loading}
          className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {loading ? "Submitting…" : "Submit"}
        </button>
        {result && (
          <p className={`text-sm ${result.error ? "text-red-400" : "text-emerald-400"}`}>
            {result.task_id ? `Task ID: ${result.task_id}` : result.error}
          </p>
        )}
      </div>
    </div>
  );
}
