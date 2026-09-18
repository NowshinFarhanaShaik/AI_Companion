import { Link } from "react-router-dom";
import { useProjectDashboard } from "../../api/learning";
import { ActivityList } from "../../components/shared/ActivityList";
import { ErrorState } from "../../components/shared/ErrorState";
import { MasteryBar } from "../../components/shared/MasteryBar";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";
import { RecommendationCard } from "../growth/RecommendationCard";
import { useProjectId } from "./useProjectId";

const linkClass = "text-indigo-600 hover:underline";

export function ProjectDashboardPage() {
  const projectId = useProjectId();
  const dashboard = useProjectDashboard(projectId);

  if (dashboard.isLoading) return <Spinner className="mx-auto mt-16" />;
  if (dashboard.isError) return <ErrorState error={dashboard.error} onRetry={() => dashboard.refetch()} />;
  const data = dashboard.data;
  if (!data) return null;
  const { material_counts: materials, latest_quiz: quiz } = data;
  const processing = materials.queued + materials.processing;

  return (
    <div className="space-y-6">
      <Card title="Overall progress">
        <MasteryBar label="Mastery across concepts, weighted by importance" value={data.overall_progress} />
        <div className="mt-3 flex flex-wrap gap-2">
          <Badge>{data.concept_count} concepts</Badge>
          <Badge tone="green">{materials.ready} materials ready</Badge>
          {processing > 0 && <Badge tone="blue">{processing} processing</Badge>}
          {materials.failed > 0 && <Badge tone="red">{materials.failed} failed</Badge>}
        </div>
      </Card>

      <RecommendationCard recommendation={data.recommendation} />

      <div className="grid gap-6 md:grid-cols-2">
        <Card
          title="Strongest concepts"
          actions={
            <Link to="growth" className={`text-sm ${linkClass}`}>
              See growth
            </Link>
          }
        >
          {data.top_concepts.length === 0 ? (
            <p className="text-sm text-slate-600">
              No concepts yet.{" "}
              <Link to="materials" className={linkClass}>
                Upload a PDF
              </Link>{" "}
              to extract them.
            </p>
          ) : (
            <div className="space-y-3">
              {data.top_concepts.map((concept) => (
                <MasteryBar
                  key={concept.concept_id}
                  label={concept.name}
                  value={concept.score}
                  unpractised={concept.evidence_count === 0}
                />
              ))}
            </div>
          )}
        </Card>

        <Card title="Needs attention">
          {data.attention_concepts.length === 0 ? (
            <p className="text-sm text-slate-600">Nothing needs attention right now.</p>
          ) : (
            <div className="space-y-3">
              {data.attention_concepts.map((trend) => (
                <MasteryBar key={trend.concept_id} label={trend.name} value={trend.score} trend={trend.label} />
              ))}
            </div>
          )}
        </Card>

        <Card title="Latest quiz">
          {quiz ? (
            <>
              <p className="text-3xl font-semibold text-slate-900">{Math.round(quiz.average_score * 100)}%</p>
              <p className="text-sm text-slate-600">
                Average over {quiz.question_count} questions
                {quiz.completed_at && ` · ${new Date(quiz.completed_at).toLocaleDateString()}`}
              </p>
            </>
          ) : (
            <p className="text-sm text-slate-600">
              No quiz taken yet.{" "}
              <Link to="quiz" className={linkClass}>
                Start one
              </Link>
              .
            </p>
          )}
        </Card>

        <Card title="Recent activity">
          <ActivityList items={data.recent_activity} empty="No activity yet." />
        </Card>
      </div>
    </div>
  );
}
