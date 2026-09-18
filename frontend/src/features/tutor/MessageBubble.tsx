import { useState } from "react";
import { openProtectedFile } from "../../api/client";
import type { Citation, TutorMessage } from "../../api/types";

function CitationChip({ citation }: { citation: Citation }) {
  const [error, setError] = useState("");

  function open() {
    setError("");
    openProtectedFile(`/materials/${citation.material_id}/file`, citation.page_number).catch((err) =>
      setError(err instanceof Error ? err.message : "Could not open the document."),
    );
  }

  return (
    <span className="inline-flex flex-col">
      <button
        type="button"
        onClick={open}
        title={citation.snippet}
        className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-800 hover:bg-indigo-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
      >
        Source: {citation.material_title} — Page {citation.page_number}
      </button>
      {error && (
        <span role="alert" className="mt-1 text-xs text-red-600">
          {error}
        </span>
      )}
    </span>
  );
}

export function MessageBubble({ message, pending = false }: { message: TutorMessage; pending?: boolean }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <p
          className={`max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2 text-sm text-white ${pending ? "opacity-70" : ""}`}
        >
          {message.content}
        </p>
      </div>
    );
  }

  if (message.grounded === false) {
    return (
      <div className="max-w-[80%] rounded-2xl rounded-bl-sm border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-700">Not in your materials</p>
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>
    );
  }

  return (
    <div className="max-w-[80%] rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900">
      <p className="whitespace-pre-wrap">{message.content}</p>
      {message.citations.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2 border-t border-slate-100 pt-3">
          {message.citations.map((citation) => (
            <CitationChip key={citation.id} citation={citation} />
          ))}
        </div>
      )}
    </div>
  );
}
