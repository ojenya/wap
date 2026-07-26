import { Loader2, Zap } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useAutomations, useCreateAutomation, useTriggerAutomation } from "@/api/hooks";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type FormValues = {
  name: string;
  trigger_type: string;
  task_title_template: string;
};

export function AutomationsPage() {
  const list = useAutomations();
  const create = useCreateAutomation();
  const trigger = useTriggerAutomation();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<FormValues>({
    defaultValues: {
      name: "",
      trigger_type: "webhook",
      task_title_template: "Automation: {{name}}",
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Automations</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Webhook / cron / SCM triggers that mint tasks and start runs.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Create automation</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-3"
            onSubmit={form.handleSubmit(async (values) => {
              setError(null);
              try {
                await create.mutateAsync({
                  ...values,
                  auto_start: false,
                });
                form.reset();
              } catch (e) {
                setError(e instanceof Error ? e.message : "Failed");
              }
            })}
          >
            <div className="space-y-1.5">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...form.register("name", { required: true })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="trigger_type">Trigger</Label>
              <Input id="trigger_type" {...form.register("trigger_type")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="task_title_template">Title template</Label>
              <Input id="task_title_template" {...form.register("task_title_template")} />
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
            <Button type="submit" disabled={create.isPending}>
              {create.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Create
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="space-y-3">
        {(list.data ?? []).map((a) => (
          <Card key={a.id}>
            <CardContent className="flex flex-wrap items-start justify-between gap-3 py-4">
              <div>
                <div className="font-medium">{a.name}</div>
                <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <StatusBadge value={a.trigger_type} />
                  <StatusBadge value={a.enabled ? "ready" : "error"} />
                </div>
                <p className="mt-2 font-mono text-xs text-muted-foreground">
                  webhook: /api/automations/webhook/{a.webhook_token}
                </p>
              </div>
              <Button
                size="sm"
                onClick={() => trigger.mutate(a.id)}
                disabled={trigger.isPending}
              >
                <Zap className="h-4 w-4" />
                Trigger
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
