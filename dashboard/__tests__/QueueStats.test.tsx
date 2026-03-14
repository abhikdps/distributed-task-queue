import { render, screen } from "@testing-library/react";
import { QueueStats } from "@/components/QueueStats";

describe("QueueStats", () => {
  it("shows loading state when loading and no stats", () => {
    render(<QueueStats stats={null} loading={true} />);
    expect(screen.getByText(/Loading queue stats/)).toBeInTheDocument();
  });

  it("shows no-stats message when not loading and no stats", () => {
    render(<QueueStats stats={null} loading={false} />);
    expect(screen.getByText(/No stats/)).toBeInTheDocument();
  });

  it("renders stats when provided", () => {
    const stats = {
      pending_count: 1,
      running_count: 2,
      completed_today: 10,
      failed_today: 0,
      p99_latency_ms: 50.5,
      throughput_per_sec: 0.1,
    };
    render(<QueueStats stats={stats} loading={false} />);
    expect(screen.getByText("Queue stats")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });
});
