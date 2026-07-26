import { useEffect, useState } from "react";

import { useUpdateWorkflowConfig, useWorkflowConfig } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function SettingsPage() {
  const cfg = useWorkflowConfig();
  const update = useUpdateWorkflowConfig();
  const [json, setJson] = useState("");

  useEffect(() => {
    if (cfg.data) setJson(JSON.stringify(cfg.data.params, null, 2));
  }, [cfg.data]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Workflow settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Safe, versioned parameters only — not an arbitrary graph editor. Allowed keys:{" "}
          {(cfg.data?.allowed_keys ?? []).join(", ")}.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{cfg.data?.name ?? "default"}</CardTitle>
          <CardDescription>version {cfg.data?.version}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="params">Parameters (JSON)</Label>
            <textarea
              id="params"
              className="min-h-[360px] w-full rounded-xl border bg-white p-3 font-mono text-xs"
              value={json}
              onChange={(e) => setJson(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-3">
            <Button
              onClick={() => {
                const parsed = JSON.parse(json) as Record<string, unknown>;
                update.mutate(parsed);
              }}
              disabled={update.isPending}
            >
              Save safe params
            </Button>
            {update.isSuccess && <span className="text-xs text-emerald-700">Saved</span>}
            {update.isError && (
              <span className="text-xs text-destructive">{(update.error as Error).message}</span>
            )}
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <div>
              <Label>Quick: max develop iterations</Label>
              <Input
                type="number"
                min={1}
                max={5}
                defaultValue={Number(cfg.data?.params.max_develop_iterations ?? 3)}
                onBlur={(e) => {
                  if (!cfg.data) return;
                  update.mutate({
                    ...cfg.data.params,
                    max_develop_iterations: Number(e.target.value),
                  });
                }}
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
