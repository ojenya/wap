import { useState } from "react";

import { useCases, useRunEvals } from "@/api/hooks";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function LearningPage() {
  const cases = useCases();
  const runEvals = useRunEvals();
  const [evalResult, setEvalResult] = useState<{
    total: number;
    passed: number;
    failed: number;
  } | null>(null);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Learning & evals</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Validated case memory from successful runs, plus a regression eval harness for
            prompt/workflow changes.
          </p>
        </div>
        <Button
          onClick={async () => {
            const res = await runEvals.mutateAsync();
            setEvalResult({ total: res.total, passed: res.passed, failed: res.failed });
          }}
          disabled={runEvals.isPending}
        >
          Run eval suite
        </Button>
      </div>

      {evalResult && (
        <Card>
          <CardContent className="flex gap-4 py-4 text-sm">
            <StatusBadge value={evalResult.failed === 0 ? "completed" : "failed"} />
            <span>
              {evalResult.passed}/{evalResult.total} passed ({evalResult.failed} failed)
            </span>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Case memory</CardTitle>
          <CardDescription>Only lessons from approved/successful runs are stored.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {cases.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">No validated lessons yet.</p>
          )}
          {cases.data?.map((c) => (
            <div key={c.id} className="rounded-xl border px-3 py-3 text-sm">
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <span className="font-medium">{c.title}</span>
                <StatusBadge value={c.task_type} />
                {c.validated && <StatusBadge value="completed" />}
              </div>
              <p className="text-muted-foreground">{c.lesson}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
