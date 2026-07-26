import type {
  CreateRepositoryInput,
  CreateTaskInput,
  Repository,
  Task,
  TaskDetail,
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
      // non-JSON error body
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
  listWorkflows: () => request<Record<string, string[]>>("/workflows"),
  listRepositories: () => request<Repository[]>("/repositories"),
  createRepository: (input: CreateRepositoryInput) =>
    request<Repository>("/repositories", { method: "POST", body: JSON.stringify(input) }),
  syncRepository: (id: string) =>
    request<Repository>(`/repositories/${id}/sync`, { method: "POST" }),
  deleteRepository: (id: string) =>
    request<void>(`/repositories/${id}`, { method: "DELETE" }),
};
