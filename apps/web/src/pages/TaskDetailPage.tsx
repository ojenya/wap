import type { StageExecution, WorkflowRun } from "@wap/shared";
import { Link, useParams } from "react-router-dom";
import styled from "styled-components";

import { StatusBadge } from "../components/StatusBadge";
import { Button, Card, ErrorText, Muted } from "../components/ui";
import { useStartRun, useTask } from "../api/hooks";

const Back = styled(Link)`
  display: inline-block;
  margin-bottom: ${({ theme }) => theme.space(4)};
`;

const TopBar = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: ${({ theme }) => theme.space(4)};
  margin-bottom: ${({ theme }) => theme.space(6)};
`;

const Timeline = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.space(3)};
`;

const StageCard = styled(Card)`
  padding: ${({ theme }) => theme.space(4)};
`;

const StageHead = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: ${({ theme }) => theme.space(3)};
`;

const StageMeta = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.space(4)};
  color: ${({ theme }) => theme.colors.textMuted};
  font-size: 12.5px;
  margin-top: ${({ theme }) => theme.space(1)};
`;

const Pre = styled.pre`
  background: ${({ theme }) => theme.colors.bg};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: 8px;
  padding: ${({ theme }) => theme.space(3)};
  margin-top: ${({ theme }) => theme.space(3)};
  max-height: 260px;
  overflow: auto;
`;

const Index = styled.span`
  color: ${({ theme }) => theme.colors.textMuted};
  font-variant-numeric: tabular-nums;
  margin-right: ${({ theme }) => theme.space(2)};
`;

function StageItem({ stage }: { stage: StageExecution }) {
  return (
    <StageCard>
      <StageHead>
        <div>
          <strong>
            <Index>{String(stage.order_index + 1).padStart(2, "0")}</Index>
            {stage.name}
          </strong>
          <StageMeta>
            <span>{stage.agent_role}</span>
            <span>{stage.tokens} tokens</span>
            <span>{stage.duration_ms.toFixed(1)} ms</span>
            <span>{stage.evidence.length} evidence</span>
          </StageMeta>
        </div>
        <StatusBadge value={stage.status} />
      </StageHead>
      {Object.keys(stage.output_payload).length > 0 && (
        <Pre>{JSON.stringify(stage.output_payload, null, 2)}</Pre>
      )}
      {stage.error && <ErrorText>{stage.error}</ErrorText>}
    </StageCard>
  );
}

function RunView({ run }: { run: WorkflowRun }) {
  const report = run.artifacts.find((a) => a.kind === "report");
  return (
    <div>
      <TopBar>
        <div>
          <h3 style={{ margin: 0 }}>
            Run {run.workflow_version} <StatusBadge value={run.status} />
          </h3>
          <StageMeta>
            <span>{run.total_tokens} total tokens</span>
            {run.risk_level && (
              <span>
                risk: <StatusBadge value={run.risk_level} />
              </span>
            )}
          </StageMeta>
        </div>
      </TopBar>

      <Timeline>
        {run.stages.map((s) => (
          <StageItem key={s.id} stage={s} />
        ))}
      </Timeline>

      {report && (
        <>
          <h3 style={{ marginTop: 24 }}>Final report</h3>
          <Card>
            <Pre style={{ maxHeight: "none", marginTop: 0 }}>{report.content}</Pre>
          </Card>
        </>
      )}
    </div>
  );
}

export function TaskDetailPage() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  const startRun = useStartRun(taskId);

  if (task.isLoading) return <Muted>Loading...</Muted>;
  if (task.isError || !task.data) return <ErrorText>Task not found.</ErrorText>;

  const latestRun = task.data.runs.at(-1);

  return (
    <div>
      <Back to="/">← Back to tasks</Back>
      <TopBar>
        <div>
          <h2 style={{ marginBottom: 4 }}>{task.data.title}</h2>
          <Muted>{task.data.description || "No description"}</Muted>
        </div>
        <Button
          $variant="primary"
          onClick={() => startRun.mutate()}
          disabled={startRun.isPending}
        >
          {startRun.isPending ? "Running workflow..." : "Run workflow"}
        </Button>
      </TopBar>

      {startRun.isError && <ErrorText>{(startRun.error as Error).message}</ErrorText>}

      {latestRun ? (
        <RunView run={latestRun} />
      ) : (
        <Muted>No runs yet. Click “Run workflow” to execute the multi-agent lifecycle.</Muted>
      )}
    </div>
  );
}
