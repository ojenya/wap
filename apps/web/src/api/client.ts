import type {
  CaseMemory,
  CreateRepositoryInput,
  CreateTaskInput,
  GitLabProject,
  Metrics,
  Repository,
  Task,
  TaskDetail,
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
  approveRun: (runId: string) =>
    request<WorkflowRun>(`/runs/${runId}/approve`, {
      method: "POST",
      body: JSON.stringify({ note: "approved from UI" }),
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
};
