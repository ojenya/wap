import { yupResolver } from "@hookform/resolvers/yup";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import styled from "styled-components";
import * as yup from "yup";

import { StatusBadge } from "../components/StatusBadge";
import {
  Button,
  Card,
  ErrorText,
  Field,
  Input,
  Label,
  Muted,
  Textarea,
} from "../components/ui";
import { useCreateTask, useTasks } from "../api/hooks";

const Grid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: ${({ theme }) => theme.space(6)};
  align-items: start;
  @media (max-width: 820px) {
    grid-template-columns: 1fr;
  }
`;

const TaskRow = styled(Link)`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: ${({ theme }) => theme.space(3)} ${({ theme }) => theme.space(4)};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: 8px;
  color: ${({ theme }) => theme.colors.text};
  margin-bottom: ${({ theme }) => theme.space(2)};
  &:hover {
    border-color: ${({ theme }) => theme.colors.accent};
  }
`;

const schema = yup.object({
  title: yup.string().required("Title is required").min(3, "At least 3 characters"),
  description: yup.string().default(""),
  repo_url: yup.string().url("Must be a valid URL").default("").transform((v) => v || ""),
  task_type: yup.string().default("bug_fix"),
});

const TASK_TYPES = ["bug_fix", "feature", "refactor", "chore"];

type TaskFormValues = yup.InferType<typeof schema>;

export function TasksPage() {
  const tasks = useTasks();
  const createTask = useCreateTask();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<TaskFormValues>({
    resolver: yupResolver(schema),
    defaultValues: { title: "", description: "", repo_url: "", task_type: "bug_fix" },
  });

  const onSubmit = handleSubmit(async (values) => {
    await createTask.mutateAsync(values);
    reset();
  });

  return (
    <Grid>
      <div>
        <h2>New task</h2>
        <Card as="form" onSubmit={onSubmit}>
          <Field>
            <Label htmlFor="title">Title</Label>
            <Input id="title" placeholder="Add logout button to navbar" {...register("title")} />
            {errors.title && <ErrorText>{errors.title.message}</ErrorText>}
          </Field>
          <Field>
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              placeholder="What should change and why"
              {...register("description")}
            />
          </Field>
          <Field>
            <Label htmlFor="repo_url">Repository URL</Label>
            <Input id="repo_url" placeholder="https://gitlab.com/org/repo" {...register("repo_url")} />
            {errors.repo_url && <ErrorText>{errors.repo_url.message}</ErrorText>}
          </Field>
          <Field>
            <Label htmlFor="task_type">Type</Label>
            <Input as="select" id="task_type" {...register("task_type")}>
              {TASK_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Input>
          </Field>
          <Button type="submit" $variant="primary" disabled={createTask.isPending}>
            {createTask.isPending ? "Creating..." : "Create task"}
          </Button>
          {createTask.isError && (
            <ErrorText style={{ display: "block", marginTop: 8 }}>
              {(createTask.error as Error).message}
            </ErrorText>
          )}
        </Card>
      </div>

      <div>
        <h2>Tasks</h2>
        {tasks.isLoading && <Muted>Loading...</Muted>}
        {tasks.isError && <ErrorText>Failed to load tasks. Is the API running?</ErrorText>}
        {tasks.data?.length === 0 && <Muted>No tasks yet. Create one to run the workflow.</Muted>}
        {tasks.data?.map((task) => (
          <TaskRow key={task.id} to={`/tasks/${task.id}`}>
            <span>{task.title}</span>
            <StatusBadge value={task.task_type} />
          </TaskRow>
        ))}
      </div>
    </Grid>
  );
}
