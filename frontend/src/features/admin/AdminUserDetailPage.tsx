import { Link, useParams } from "react-router-dom";
import { useAdminUser } from "../../api/admin";
import { activityTypeLabel } from "../../components/shared/activityLabels";
import { ErrorState } from "../../components/shared/ErrorState";
import { SimpleTable } from "../../components/shared/SimpleTable";
import { StatTile } from "../../components/shared/StatTile";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";
import { AIUsagePanel } from "../analytics/AnalyticsPanels";
import { date, percent, usd } from "../analytics/format";

const linkClass = "text-sm text-indigo-600 hover:underline";

export function AdminUserDetailPage() {
  const { userId } = useParams();
  const detail = useAdminUser(userId);

  if (detail.isLoading) return <Spinner className="mx-auto mt-16" />;
  if (detail.isError) return <ErrorState error={detail.error} onRetry={() => detail.refetch()} />;
  const data = detail.data;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{data.user.name || data.user.email}</h2>
          <p className="text-sm text-slate-500">
            {data.user.email} · joined {date(data.user.joined_at)}
          </p>
        </div>
        <div className="flex gap-4">
          <Link className={linkClass} to={`/admin/activity?user_id=${data.user.id}`}>
            All activity
          </Link>
          <Link className={linkClass} to="/admin/users">
            Back to users
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Spaces" value={data.spaces.length} hint={data.spaces.map((space) => space.name).join(", ")} />
        <StatTile label="Projects" value={data.projects.length} />
        <StatTile label="AI calls" value={data.ai.calls} hint={`${data.ai.errors} failed`} />
        <StatTile label="AI cost" value={usd(data.ai.estimated_cost_usd)} />
      </div>

      <Card title="Projects and progress">
        <SimpleTable
          rows={data.projects}
          rowKey={(row) => row.project_id}
          empty="No projects yet."
          columns={[
            { header: "Project", cell: (row) => row.name },
            { header: "Space", cell: (row) => row.space_name },
            { header: "Materials", numeric: true, cell: (row) => row.materials },
            { header: "Concepts", numeric: true, cell: (row) => row.concepts },
            { header: "Avg. mastery", numeric: true, cell: (row) => percent(row.average_mastery) },
            { header: "Answers", numeric: true, cell: (row) => row.questions_answered },
            { header: "Avg. score", numeric: true, cell: (row) => percent(row.average_score) },
          ]}
        />
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Recent assessments">
          <SimpleTable
            rows={data.assessments}
            rowKey={(row) => row.id}
            empty="No quizzes yet."
            columns={[
              { header: "Project", cell: (row) => row.project_name },
              { header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
              { header: "Answered", numeric: true, cell: (row) => row.answered },
              { header: "Score", numeric: true, cell: (row) => percent(row.average_score) },
              { header: "Started", cell: (row) => new Date(row.created_at).toLocaleString() },
            ]}
          />
        </Card>
        <Card title="Recent activity">
          <SimpleTable
            rows={data.recent_activity}
            rowKey={(row) => row.id}
            empty="No activity yet."
            columns={[
              { header: "When", cell: (row) => new Date(row.created_at).toLocaleString() },
              { header: "Event", cell: (row) => activityTypeLabel(row.type) },
              { header: "Project", cell: (row) => row.project_name ?? "—" },
            ]}
          />
        </Card>
      </div>

      <AIUsagePanel ai={data.ai} />
    </div>
  );
}
