// Shared domain contracts between the orchestrator API and the web UI.
// Mirrors the Pydantic schemas in apps/api/app/schemas.py.

export type RunStatus = "pending" | "running" | "completed" | "failed";
export type StageStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped";
export type RiskLevel = "low" | "medium" | "high";

export type TaskType = "bug_fix" | "feature" | "refactor" | "chore";

export interface Evidence {
  source: string;
  reference: string;
  reason?: string;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  repo_url: string;
  base_branch: string;
  task_type: string;
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
  created_at: string;
  finished_at: string | null;
  total_tokens: number;
  stages: StageExecution[];
  artifacts: Artifact[];
}

export interface TaskDetail extends Task {
  runs: WorkflowRun[];
}

export interface CreateTaskInput {
  title: string;
  description?: string;
  repo_url?: string;
  base_branch?: string;
  task_type?: string;
}
