import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import type { CreateTaskInput } from "@wap/shared";

import { api } from "./client";

export const taskKeys = {
  all: ["tasks"] as const,
  detail: (id: string) => ["tasks", id] as const,
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

export function useWorkflows() {
  return useQuery({ queryKey: ["workflows"], queryFn: api.listWorkflows });
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
