export type RunStatus =
  | "pending"
  | "running"
  | "awaiting_approval"
  | "completed"
  | "failed";
export type StageStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped";
export type RiskLevel = "low" | "medium" | "high";
export type RepoStatus = "pending" | "ready" | "error";
export type RepoProvider = "gitlab" | "github" | "git";

export interface Evidence {
  source: string;
  reference: string;
  reason?: string;
}

export interface Repository {
  id: string;
  name: string;
  url: string;
  provider: RepoProvider | string;
  default_branch: string;
  status: RepoStatus | string;
  last_error: string | null;
  last_synced_at: string | null;
  head_sha: string | null;
  created_at: string;
  has_token: boolean;
  gitlab_project_id: number | null;
  path_filters: string[];
}

export interface CreateRepositoryInput {
  name: string;
  url: string;
  default_branch?: string;
  token?: string;
  provider?: string;
  gitlab_project_id?: number | null;
  path_filters?: string[];
}

export interface GitLabProject {
  id: number;
  name: string;
  path_with_namespace: string;
  http_url_to_repo: string;
  default_branch: string;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  repository_id: string | null;
  repo_url: string;
  base_branch: string;
  task_type: string;
  path_filters: string[];
  require_approval: boolean;
  created_at: string;
}

export interface StageExecution {
  id: string;
  order_index: number;
  name: string;
  agent_role: string;
  status: StageStatus;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown>;
  evidence: Evidence[];
  tokens: number;
  duration_ms: number;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface Artifact {
  id: string;
  kind: string;
  name: string;
  content: string;
  created_at: string;
}

export interface WorkflowRun {
  id: string;
  task_id: string;
  workflow_version: string;
  status: RunStatus;
  risk_level: RiskLevel | null;
  worktree_path?: string | null;
  develop_iterations?: number;
  approved_by?: string | null;
  mr_url?: string | null;
  created_at: string;
  finished_at: string | null;
  total_tokens: number;
  total_duration_ms?: number;
  stages: StageExecution[];
  artifacts: Artifact[];
}

export interface TaskDetail extends Task {
  runs: WorkflowRun[];
}

export interface CreateTaskInput {
  title: string;
  description?: string;
  repository_id?: string | null;
  repo_url?: string;
  base_branch?: string;
  task_type?: string;
  path_filters?: string[];
  require_approval?: boolean;
}

export interface WorkflowConfig {
  name: string;
  version: string;
  params: Record<string, unknown>;
  updated_at: string | null;
  allowed_keys: string[];
}

export interface Metrics {
  runs_total: number;
  runs_completed: number;
  runs_failed: number;
  runs_awaiting_approval: number;
  avg_tokens: number;
  avg_duration_ms: number;
  total_tokens: number;
  stage_avg_ms: Record<string, number>;
  recent_runs: WorkflowRun[];
}

export interface CaseMemory {
  id: string;
  task_type: string;
  title: string;
  lesson: string;
  validated: boolean;
  run_id: string | null;
  repository_id: string | null;
  created_at: string;
}
