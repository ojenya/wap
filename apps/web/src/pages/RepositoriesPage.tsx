import { yupResolver } from "@hookform/resolvers/yup";
import type { OAuthConnection, RemoteRepo } from "@wap/shared";
import { Github, Loader2, RefreshCw, Trash2, Unplug } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useSearchParams } from "react-router-dom";
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
  const [searchParams, setSearchParams] = useSearchParams();

  const [providers, setProviders] = useState<Record<string, { configured: boolean }> | null>(
    null,
  );
  const [connections, setConnections] = useState<OAuthConnection[]>([]);
  const [activeConnectionId, setActiveConnectionId] = useState<string | null>(null);
  const [remoteRepos, setRemoteRepos] = useState<RemoteRepo[]>([]);
  const [repoSearch, setRepoSearch] = useState("");
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [oauthBusy, setOauthBusy] = useState<string | null>(null);
  const [oauthError, setOauthError] = useState<string | null>(null);
  const [oauthMsg, setOauthMsg] = useState<string | null>(null);
  const [showManual, setShowManual] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
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

  const refreshConnections = useCallback(async () => {
    const list = await api.listOAuthConnections();
    setConnections(list);
    if (!activeConnectionId && list[0]) {
      setActiveConnectionId(list[0].id);
    }
  }, [activeConnectionId]);

  useEffect(() => {
    api.oauthProviders().then(setProviders).catch(() => setProviders(null));
    refreshConnections().catch(() => undefined);
  }, [refreshConnections]);

  // Handle ?oauth=gitlab|github&code=...&state=... from provider redirect.
  useEffect(() => {
    const provider = searchParams.get("oauth");
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const error = searchParams.get("error");
    const connected = searchParams.get("connected");
    if (!provider) return;

    if (error) {
      setOauthError(error);
      setSearchParams({}, { replace: true });
      return;
    }
    if (connected === "1") {
      setOauthMsg(`${provider} connected`);
      refreshConnections().catch(() => undefined);
      setSearchParams({}, { replace: true });
      return;
    }
    if (code && state) {
      setOauthBusy(provider);
      api
        .oauthCallback(provider, { code, state })
        .then(async (conn) => {
          setOauthMsg(`Connected as ${conn.account_login}`);
          await refreshConnections();
          setActiveConnectionId(conn.id);
        })
        .catch((e: Error) => setOauthError(e.message))
        .finally(() => {
          setOauthBusy(null);
          setSearchParams({}, { replace: true });
        });
    }
  }, [searchParams, setSearchParams, refreshConnections]);

  useEffect(() => {
    if (!activeConnectionId) {
      setRemoteRepos([]);
      return;
    }
    setLoadingRepos(true);
    api
      .listOAuthRepos(activeConnectionId, repoSearch)
      .then(setRemoteRepos)
      .catch((e: Error) => setOauthError(e.message))
      .finally(() => setLoadingRepos(false));
  }, [activeConnectionId, repoSearch]);

  const startOAuth = async (provider: "gitlab" | "github") => {
    setOauthError(null);
    setOauthBusy(provider);
    try {
      const { url } = await api.oauthStart(provider);
      window.location.href = url;
    } catch (e) {
      setOauthError(e instanceof Error ? e.message : "OAuth start failed");
      setOauthBusy(null);
    }
  };

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

  const active = connections.find((c) => c.id === activeConnectionId) ?? null;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Repositories</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Connect GitLab / GitHub via OAuth — no PAT pasting. Tokens stay encrypted server-side.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Connect account</CardTitle>
          <CardDescription>
            Sign in once; then pick repositories from the list. Configure OAuth apps and set
            client id/secret in the API env.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() => startOAuth("gitlab")}
              disabled={oauthBusy !== null || providers?.gitlab?.configured === false}
            >
              {oauthBusy === "gitlab" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <span className="font-semibold">GL</span>
              )}
              Connect GitLab
            </Button>
            <Button
              variant="outline"
              onClick={() => startOAuth("github")}
              disabled={oauthBusy !== null || providers?.github?.configured === false}
            >
              {oauthBusy === "github" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Github className="h-4 w-4" />
              )}
              Connect GitHub
            </Button>
          </div>
          {providers && (
            <p className="text-xs text-muted-foreground">
              GitLab OAuth: {providers.gitlab?.configured ? "configured" : "missing env"} · GitHub
              OAuth: {providers.github?.configured ? "configured" : "missing env"}
            </p>
          )}
          {oauthError && <p className="text-xs text-destructive">{oauthError}</p>}
          {oauthMsg && <p className="text-xs text-emerald-700">{oauthMsg}</p>}

          {connections.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {connections.map((c) => (
                <div key={c.id} className="flex items-center gap-1">
                  <Button
                    size="sm"
                    variant={c.id === activeConnectionId ? "default" : "outline"}
                    onClick={() => setActiveConnectionId(c.id)}
                  >
                    {c.provider}: @{c.account_login}
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    title="Disconnect"
                    onClick={async () => {
                      await api.deleteOAuthConnection(c.id);
                      await refreshConnections();
                      if (activeConnectionId === c.id) setActiveConnectionId(null);
                    }}
                  >
                    <Unplug className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {active && (
        <Card>
          <CardHeader>
            <CardTitle>
              Repositories for @{active.account_login}
            </CardTitle>
            <CardDescription>Click a repo to connect it to the Change Factory.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              className="max-w-sm"
              placeholder="Filter…"
              value={repoSearch}
              onChange={(e) => setRepoSearch(e.target.value)}
            />
            {loadingRepos && (
              <p className="text-sm text-muted-foreground">
                <Loader2 className="mr-2 inline h-4 w-4 animate-spin" /> Loading…
              </p>
            )}
            <div className="max-h-72 space-y-2 overflow-auto">
              {remoteRepos.map((r) => (
                <button
                  key={`${r.provider}-${r.external_id}`}
                  type="button"
                  className="flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left text-sm hover:bg-black/[0.02]"
                  onClick={async () => {
                    setOauthBusy("connect");
                    try {
                      await api.connectOAuthRepo(active.id, {
                        external_id: r.external_id,
                        name: r.name,
                        clone_url: r.clone_url,
                        default_branch: r.default_branch,
                      });
                      await repos.refetch();
                      setOauthMsg(`Connected ${r.full_name}`);
                    } catch (e) {
                      setOauthError(e instanceof Error ? e.message : "Connect failed");
                    } finally {
                      setOauthBusy(null);
                    }
                  }}
                >
                  <span>{r.full_name}</span>
                  <span className="text-xs text-muted-foreground">{r.default_branch}</span>
                </button>
              ))}
              {!loadingRepos && remoteRepos.length === 0 && (
                <p className="text-sm text-muted-foreground">No repositories found.</p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Manual connect</CardTitle>
            <CardDescription>
              Fallback for bare git URLs or when OAuth apps are not configured yet.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!showManual ? (
              <Button variant="outline" onClick={() => setShowManual(true)}>
                Show manual form (PAT / URL)
              </Button>
            ) : (
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
                  <Label htmlFor="token">Access token (optional)</Label>
                  <Input id="token" type="password" {...register("token")} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="gitlab_project_id">GitLab project id</Label>
                  <Input id="gitlab_project_id" {...register("gitlab_project_id")} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="path_filters">Path filters</Label>
                  <Input
                    id="path_filters"
                    placeholder="apps/api, packages/shared"
                    {...register("path_filters")}
                  />
                </div>
                <Button type="submit" disabled={createRepo.isPending}>
                  {createRepo.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                  Connect repository
                </Button>
                {createRepo.isError && (
                  <p className="text-xs text-destructive">
                    {(createRepo.error as Error).message}
                  </p>
                )}
              </form>
            )}
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
