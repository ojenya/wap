import { yupResolver } from "@hookform/resolvers/yup";
import type { GitLabProject } from "@wap/shared";
import { Loader2, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import * as yup from "yup";

import { api } from "@/api/client";
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
  name: yup.string().required().min(1),
  url: yup.string().required().min(8),
  default_branch: yup.string().default("main"),
  token: yup.string().default(""),
  path_filters: yup.string().default(""),
  gitlab_project_id: yup.string().default(""),
});

type FormValues = yup.InferType<typeof schema>;

export function RepositoriesPage() {
  const repos = useRepositories();
  const createRepo = useCreateRepository();
  const syncRepo = useSyncRepository();
  const deleteRepo = useDeleteRepository();

  const [gitlabToken, setGitlabToken] = useState("");
  const [gitlabSearch, setGitlabSearch] = useState("");
  const [projects, setProjects] = useState<GitLabProject[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [oauthUrl, setOauthUrl] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: yupResolver(schema),
    defaultValues: {
      name: "",
      url: "",
      default_branch: "main",
      token: "",
      path_filters: "",
      gitlab_project_id: "",
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    const filters = values.path_filters
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    await createRepo.mutateAsync({
      name: values.name,
      url: values.url,
      default_branch: values.default_branch,
      token: values.token,
      path_filters: filters,
      gitlab_project_id: values.gitlab_project_id
        ? Number(values.gitlab_project_id)
        : null,
    });
    reset();
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Repositories</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Connect GitLab / GitHub / git. Tokens are encrypted and only decrypted for clone/push with
          an audit log.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Browse GitLab projects</CardTitle>
          <CardDescription>
            Paste a PAT (or complete OAuth if configured), pick a project, and we prefill the form.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Input
              className="max-w-sm"
              type="password"
              placeholder="glpat-… / OAuth access token"
              value={gitlabToken}
              onChange={(e) => setGitlabToken(e.target.value)}
            />
            <Input
              className="max-w-[180px]"
              placeholder="Search"
              value={gitlabSearch}
              onChange={(e) => setGitlabSearch(e.target.value)}
            />
            <Button
              variant="outline"
              disabled={!gitlabToken || loadingProjects}
              onClick={async () => {
                setLoadingProjects(true);
                try {
                  setProjects(await api.gitlabProjects(gitlabToken, gitlabSearch));
                } finally {
                  setLoadingProjects(false);
                }
              }}
            >
              {loadingProjects ? <Loader2 className="h-4 w-4 animate-spin" /> : "List projects"}
            </Button>
            <Button
              variant="ghost"
              onClick={async () => {
                const res = await api.gitlabOAuthUrl();
                setOauthUrl(res.url);
              }}
            >
              Get OAuth URL
            </Button>
          </div>
          {oauthUrl && (
            <a className="text-sm underline" href={oauthUrl} target="_blank" rel="noreferrer">
              Open GitLab OAuth
            </a>
          )}
          <div className="max-h-48 space-y-2 overflow-auto">
            {projects.map((p) => (
              <button
                key={p.id}
                type="button"
                className="flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left text-sm hover:bg-black/[0.02]"
                onClick={() => {
                  setValue("name", p.name);
                  setValue("url", p.http_url_to_repo);
                  setValue("default_branch", p.default_branch);
                  setValue("gitlab_project_id", String(p.id));
                  setValue("token", gitlabToken);
                }}
              >
                <span>{p.path_with_namespace}</span>
                <span className="text-xs text-muted-foreground">#{p.id}</span>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Add repository</CardTitle>
            <CardDescription>URL + optional token / GitLab project id / path filters.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={onSubmit}>
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input id="name" {...register("name")} />
                {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="url">Git URL</Label>
                <Input id="url" {...register("url")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="default_branch">Default branch</Label>
                <Input id="default_branch" {...register("default_branch")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="token">Access token</Label>
                <Input id="token" type="password" {...register("token")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="gitlab_project_id">GitLab project id (for MR)</Label>
                <Input id="gitlab_project_id" {...register("gitlab_project_id")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="path_filters">Path filters</Label>
                <Input id="path_filters" placeholder="apps/api, packages/shared" {...register("path_filters")} />
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
          {repos.data?.map((repo) => (
            <Card key={repo.id}>
              <CardContent className="flex items-start justify-between gap-4 py-5">
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{repo.name}</span>
                    <StatusBadge value={repo.status} />
                    <StatusBadge value={String(repo.provider)} />
                  </div>
                  <p className="truncate text-sm text-muted-foreground">{repo.url}</p>
                  <p className="text-xs text-muted-foreground">
                    {repo.default_branch}
                    {repo.head_sha ? ` · ${repo.head_sha.slice(0, 8)}` : ""}
                    {repo.path_filters?.length
                      ? ` · scope: ${repo.path_filters.join(", ")}`
                      : ""}
                  </p>
                  {repo.last_error && (
                    <p className="text-xs text-destructive">{repo.last_error}</p>
                  )}
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button variant="outline" size="icon" onClick={() => syncRepo.mutate(repo.id)}>
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" size="icon" onClick={() => deleteRepo.mutate(repo.id)}>
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
