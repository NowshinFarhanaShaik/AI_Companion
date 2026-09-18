import { useRef, useState, type DragEvent } from "react";
import { openProtectedFile } from "../../api/client";
import {
  isProcessing,
  useConcepts,
  useDeleteMaterial,
  useMaterials,
  useRetryMaterial,
  useUploadMaterial,
} from "../../api/materials";
import type { Material } from "../../api/types";
import { EmptyState } from "../../components/shared/EmptyState";
import { ErrorState } from "../../components/shared/ErrorState";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";
import { useProjectId } from "../projects/useProjectId";

const MAX_BYTES = 20 * 1024 * 1024;

function UploadZone({ projectId }: { projectId: string }) {
  const upload = useUploadMaterial(projectId);
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState("");

  function send(file: File | undefined) {
    if (!file) return;
    setLocalError("");
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setLocalError("Only PDF files are supported.");
    } else if (file.size > MAX_BYTES) {
      setLocalError("Files can be at most 20 MB.");
    } else {
      upload.mutate(file);
    }
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    send(event.dataTransfer.files[0]);
  }

  const error = localError || upload.error?.message;
  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={`mb-6 rounded-xl border-2 border-dashed p-8 text-center transition ${dragging ? "border-indigo-500 bg-indigo-50" : "border-slate-300 bg-white"}`}
    >
      <p className="font-medium text-slate-900">Drop a PDF here</p>
      <p className="mt-1 text-sm text-slate-600">
        Up to 20 MB and 200 pages. Processing continues even if you close this tab.
      </p>
      <input
        ref={input}
        type="file"
        accept="application/pdf"
        className="hidden"
        aria-label="Choose a PDF to upload"
        onChange={(event) => {
          send(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
      <Button className="mt-4" loading={upload.isPending} onClick={() => input.current?.click()}>
        Choose a PDF
      </Button>
      {error && (
        <p role="alert" className="mt-3 text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

function MaterialRow({ material, projectId }: { material: Material; projectId: string }) {
  const retry = useRetryMaterial(projectId);
  const remove = useDeleteMaterial(projectId);
  const [openError, setOpenError] = useState("");
  const error = openError || retry.error?.message || remove.error?.message;

  function confirmDelete() {
    const question = `Delete "${material.title}"? The Tutor will no longer use it.`;
    if (window.confirm(question)) remove.mutate(material.id);
  }

  return (
    <li className="flex flex-wrap items-start justify-between gap-3 py-4">
      <div className="min-w-0">
        <p className="flex items-center gap-2 font-medium text-slate-900">
          <span className="truncate">{material.title}</span>
          <StatusBadge status={material.status} />
          {isProcessing(material) && <Spinner size="sm" />}
        </p>
        <p className="mt-1 text-sm text-slate-600">
          {material.page_count} pages
          {material.status === "ready" && ` · ${material.chunk_count} searchable sections`}
        </p>
        {material.status === "failed" && <p className="mt-1 text-sm text-red-700">{material.error_message}</p>}
        {error && (
          <p role="alert" className="mt-1 text-sm text-red-600">
            {error}
          </p>
        )}
      </div>
      <div className="flex gap-2">
        {material.status === "failed" && (
          <Button size="sm" variant="secondary" loading={retry.isPending} onClick={() => retry.mutate(material.id)}>
            Retry
          </Button>
        )}
        <Button
          size="sm"
          variant="secondary"
          onClick={() => openProtectedFile(`/materials/${material.id}/file`).catch((err) => setOpenError(err.message))}
        >
          Open
        </Button>
        <Button size="sm" variant="ghost" loading={remove.isPending} onClick={confirmDelete}>
          Delete
        </Button>
      </div>
    </li>
  );
}

export function MaterialsPage() {
  const projectId = useProjectId();
  const materials = useMaterials(projectId);
  const items = materials.data?.items ?? [];
  const concepts = useConcepts(projectId, items.filter((material) => material.status === "ready").length);

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <UploadZone projectId={projectId} />
        {materials.isLoading && <Spinner className="mx-auto mt-10" />}
        {materials.error && <ErrorState error={materials.error} onRetry={() => materials.refetch()} />}
        {materials.data && items.length === 0 && (
          <EmptyState
            title="No materials yet"
            description="Upload your notes, slides or a textbook chapter. The Tutor answers from these and cites the page."
          />
        )}
        {items.length > 0 && (
          <Card title="Materials">
            <ul className="divide-y divide-slate-100">
              {items.map((material) => (
                <MaterialRow key={material.id} material={material} projectId={projectId} />
              ))}
            </ul>
          </Card>
        )}
      </div>
      <Card title="Concepts found">
        {concepts.isLoading && <Spinner />}
        {concepts.error && <ErrorState error={concepts.error} onRetry={() => concepts.refetch()} />}
        {concepts.data?.items.length === 0 && (
          <p className="text-sm text-slate-600">Concepts appear here once a material is ready.</p>
        )}
        <ul className="space-y-3">
          {concepts.data?.items.map((concept) => (
            <li key={concept.id}>
              <p className="flex items-center gap-2 text-sm font-medium text-slate-900">
                {concept.name}
                {concept.importance >= 4 && <Badge tone="blue">key</Badge>}
              </p>
              <p className="text-sm text-slate-600">{concept.description}</p>
              {concept.pages.length > 0 && <p className="text-xs text-slate-500">Pages {concept.pages.join(", ")}</p>}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
