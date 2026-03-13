"use client";

import { useEffect, useState } from "react";
import { QueueStats } from "@/components/QueueStats";
import { TaskList } from "@/components/TaskList";
import { SubmitTask } from "@/components/SubmitTask";
import { MetricsCharts } from "@/components/MetricsCharts";

export default function Home() {
  const [stats, setStats] = useState<QueueStats | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchStats = async () => {
    try {
      const res = await fetch("/api/stats");
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (_) {}
  };

  const fetchTasks = async () => {
    try {
      const res = await fetch("/api/tasks?limit=20");
      if (res.ok) {
        const data = await res.json();
        setTasks(data.tasks || []);
        setTotal(data.total ?? 0);
      }
    } catch (_) {}
  };

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await Promise.all([fetchStats(), fetchTasks()]);
      setLoading(false);
    };
    load();
    const t = setInterval(() => {
      fetchStats();
      fetchTasks();
    }, 3000);
    return () => clearInterval(t);
  }, []);

  const onTaskSubmitted = () => {
    fetchStats();
    fetchTasks();
  };

  return (
    <div className="space-y-8">
      <QueueStats stats={stats} loading={loading} />
      <MetricsCharts />
      <SubmitTask onSubmitted={onTaskSubmitted} />
      <TaskList tasks={tasks} total={total} loading={loading} onRefresh={fetchTasks} />
    </div>
  );
}

export interface QueueStats {
  pending_count: number;
  running_count: number;
  completed_today: number;
  failed_today: number;
  p99_latency_ms: number;
  throughput_per_sec: number;
}

export interface Task {
  task_id: string;
  status: string;
  payload: string;
  priority: number;
  attempt: number;
  max_retries: number;
  created_at: number;
  updated_at: number;
  queue?: string;
}
