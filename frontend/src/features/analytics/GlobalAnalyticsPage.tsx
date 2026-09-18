import { Link } from "react-router-dom";
import { useGlobalAnalytics } from "../../api/analytics";
import { ErrorState } from "../../components/shared/ErrorState";
import { PageHeader } from "../../components/shared/PageHeader";
import { SimpleTable } from "../../components/shared/SimpleTable";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";
import { AIUsagePanel, ActivityPanel, QuizPanel, SummaryTiles } from "./AnalyticsPanels";
import { date, percent } from "./format";

const linkClass = "font-medium text-indigo-600 hover:underline";

export function GlobalAnalyticsPage() {
  const analytics = useGlobalAnalytics();

  if (analytics.isLoading) return <Spinner className="mx-auto mt-16" />;
  if (analytics.isError) return <ErrorState error={analytics.error} onRetry={() => analytics.refetch()} />;
  const data = analytics.data;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <PageHeader title="Analytics" subtitle="Learning activity across all your Spaces and Projects" />
      <SummaryTiles {...data} />
      <div className="grid gap-4 lg:grid-cols-2">
        <ActivityPanel activity={data.activity} />
        <QuizPanel quiz={data.quiz} />
      </div>
      <Card title="Spaces">
        <SimpleTable
          rows={data.spaces}
          rowKey={(row) => row.space_id}
          empty="No Spaces yet."
          columns={[
            {
              header: "Space",
              cell: (row) => (
                <Link to={`/spaces/${row.space_id}`} className={linkClass}>
                  {row.name}
                </Link>
              ),
            },
            { header: "Projects", numeric: true, cell: (row) => row.projects },
            { header: "Events", numeric: true, cell: (row) => row.events },
            { header: "Avg. mastery", numeric: true, cell: (row) => percent(row.average_mastery) },
          ]}
        />
      </Card>
      <Card title="Projects">
        <SimpleTable
          rows={data.projects}
          rowKey={(row) => row.project_id}
          empty="No Projects yet."
          columns={[
            {
              header: "Project",
              cell: (row) => (
                <Link to={`/projects/${row.project_id}/analytics`} className={linkClass}>
                  {row.name}
                </Link>
              ),
            },
            { header: "Space", cell: (row) => row.space_name },
            { header: "Materials", numeric: true, cell: (row) => row.materials },
            { header: "Concepts", numeric: true, cell: (row) => row.concepts },
            { header: "Avg. mastery", numeric: true, cell: (row) => percent(row.average_mastery) },
            { header: "Answers", numeric: true, cell: (row) => row.questions_answered },
            { header: "Avg. score", numeric: true, cell: (row) => percent(row.average_score) },
            { header: "Last active", cell: (row) => date(row.last_activity_at) },
          ]}
        />
      </Card>
      <AIUsagePanel ai={data.ai} />
    </div>
  );
}
