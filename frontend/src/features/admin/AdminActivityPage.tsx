import { useSearchParams } from "react-router-dom";
import { useAdminActivity, useAdminUser, useAdminUsers } from "../../api/admin";
import type { AdminActivityFilters } from "../../api/types";
import { activityTypeLabel, activityTypeOptions } from "../../components/shared/activityLabels";
import { ErrorState } from "../../components/shared/ErrorState";
import { Pager } from "../../components/shared/Pager";
import { SimpleTable } from "../../components/shared/SimpleTable";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { Spinner } from "../../components/ui/Spinner";

const LIMIT = 50;
const FILTERS = ["user_id", "space_id", "project_id", "type", "date_from", "date_to"] as const;

// Filters live in the URL, so a filtered view can be shared or bookmarked.
export function AdminActivityPage() {
  const [params, setParams] = useSearchParams();
  const value = (key: string) => params.get(key) ?? "";
  const filters: AdminActivityFilters = {
    user_id: value("user_id") || undefined,
    space_id: value("space_id") || undefined,
    project_id: value("project_id") || undefined,
    type: value("type") || undefined,
    date_from: value("date_from") || undefined,
    date_to: value("date_to") || undefined,
    limit: LIMIT,
    offset: Number(params.get("offset") ?? 0),
  };
  const activity = useAdminActivity(filters);
  const users = useAdminUsers({ limit: 100, offset: 0 });
  // Space and Project choices come from the selected user's own journey.
  const selectedUser = useAdminUser(filters.user_id);

  function update(key: string, next: string) {
    const copy = new URLSearchParams(params);
    if (next) copy.set(key, next);
    else copy.delete(key);
    if (key === "user_id") {
      copy.delete("space_id");
      copy.delete("project_id");
    }
    if (key !== "offset") copy.delete("offset");
    setParams(copy, { replace: true });
  }

  const hasUser = Boolean(filters.user_id);
  const spaces = selectedUser.data?.spaces ?? [];
  const projects = (selectedUser.data?.projects ?? []).filter(
    (project) => !filters.space_id || project.space_id === filters.space_id,
  );

  return (
    <Card
      title="Platform activity"
      actions={
        FILTERS.some((key) => params.has(key)) && (
          <Button variant="ghost" size="sm" onClick={() => setParams({}, { replace: true })}>
            Clear filters
          </Button>
        )
      }
    >
      <div className="mb-4 grid gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Select
          label="User"
          placeholder="All users"
          value={value("user_id")}
          onChange={(e) => update("user_id", e.target.value)}
          options={(users.data?.items ?? []).map((user) => ({ value: user.id, label: user.email }))}
        />
        <Select
          label="Space"
          placeholder={hasUser ? "All spaces" : "Pick a user first"}
          disabled={!hasUser}
          value={value("space_id")}
          onChange={(e) => update("space_id", e.target.value)}
          options={spaces.map((space) => ({ value: space.id, label: space.name }))}
        />
        <Select
          label="Project"
          placeholder={hasUser ? "All projects" : "Pick a user first"}
          disabled={!hasUser}
          value={value("project_id")}
          onChange={(e) => update("project_id", e.target.value)}
          options={projects.map((project) => ({ value: project.project_id, label: project.name }))}
        />
        <Select
          label="Activity type"
          placeholder="All types"
          value={value("type")}
          onChange={(e) => update("type", e.target.value)}
          options={activityTypeOptions}
        />
        <Input label="From" type="date" value={value("date_from")} onChange={(e) => update("date_from", e.target.value)} />
        <Input label="To" type="date" value={value("date_to")} onChange={(e) => update("date_to", e.target.value)} />
      </div>

      {activity.isLoading && <Spinner className="mx-auto my-8" />}
      {activity.isError && <ErrorState error={activity.error} onRetry={() => activity.refetch()} />}
      {activity.data && (
        <>
          <SimpleTable
            rows={activity.data.items}
            rowKey={(row) => row.id}
            empty="No activity matches these filters."
            columns={[
              { header: "When", cell: (row) => new Date(row.created_at).toLocaleString() },
              { header: "User", cell: (row) => row.user_email },
              { header: "Event", cell: (row) => activityTypeLabel(row.type) },
              { header: "Space", cell: (row) => row.space_name ?? "—" },
              { header: "Project", cell: (row) => row.project_name ?? "—" },
              {
                header: "Details",
                cell: (row) => (
                  <code className="block max-w-xs truncate text-xs text-slate-500" title={JSON.stringify(row.payload)}>
                    {JSON.stringify(row.payload)}
                  </code>
                ),
              },
            ]}
          />
          <Pager
            count={activity.data.count}
            limit={LIMIT}
            offset={filters.offset}
            onChange={(next) => update("offset", String(next))}
          />
        </>
      )}
    </Card>
  );
}
