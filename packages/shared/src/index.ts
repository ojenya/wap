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

export interface Environment {
  id: string;
  name: string;
  repository_id: string | null;
  dockerfile_path: string;
  environment_json_path: string;
  update_script: string;
  agents_md_path: string;
  backend: string;
  vcpu_count: number;
  mem_size_mib: number;
  snapshot_id: string | null;
  status: string;
  last_refresh_log: string;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface VmInstance {
  id: string;
  environment_id: string;
  run_id: string | null;
  backend: string;
  status: string;
  work_dir: string;
  workspace_path: string;
  socket_path: string;
  pid: number | null;
  guest_ip: string | null;
  snapshot_path: string | null;
  rootfs_path: string | null;
  last_error: string | null;
  meta: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface VmCapabilities {
  kvm: boolean;
  firecracker_bin: string | null;
  kernel: string | null;
  rootfs: string | null;
  mode: string;
  can_boot_real: boolean;
  can_emulate: boolean;
  preferred_backend: string;
  reason: string;
}

export interface Automation {
  id: string;
  name: string;
  enabled: boolean;
  trigger_type: string;
  cron_expr: string;
  webhook_token: string;
  repository_id: string | null;
  task_title_template: string;
  task_description_template: string;
  task_type: string;
  auto_start: boolean;
  last_triggered_at: string | null;
  created_at: string;
}

export interface RunEvent {
  id: string;
  run_id: string;
  kind: string;
  stage_name: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface RunComment {
  id: string;
  run_id: string;
  author: string;
  body: string;
  kind: string;
  created_at: string;
}

export interface VaultSecretMeta {
  id: string;
  name: string;
  scope: string;
  environment_id: string | null;
  description: string;
  created_at: string;
  has_value: boolean;
}

export interface EgressPolicy {
  id: string;
  name: string;
  allow_all: boolean;
  allowed_domains: string[];
  environment_id: string | null;
}

export interface McpServer {
  id: string;
  name: string;
  transport: string;
  url: string;
  command: string;
  enabled: boolean;
  tools_cache: unknown[];
  created_at: string;
}

export interface OAuthConnection {
  id: string;
  provider: string;
  account_id: string;
  account_login: string;
  account_name: string;
  scopes: string;
  created_at: string;
  updated_at: string;
}

export interface RemoteRepo {
  external_id: string;
  name: string;
  full_name: string;
  clone_url: string;
  default_branch: string;
  provider: string;
}
