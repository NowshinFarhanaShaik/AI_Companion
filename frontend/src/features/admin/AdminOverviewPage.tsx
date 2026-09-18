import { useAdminOverview } from "../../api/admin";
import { ErrorState } from "../../components/shared/ErrorState";
import { StatTile } from "../../components/shared/StatTile";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";
import { ActivityPanel } from "../analytics/AnalyticsPanels";

export function AdminOverviewPage() {
  const overview = useAdminOverview();
  if (overview.isLoading) return <Spinner className="mx-auto mt-16" />;
  if (overview.isError) return <ErrorState error={overview.error} onRetry={() => overview.refetch()} />;
  const data = overview.data;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Users" value={data.users} hint={`${data.active_users_7d} active in the last 7 days`} />
        <StatTile label="Spaces" value={data.spaces} />
        <StatTile label="Projects" value={data.projects} />
        <StatTile label="Materials" value={data.materials} />
        <StatTile label="Quiz sessions" value={data.quiz_sessions} />
        <StatTile label="Questions answered" value={data.questions_answered} />
        <StatTile label="Learning events, last 14 days" value={data.events.total} />
      </div>
      <Card title="Materials by status">
        {data.materials_by_status.length === 0 ? (
          <p className="text-sm text-slate-600">No materials uploaded yet.</p>
        ) : (
          <div className="flex flex-wrap gap-4 text-sm text-slate-800">
            {data.materials_by_status.map((row) => (
              <span key={row.status} className="flex items-center gap-2">
                <StatusBadge status={row.status} /> {row.count}
              </span>
            ))}
          </div>
        )}
      </Card>
      <ActivityPanel activity={data.events} />
    </div>
  );
}
