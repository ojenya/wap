import { yupResolver } from "@hookform/resolvers/yup";
import { Loader2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import * as yup from "yup";

import { useCreateTask, useRepositories, useTasks } from "@/api/hooks";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const schema = yup.object({
  title: yup.string().required("Title is required").min(3),
  description: yup.string().default(""),
  repository_id: yup.string().nullable().default(null),
  task_type: yup.string().default("feature"),
  path_filters: yup.string().default(""),
  require_approval: yup.boolean().default(true),
});

type FormValues = yup.InferType<typeof schema>;

const TASK_TYPES = [
  { value: "audit", label: "Audit (read-only)" },
  { value: "bug_fix", label: "Bug fix" },
  { value: "feature", label: "Feature" },
  { value: "refactor", label: "Refactor" },
  { value: "chore", label: "Chore" },
];

export function TasksPage() {
  const tasks = useTasks();
  const repos = useRepositories();
  const createTask = useCreateTask();

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: yupResolver(schema),
    defaultValues: {
      title: "",
      description: "",
      repository_id: null,
      task_type: "feature",
      path_filters: "",
      require_approval: true,
    },
  });

  const taskType = watch("task_type");
  const repositoryId = watch("repository_id");
  const requireApproval = watch("require_approval");

  const onSubmit = handleSubmit(async (values) => {
    const repo = repos.data?.find((r) => r.id === values.repository_id);
    const filters = values.path_filters
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    await createTask.mutateAsync({
      title: values.title,
      description: values.description,
      repository_id: values.repository_id || null,
      base_branch: repo?.default_branch ?? "main",
      task_type: values.task_type,
      path_filters: filters,
      require_approval: values.require_approval,
    });
    reset();
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Tasks</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Create an audit or develop task against a connected repository. High-risk runs pause for
          approval.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>New task</CardTitle>
            <CardDescription>Optional monorepo path filters: packages/api, apps/web</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={onSubmit}>
              <div className="space-y-2">
                <Label htmlFor="title">Title</Label>
                <Input id="title" placeholder="Add rate limiting to login" {...register("title")} />
                {errors.title && <p className="text-xs text-destructive">{errors.title.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea id="description" {...register("description")} />
              </div>
              <div className="space-y-2">
                <Label>Repository</Label>
                <Select
                  value={repositoryId ?? "none"}
                  onValueChange={(v) => setValue("repository_id", v === "none" ? null : v)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select repository" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No repository (synthetic)</SelectItem>
                    {repos.data?.map((r) => (
                      <SelectItem key={r.id} value={r.id}>
                        {r.name} ({r.status})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Type</Label>
                <Select value={taskType} onValueChange={(v) => setValue("task_type", v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {TASK_TYPES.map((t) => (
                      <SelectItem key={t.value} value={t.value}>
                        {t.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="path_filters">Path filters (comma-separated)</Label>
                <Input id="path_filters" placeholder="src/, apps/api" {...register("path_filters")} />
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={requireApproval}
                  onChange={(e) => setValue("require_approval", e.target.checked)}
                />
                Require human approval for high-risk changes
              </label>
              <Button type="submit" disabled={createTask.isPending}>
                {createTask.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Create task
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="space-y-3">
          {tasks.data?.map((task) => (
            <Link key={task.id} to={`/tasks/${task.id}`} className="block">
              <Card className="transition-colors hover:bg-black/[0.015]">
                <CardContent className="flex items-center justify-between gap-3 py-4">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{task.title}</div>
                    <div className="truncate text-xs text-muted-foreground">
                      {task.repo_url || "no repository"}
                    </div>
                  </div>
                  <StatusBadge value={task.task_type} />
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
