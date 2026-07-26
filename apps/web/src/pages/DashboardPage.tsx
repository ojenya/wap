import { Link } from "react-router-dom";

import { useMetrics } from "@/api/hooks";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function DashboardPage() {
  const metrics = useMetrics();
  const m = metrics.data;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Cost, latency and run health across the multi-agent factory.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Runs", m?.runs_total ?? "—"],
          ["Completed", m?.runs_completed ?? "—"],
          ["Awaiting approval", m?.runs_awaiting_approval ?? "—"],
          ["Failed", m?.runs_failed ?? "—"],
        ].map(([label, value]) => (
          <Card key={label}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
            </CardHeader>
            <CardContent className="text-3xl font-semibold tracking-tight">{value}</CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Cost & latency</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Total tokens</span>
              <span className="font-medium">{m?.total_tokens ?? 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Avg tokens / run</span>
              <span className="font-medium">{(m?.avg_tokens ?? 0).toFixed(1)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Avg duration</span>
              <span className="font-medium">{(m?.avg_duration_ms ?? 0).toFixed(1)} ms</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Stage avg latency</CardTitle>
          </CardHeader>
          <CardContent className="max-h-56 space-y-1 overflow-auto text-sm">
            {Object.entries(m?.stage_avg_ms ?? {}).map(([name, ms]) => (
              <div key={name} className="flex justify-between gap-3">
                <span className="text-muted-foreground">{name}</span>
                <span className="font-mono text-xs">{ms.toFixed(2)} ms</span>
              </div>
            ))}
            {!m && <p className="text-muted-foreground">Loading…</p>}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent runs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {(m?.recent_runs ?? []).map((run) => (
            <Link
              key={run.id}
              to={`/tasks/${run.task_id}`}
              className="flex items-center justify-between rounded-xl border px-3 py-2 text-sm hover:bg-black/[0.02]"
            >
              <span className="font-mono text-xs text-muted-foreground">{run.id.slice(0, 8)}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">{run.total_tokens} tok</span>
                <StatusBadge value={run.status} />
              </div>
            </Link>
          ))}
          {m && m.recent_runs.length === 0 && (
            <p className="text-sm text-muted-foreground">No runs yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
