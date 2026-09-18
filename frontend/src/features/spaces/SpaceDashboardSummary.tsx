import { useSpaceDashboard } from "../../api/learning";
import { ActivityList } from "../../components/shared/ActivityList";
import { ErrorState } from "../../components/shared/ErrorState";
import { MasteryBar } from "../../components/shared/MasteryBar";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";

export function SpaceDashboardSummary({ spaceId }: { spaceId: string }) {
  const dashboard = useSpaceDashboard(spaceId);

  if (dashboard.isLoading) return <Spinner className="mx-auto my-6" />;
  if (dashboard.isError) return <ErrorState error={dashboard.error} onRetry={() => dashboard.refetch()} />;
  const data = dashboard.data;
  if (!data) return null;
  const attention = data.projects.reduce((sum, project) => sum + project.attention_count, 0);

  return (
    <div className="mb-6 grid gap-6 md:grid-cols-2">
      <Card title="Space progress">
        <MasteryBar label="Mastery across this Space's projects" value={data.overall_progress} />
        <div className="mt-3 flex flex-wrap gap-2">
          <Badge>
            {data.project_count} {data.project_count === 1 ? "project" : "projects"}
          </Badge>
          {attention > 0 ? (
            <Badge tone="yellow">
              {attention} {attention === 1 ? "concept needs" : "concepts need"} attention
            </Badge>
          ) : (
            <Badge tone="green">Nothing needs attention</Badge>
          )}
        </div>
      </Card>
      <Card title="Recent activity">
        <ActivityList items={data.recent_activity} empty="No activity in this Space yet." />
      </Card>
    </div>
  );
}
