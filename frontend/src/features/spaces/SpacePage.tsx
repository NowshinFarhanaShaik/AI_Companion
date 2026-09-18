import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useCreateProject, useProjects, useSpace } from "../../api/workspace";
import { EmptyState } from "../../components/shared/EmptyState";
import { ErrorState } from "../../components/shared/ErrorState";
import { PageHeader } from "../../components/shared/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Spinner } from "../../components/ui/Spinner";
import { Textarea } from "../../components/ui/Textarea";
import { SpaceDashboardSummary } from "./SpaceDashboardSummary";

function NewProjectForm({ spaceId, onCancel }: { spaceId: string; onCancel: () => void }) {
  const createProject = useCreateProject(spaceId);
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [goal, setGoal] = useState("");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    createProject.mutate(
      { name, description, learning_goal: goal },
      { onSuccess: (project) => navigate(`/projects/${project.id}`) },
    );
  }

  return (
    <Card title="New Project" className="mb-6">
      <form onSubmit={onSubmit} className="space-y-3">
        <Input
          label="Name"
          required
          maxLength={160}
          placeholder="e.g. Neural Networks basics"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Textarea
          label="Description"
          required
          placeholder="What does this Project cover?"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <Textarea
          label="Learning goal"
          required
          placeholder="What do you want to be able to do? The Tutor uses this."
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
        />
        {createProject.error && (
          <p role="alert" className="text-sm text-red-600">
            {createProject.error.message}
          </p>
        )}
        <div className="flex gap-2">
          <Button type="submit" loading={createProject.isPending}>
            Create Project
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}

export function SpacePage() {
  const { spaceId = "" } = useParams();
  const space = useSpace(spaceId);
  const projects = useProjects(spaceId);
  const [creating, setCreating] = useState(false);

  if (space.isLoading) return <Spinner className="mx-auto mt-10" />;
  if (space.error) return <ErrorState error={space.error} onRetry={() => space.refetch()} />;

  return (
    <>
      <p className="mb-2 text-sm">
        <Link to="/spaces" className="text-indigo-600 hover:underline">
          ← All Spaces
        </Link>
      </p>
      <PageHeader
        title={space.data?.name ?? ""}
        subtitle={space.data?.description}
        actions={!creating && <Button onClick={() => setCreating(true)}>New Project</Button>}
      />
      <SpaceDashboardSummary spaceId={spaceId} />
      {creating && <NewProjectForm spaceId={spaceId} onCancel={() => setCreating(false)} />}
      {projects.isLoading && <Spinner className="mx-auto mt-10" />}
      {projects.error && <ErrorState error={projects.error} onRetry={() => projects.refetch()} />}
      {projects.data?.items.length === 0 && !creating && (
        <EmptyState
          title="No Projects in this Space"
          description="A Project is one focused learning journey with its own materials, Tutor and quizzes."
          action={<Button onClick={() => setCreating(true)}>Create a Project</Button>}
        />
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {projects.data?.items.map((project) => (
          <Link
            key={project.id}
            to={`/projects/${project.id}`}
            className="block rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          >
            <Card className="h-full transition hover:border-indigo-300">
              <h2 className="font-semibold text-slate-900">{project.name}</h2>
              <p className="mt-1 line-clamp-2 text-sm text-slate-600">{project.description}</p>
              <p className="mt-3 text-xs text-slate-500">Goal: {project.learning_goal}</p>
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}
