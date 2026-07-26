import type {
  Automation,
  Artifact,
  CaseMemory,
  CreateRepositoryInput,
  CreateTaskInput,
  Environment,
  GitLabProject,
  Metrics,
  OAuthConnection,
  RemoteRepo,
  Repository,
  RunComment,
  RunEvent,
  Task,
  TaskDetail,
  VmCapabilities,
  VmInstance,
  WorkflowConfig,
  WorkflowRun,
} from "@wap/shared";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ? JSON.stringify(body.detail) : detail;
    } catch {
      // ignore
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  listTasks: () => request<Task[]>("/tasks"),
  getTask: (id: string) => request<TaskDetail>(`/tasks/${id}`),
  createTask: (input: CreateTaskInput) =>
    request<Task>("/tasks", { method: "POST", body: JSON.stringify(input) }),
  startRun: (taskId: string) =>
    request<WorkflowRun>(`/tasks/${taskId}/runs`, { method: "POST" }),
  getRun: (runId: string) => request<WorkflowRun>(`/runs/${runId}`),
  approveRun: (runId: string, note = "approved from UI") =>
    request<WorkflowRun>(`/runs/${runId}/approve`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  listRepositories: () => request<Repository[]>("/repositories"),
  createRepository: (input: CreateRepositoryInput) =>
    request<Repository>("/repositories", { method: "POST", body: JSON.stringify(input) }),
  syncRepository: (id: string) =>
    request<Repository>(`/repositories/${id}/sync`, { method: "POST" }),
  deleteRepository: (id: string) =>
    request<void>(`/repositories/${id}`, { method: "DELETE" }),
  gitlabOAuthUrl: () => request<{ url: string | null }>("/repositories/gitlab/oauth-url"),
  gitlabProjects: (token: string, search = "") =>
    request<GitLabProject[]>(
      `/repositories/gitlab/projects?token=${encodeURIComponent(token)}&search=${encodeURIComponent(search)}`,
    ),
  gitlabBranches: (token: string, projectId: number) =>
    request<string[]>(
      `/repositories/gitlab/projects/${projectId}/branches?token=${encodeURIComponent(token)}`,
    ),
  metrics: () => request<Metrics>("/metrics"),
  getWorkflowConfig: () => request<WorkflowConfig>("/workflow-config"),
  updateWorkflowConfig: (params: Record<string, unknown>) =>
    request<WorkflowConfig>("/workflow-config", {
      method: "PUT",
      body: JSON.stringify({ params }),
    }),
  listCases: () => request<CaseMemory[]>("/learning/cases"),
  runEvals: () =>
    request<{ total: number; passed: number; failed: number; results: unknown[] }>(
      "/learning/evals/run",
      { method: "POST" },
    ),
  listEnvironments: () => request<Environment[]>("/environments"),
  createEnvironment: (input: {
    name: string;
    update_script?: string;
    repository_id?: string;
    backend?: string;
  }) =>
    request<Environment>("/environments", { method: "POST", body: JSON.stringify(input) }),
  refreshEnvironment: (id: string) =>
    request<Environment>(`/environments/${id}/refresh`, { method: "POST" }),
  vmCapabilities: () => request<VmCapabilities>("/environments/capabilities"),
  bootVm: (envId: string, body: Record<string, unknown> = {}) =>
    request<VmInstance>(`/environments/${envId}/vms/boot`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  destroyVm: (envId: string, vmId: string) =>
    request<VmInstance>(`/environments/${envId}/vms/${vmId}/destroy`, { method: "POST" }),
  snapshotVm: (envId: string, vmId: string) =>
    request<VmInstance>(`/environments/${envId}/vms/${vmId}/snapshot`, { method: "POST" }),
  listVms: (envId: string) => request<VmInstance[]>(`/environments/${envId}/vms`),
  listAutomations: () => request<Automation[]>("/automations"),
  createAutomation: (input: Record<string, unknown>) =>
    request<Automation>("/automations", { method: "POST", body: JSON.stringify(input) }),
  triggerAutomation: (id: string) =>
    request<{ task_id: string; run_id: string | null }>(`/automations/${id}/trigger`, {
      method: "POST",
    }),
  listRunEvents: (runId: string) => request<RunEvent[]>(`/runs/${runId}/events`),
  listRunComments: (runId: string) => request<RunComment[]>(`/runs/${runId}/comments`),
  addRunComment: (runId: string, body: string) =>
    request<RunComment>(`/runs/${runId}/comments`, {
      method: "POST",
      body: JSON.stringify({ body, kind: "comment" }),
    }),
  steerRun: (runId: string, guidance: string) =>
    request<RunComment>(`/runs/${runId}/steer`, {
      method: "POST",
      body: JSON.stringify({ guidance }),
    }),
  listRunArtifacts: (runId: string) => request<Artifact[]>(`/runs/${runId}/artifacts`),
  artifactContentUrl: (artifactId: string) => `${BASE}/artifacts/${artifactId}/content`,
  oauthProviders: () =>
    request<Record<string, { configured: boolean; redirect_uri: string }>>("/oauth/providers"),
  oauthStart: (provider: string) =>
    request<{ url: string; state: string; provider: string }>(`/oauth/${provider}/start`),
  oauthCallback: (provider: string, body: { code: string; state: string }) =>
    request<OAuthConnection>(`/oauth/${provider}/callback`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listOAuthConnections: () => request<OAuthConnection[]>("/oauth/connections"),
  deleteOAuthConnection: (id: string) =>
    request<void>(`/oauth/connections/${id}`, { method: "DELETE" }),
  listOAuthRepos: (connectionId: string, search = "") =>
    request<RemoteRepo[]>(
      `/oauth/connections/${connectionId}/repos?search=${encodeURIComponent(search)}`,
    ),
  connectOAuthRepo: (
    connectionId: string,
    body: {
      external_id: string;
      name: string;
      clone_url: string;
      default_branch?: string;
      path_filters?: string[];
    },
  ) =>
    request<Repository>(`/oauth/connections/${connectionId}/repositories`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
