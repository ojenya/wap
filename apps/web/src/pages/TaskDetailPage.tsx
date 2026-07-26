import type { Artifact, StageExecution, WorkflowRun } from "@wap/shared";
import { ArrowLeft, Check, Loader2, MessageSquare, Play, Send, Square } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "@/api/client";
import {
  useApproveRun,
  useCancelRun,
  useRunComments,
  useRunEvents,
  useStartRun,
  useTask,
} from "@/api/hooks";
import { RunTimeline } from "@/components/RunTimeline";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

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

function ArtifactGallery({ artifacts }: { artifacts: Artifact[] }) {
  const media = artifacts.filter(
    (a) =>
      a.kind === "playwright" ||
      a.name.endsWith(".png") ||
      a.name.endsWith(".webm") ||
      a.name.endsWith(".zip"),
  );
  if (!media.length) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Artifact gallery</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        {media.map((a) => {
          const href = api.artifactContentUrl(a.id);
          const isImage = a.name.endsWith(".png") || a.content.endsWith(".png");
          return (
            <a
              key={a.id}
              href={href}
              target="_blank"
              rel="noreferrer"
              className="rounded-xl border border-black/5 bg-[#f7f7f8] p-3 text-xs hover:bg-white"
            >
              <div className="mb-2 font-medium">{a.name}</div>
              <div className="text-muted-foreground">{a.kind}</div>
              {isImage && (
                <img
                  src={href}
                  alt={a.name}
                  className="mt-2 max-h-40 w-full rounded-lg object-contain"
                />
              )}
            </a>
          );
        })}
      </CardContent>
    </Card>
  );
}

function Transcript({
  runId,
  runStatus,
}: {
  runId: string;
  runStatus: WorkflowRun["status"];
}) {
  const events = useRunEvents(runId);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Run transcript</CardTitle>
      </CardHeader>
      <CardContent className="max-h-96 overflow-auto pe-1">
        <RunTimeline events={events.data ?? []} runStatus={runStatus} />
      </CardContent>
    </Card>
  );
}

function HitlPanel({ runId }: { runId: string }) {
  const comments = useRunComments(runId);
  const [body, setBody] = useState("");
  const [pending, setPending] = useState(false);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4" /> Human-in-the-loop
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="max-h-40 space-y-2 overflow-auto">
          {(comments.data ?? []).map((c) => (
            <div key={c.id} className="rounded-lg bg-[#f7f7f8] px-3 py-2 text-xs">
              <div className="text-muted-foreground">
                {c.author} · {c.kind}
              </div>
              <div className="mt-1 whitespace-pre-wrap">{c.body}</div>
            </div>
          ))}
        </div>
        <Textarea
          rows={3}
          placeholder="Comment or steer guidance…"
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={!body || pending}
            onClick={async () => {
              setPending(true);
              try {
                await api.addRunComment(runId, body);
                setBody("");
                await comments.refetch();
              } finally {
                setPending(false);
              }
            }}
          >
            <Send className="h-4 w-4" /> Comment
          </Button>
          <Button
            size="sm"
            disabled={!body || pending}
            onClick={async () => {
              setPending(true);
              try {
                await api.steerRun(runId, body);
                setBody("");
                await comments.refetch();
              } finally {
                setPending(false);
              }
            }}
          >
            Steer develop
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function RunView({
  run,
  onApprove,
  approving,
  onCancel,
  cancelling,
}: {
  run: WorkflowRun;
  onApprove: () => void;
  approving: boolean;
  onCancel: () => void;
  cancelling: boolean;
}) {
  const report = run.artifacts.find((a) => a.kind === "report");
  const active = run.status === "pending" || run.status === "running";
  const stoppable =
    run.status === "pending" ||
    run.status === "running" ||
    run.status === "awaiting_approval";
  const sandbox = run.stages.find((s) => s.name === "sandbox_qa");
  const desktop = sandbox?.output_payload?.desktop_session as
    | { status?: string; instructions?: string[] }
    | undefined;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold">Run {run.workflow_version}</h2>
        <StatusBadge value={run.status} />
        <span className="text-sm text-muted-foreground">{run.total_tokens} tokens</span>
        {run.risk_level && <StatusBadge value={run.risk_level} />}
        {typeof run.develop_iterations === "number" && run.develop_iterations > 0 && (
          <span className="text-xs text-muted-foreground">
            develop retries: {run.develop_iterations}
          </span>
        )}
        {stoppable && (
          <Button
            variant="outline"
            size="sm"
            className="ms-auto"
            disabled={cancelling}
            onClick={onCancel}
          >
            {cancelling ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Square className="h-3.5 w-3.5 fill-current" />
            )}
            Stop run
          </Button>
        )}
      </div>
      {run.status === "awaiting_approval" && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
            <p className="text-sm">High-risk change paused at the human approval gate.</p>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={onCancel} disabled={cancelling || approving}>
                {cancelling ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Square className="h-3.5 w-3.5 fill-current" />
                )}
                Stop
              </Button>
              <Button onClick={onApprove} disabled={approving || cancelling}>
                {approving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Check className="h-4 w-4" />
                )}
                Approve & continue
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
      {run.status === "cancelled" && (
        <p className="rounded-xl border border-neutral-200 bg-[#f7f7f8] px-3 py-2 text-sm text-muted-foreground">
          Run was stopped. Remaining stages were skipped.
        </p>
      )}
      {run.worktree_path && (
        <p className="rounded-xl bg-[#f7f7f8] px-3 py-2 font-mono text-xs text-muted-foreground">
          worktree: {run.worktree_path}
        </p>
      )}
      {run.mr_url && (
        <a className="text-sm underline" href={run.mr_url} target="_blank" rel="noreferrer">
          Merge request / PR: {run.mr_url}
        </a>
      )}
      {desktop?.status === "ready" && (
        <Card>
          <CardHeader>
            <CardTitle>Desktop verification</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm text-muted-foreground">
            {(desktop.instructions ?? []).map((step) => (
              <p key={step}>• {step}</p>
            ))}
          </CardContent>
        </Card>
      )}
      {active && (
        <p className="text-xs text-muted-foreground">Run in progress… polling for updates.</p>
      )}
      <Transcript runId={run.id} runStatus={run.status} />
      <HitlPanel runId={run.id} />
      <ArtifactGallery artifacts={run.artifacts} />
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
  const task = useTask(taskId, 1500);
  const startRun = useStartRun(taskId);
  const approve = useApproveRun(taskId);
  const cancel = useCancelRun(taskId);

  if (task.isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (task.isError || !task.data) {
    return <p className="text-sm text-destructive">Task not found.</p>;
  }

  const latestRun = task.data.runs.at(-1);
  const runBusy =
    latestRun?.status === "pending" ||
    latestRun?.status === "running" ||
    latestRun?.status === "awaiting_approval";

  return (
    <div className="space-y-6">
      <Link
        to="/tasks"
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
            {task.data.require_approval && <StatusBadge value="awaiting_approval" />}
            {task.data.repo_url && (
              <span className="text-xs text-muted-foreground">{task.data.repo_url}</span>
            )}
          </div>
        </div>
        <Button onClick={() => startRun.mutate()} disabled={startRun.isPending || runBusy}>
          {startRun.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          Run workflow
        </Button>
      </div>

      {latestRun ? (
        <RunView
          run={latestRun}
          approving={approve.isPending}
          onApprove={() => approve.mutate(latestRun.id)}
          cancelling={cancel.isPending}
          onCancel={() => cancel.mutate(latestRun.id)}
        />
      ) : (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No runs yet.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
