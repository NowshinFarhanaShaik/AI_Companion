import { useProjectAnalytics } from "../../api/analytics";
import { ErrorState } from "../../components/shared/ErrorState";
import { MasteryBar } from "../../components/shared/MasteryBar";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";
import { useProjectId } from "../projects/useProjectId";
import { AIUsagePanel, ActivityPanel, QuizPanel, SummaryTiles } from "./AnalyticsPanels";

export function ProjectAnalyticsPage() {
  const analytics = useProjectAnalytics(useProjectId());

  if (analytics.isLoading) return <Spinner className="mx-auto mt-16" />;
  if (analytics.isError) return <ErrorState error={analytics.error} onRetry={() => analytics.refetch()} />;
  const data = analytics.data;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <SummaryTiles {...data} />
      <div className="grid gap-4 lg:grid-cols-2">
        <ActivityPanel activity={data.activity} />
        <QuizPanel quiz={data.quiz} />
      </div>
      <Card title="Concept trends">
        {data.trends.length === 0 ? (
          <p className="text-sm text-slate-600">Upload a PDF so concepts can be extracted.</p>
        ) : (
          <div className="space-y-3">
            {data.trends.map((trend) => (
              <MasteryBar
                key={trend.concept_id}
                label={trend.name}
                value={trend.score}
                trend={trend.label}
                unpractised={trend.evidence_count === 0}
              />
            ))}
          </div>
        )}
      </Card>
      <AIUsagePanel ai={data.ai} />
    </div>
  );
}
