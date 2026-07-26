import { yupResolver } from "@hookform/resolvers/yup";
import { Loader2, RefreshCw, Trash2 } from "lucide-react";
import { useForm } from "react-hook-form";
import * as yup from "yup";

import {
  useCreateRepository,
  useDeleteRepository,
  useRepositories,
  useSyncRepository,
} from "@/api/hooks";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const schema = yup.object({
  name: yup.string().required("Name is required").min(1),
  url: yup.string().required("URL is required").min(8),
  default_branch: yup.string().default("main"),
  token: yup.string().default(""),
});

type FormValues = yup.InferType<typeof schema>;

export function RepositoriesPage() {
  const repos = useRepositories();
  const createRepo = useCreateRepository();
  const syncRepo = useSyncRepository();
  const deleteRepo = useDeleteRepository();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: yupResolver(schema),
    defaultValues: { name: "", url: "", default_branch: "main", token: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    await createRepo.mutateAsync(values);
    reset();
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Repositories</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Connect a GitLab, GitHub, or any git URL. Private repos need a personal / deploy token.
          Every run gets an isolated worktree.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Add repository</CardTitle>
            <CardDescription>URL + optional token. Provider is detected automatically.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={onSubmit}>
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input id="name" placeholder="payments-service" {...register("name")} />
                {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="url">Git URL</Label>
                <Input
                  id="url"
                  placeholder="https://gitlab.com/org/project.git"
                  {...register("url")}
                />
                {errors.url && <p className="text-xs text-destructive">{errors.url.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="default_branch">Default branch</Label>
                <Input id="default_branch" {...register("default_branch")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="token">Access token (optional)</Label>
                <Input
                  id="token"
                  type="password"
                  placeholder="glpat-… / ghp_…"
                  autoComplete="off"
                  {...register("token")}
                />
                <p className="text-xs text-muted-foreground">
                  Stored encrypted. Never shown back in the API.
                </p>
              </div>
              <Button type="submit" disabled={createRepo.isPending}>
                {createRepo.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Connect repository
              </Button>
              {createRepo.isError && (
                <p className="text-xs text-destructive">{(createRepo.error as Error).message}</p>
              )}
            </form>
          </CardContent>
        </Card>

        <div className="space-y-3">
          {repos.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {repos.data?.length === 0 && (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                No repositories yet. Connect one to run audit / develop workflows.
              </CardContent>
            </Card>
          )}
          {repos.data?.map((repo) => (
            <Card key={repo.id}>
              <CardContent className="flex items-start justify-between gap-4 py-5">
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{repo.name}</span>
                    <StatusBadge value={repo.status} />
                    <StatusBadge value={String(repo.provider)} />
                    {repo.has_token && <StatusBadge value="token" />}
                  </div>
                  <p className="truncate text-sm text-muted-foreground">{repo.url}</p>
                  <p className="text-xs text-muted-foreground">
                    branch {repo.default_branch}
                    {repo.head_sha ? ` · ${repo.head_sha.slice(0, 8)}` : ""}
                  </p>
                  {repo.last_error && (
                    <p className="text-xs text-destructive">{repo.last_error}</p>
                  )}
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button
                    variant="outline"
                    size="icon"
                    title="Sync"
                    onClick={() => syncRepo.mutate(repo.id)}
                    disabled={syncRepo.isPending}
                  >
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    title="Delete"
                    onClick={() => deleteRepo.mutate(repo.id)}
                    disabled={deleteRepo.isPending}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
