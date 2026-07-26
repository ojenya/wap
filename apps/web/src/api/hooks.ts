import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import type { CreateRepositoryInput, CreateTaskInput } from "@wap/shared";

import { api } from "./client";

export const taskKeys = {
  all: ["tasks"] as const,
  detail: (id: string) => ["tasks", id] as const,
};

export const repoKeys = {
  all: ["repositories"] as const,
};

export function useTasks() {
  return useQuery({ queryKey: taskKeys.all, queryFn: api.listTasks });
}

export function useTask(id: string) {
  return useQuery({
    queryKey: taskKeys.detail(id),
    queryFn: () => api.getTask(id),
  });
}

export function useRepositories() {
  return useQuery({ queryKey: repoKeys.all, queryFn: api.listRepositories });
}

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateTaskInput) => api.createTask(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: taskKeys.all }),
  });
}

export function useStartRun(taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.startRun(taskId),
    onSuccess: () => qc.invalidateQueries({ queryKey: taskKeys.detail(taskId) }),
  });
}

export function useCreateRepository() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateRepositoryInput) => api.createRepository(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: repoKeys.all }),
  });
}

export function useSyncRepository() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.syncRepository(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: repoKeys.all }),
  });
}

export function useDeleteRepository() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteRepository(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: repoKeys.all }),
  });
}
