import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useCreateSpace, useSpaces } from "../../api/workspace";
import { EmptyState } from "../../components/shared/EmptyState";
import { ErrorState } from "../../components/shared/ErrorState";
import { PageHeader } from "../../components/shared/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Spinner } from "../../components/ui/Spinner";
import { Textarea } from "../../components/ui/Textarea";

function NewSpaceForm({ onDone }: { onDone: () => void }) {
  const createSpace = useCreateSpace();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    createSpace.mutate({ name, description }, { onSuccess: onDone });
  }

  return (
    <Card title="New Space" className="mb-6">
      <form onSubmit={onSubmit} className="space-y-3">
        <Input
          label="Name"
          required
          maxLength={120}
          placeholder="e.g. Machine Learning"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Textarea
          label="Description"
          required
          placeholder="What broad area is this Space for?"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        {createSpace.error && (
          <p role="alert" className="text-sm text-red-600">
            {createSpace.error.message}
          </p>
        )}
        <div className="flex gap-2">
          <Button type="submit" loading={createSpace.isPending}>
            Create Space
          </Button>
          <Button type="button" variant="ghost" onClick={onDone}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}

export function SpacesPage() {
  const spaces = useSpaces();
  const [creating, setCreating] = useState(false);

  return (
    <>
      <PageHeader
        title="Your Spaces"
        subtitle="A Space is a broad area you want to learn. Projects inside it hold your materials, Tutor and quizzes."
        actions={!creating && <Button onClick={() => setCreating(true)}>New Space</Button>}
      />
      {creating && <NewSpaceForm onDone={() => setCreating(false)} />}
      {spaces.isLoading && <Spinner className="mx-auto mt-10" />}
      {spaces.error && <ErrorState error={spaces.error} onRetry={() => spaces.refetch()} />}
      {spaces.data?.items.length === 0 && !creating && (
        <EmptyState
          title="No Spaces yet"
          description="Create your first Space to start a learning journey."
          action={<Button onClick={() => setCreating(true)}>Create a Space</Button>}
        />
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {spaces.data?.items.map((space) => (
          <Link
            key={space.id}
            to={`/spaces/${space.id}`}
            className="block rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          >
            <Card className="h-full transition hover:border-indigo-300">
              <h2 className="font-semibold text-slate-900">{space.name}</h2>
              <p className="mt-1 line-clamp-2 text-sm text-slate-600">{space.description}</p>
              <p className="mt-3 text-xs text-slate-500">
                {space.project_count} {space.project_count === 1 ? "project" : "projects"}
              </p>
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}
