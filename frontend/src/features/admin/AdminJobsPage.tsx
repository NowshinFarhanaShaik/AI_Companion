import { useState } from "react";
import { useAdminJobs, useAdminJobsSummary, useRetryJob } from "../../api/admin";
import { ErrorState } from "../../components/shared/ErrorState";
import { Pager } from "../../components/shared/Pager";
import { SimpleTable } from "../../components/shared/SimpleTable";
import { StatTile } from "../../components/shared/StatTile";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Select } from "../../components/ui/Select";
import { Spinner } from "../../components/ui/Spinner";

const LIMIT = 25;
const STATUSES = ["queued", "running", "succeeded", "failed"];

export function AdminJobsPage() {
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [offset, setOffset] = useState(0);
  const summary = useAdminJobsSummary();
  const jobs = useAdminJobs({ status, type, limit: LIMIT, offset });
  const retry = useRetryJob();

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {STATUSES.map((name) => (
          <StatTile key={name} label={name[0].toUpperCase() + name.slice(1)} value={summary.data?.by_status[name] ?? "—"} />
        ))}
      </div>
      <Card title="Background jobs">
        <div className="mb-3 grid max-w-xl gap-3 sm:grid-cols-2">
          <Select
            label="Status"
            placeholder="All statuses"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setOffset(0);
            }}
            options={STATUSES.map((name) => ({ value: name, label: name }))}
          />
          <Select
            label="Type"
            placeholder="All types"
            value={type}
            onChange={(event) => {
              setType(event.target.value);
              setOffset(0);
            }}
            options={(summary.data?.by_type ?? []).map((row) => ({ value: row.type, label: `${row.type} (${row.count})` }))}
          />
        </div>
        {retry.error && <ErrorState error={retry.error} />}
        {jobs.isLoading && <Spinner className="mx-auto my-8" />}
        {jobs.isError && <ErrorState error={jobs.error} onRetry={() => jobs.refetch()} />}
        {jobs.data && (
          <>
            <SimpleTable
              rows={jobs.data.items}
              rowKey={(row) => row.id}
              empty="No jobs match."
              columns={[
                { header: "Created", cell: (row) => new Date(row.created_at).toLocaleString() },
                { header: "Type", cell: (row) => <code className="text-xs">{row.type}</code> },
                { header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
                { header: "Attempts", numeric: true, cell: (row) => `${row.attempts}/${row.max_attempts}` },
                {
                  header: "Last error",
                  cell: (row) => (
                    <span className="block max-w-sm truncate text-xs text-red-700" title={row.last_error}>
                      {row.last_error || "—"}
                    </span>
                  ),
                },
                {
                  header: "Action",
                  numeric: true,
                  cell: (row) =>
                    row.status === "failed" && (
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={retry.isPending && retry.variables === row.id}
                        onClick={() => retry.mutate(row.id)}
                      >
                        Retry
                      </Button>
                    ),
                },
              ]}
            />
            <Pager count={jobs.data.count} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>
    </div>
  );
}
