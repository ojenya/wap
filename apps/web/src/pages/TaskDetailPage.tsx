import type { StageExecution, WorkflowRun } from "@wap/shared";
import { ArrowLeft, Loader2, Play } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { useStartRun, useTask } from "@/api/hooks";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function StageItem({ stage }: { stage: StageExecution }) {
  return (
    <Card>
      <CardContent className="space-y-3 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="font-medium">
              <span className="mr-2 font-mono text-xs text-muted-foreground">
                {String(stage.order_index + 1).padStart(2, "0")}
              </span>
              {stage.name}
            </div>
            <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted-foreground">
              <span>{stage.agent_role}</span>
              <span>{stage.tokens} tokens</span>
              <span>{stage.duration_ms.toFixed(1)} ms</span>
              <span>{stage.evidence.length} evidence</span>
            </div>
          </div>
          <StatusBadge value={stage.status} />
        </div>
        {Object.keys(stage.output_payload).length > 0 && (
          <pre className="max-h-64 overflow-auto rounded-xl bg-[#f7f7f8] p-3 text-xs leading-relaxed">
            {JSON.stringify(stage.output_payload, null, 2)}
          </pre>
        )}
        {stage.error && <p className="text-xs text-destructive">{stage.error}</p>}
      </CardContent>
    </Card>
  );
}

function RunView({ run }: { run: WorkflowRun }) {
  const report = run.artifacts.find((a) => a.kind === "report");
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold">Run {run.workflow_version}</h2>
        <StatusBadge value={run.status} />
        <span className="text-sm text-muted-foreground">{run.total_tokens} tokens</span>
        {run.risk_level && <StatusBadge value={run.risk_level} />}
      </div>
      {run.worktree_path && (
        <p className="rounded-xl bg-[#f7f7f8] px-3 py-2 font-mono text-xs text-muted-foreground">
          worktree: {run.worktree_path}
        </p>
      )}
      <div className="space-y-3">
        {run.stages.map((s) => (
          <StageItem key={s.id} stage={s} />
        ))}
      </div>
      {report && (
        <Card>
          <CardHeader>
            <CardTitle>Final report</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap rounded-xl bg-[#f7f7f8] p-4 text-sm leading-relaxed">
              {report.content}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export function TaskDetailPage() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  const startRun = useStartRun(taskId);

  if (task.isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (task.isError || !task.data) {
    return <p className="text-sm text-destructive">Task not found.</p>;
  }

  const latestRun = task.data.runs.at(-1);

  return (
    <div className="space-y-6">
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Back to tasks
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{task.data.title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {task.data.description || "No description"}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <StatusBadge value={task.data.task_type} />
            {task.data.repo_url && (
              <span className="text-xs text-muted-foreground">{task.data.repo_url}</span>
            )}
          </div>
        </div>
        <Button onClick={() => startRun.mutate()} disabled={startRun.isPending}>
          {startRun.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          Run workflow
        </Button>
      </div>

      {startRun.isError && (
        <p className="text-sm text-destructive">{(startRun.error as Error).message}</p>
      )}

      {latestRun ? (
        <RunView run={latestRun} />
      ) : (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No runs yet. Click “Run workflow” to execute the multi-agent lifecycle in a worktree.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
