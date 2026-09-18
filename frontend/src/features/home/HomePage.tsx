import { Link } from "react-router-dom";
import { useHome } from "../../api/learning";
import { useAuth } from "../../auth/useAuth";
import { EmptyState } from "../../components/shared/EmptyState";
import { ErrorState } from "../../components/shared/ErrorState";
import { MasteryBar } from "../../components/shared/MasteryBar";
import { PageHeader } from "../../components/shared/PageHeader";
import { Badge } from "../../components/ui/Badge";
import { buttonClasses } from "../../components/ui/buttonStyles";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";
import { RecommendationCard } from "../growth/RecommendationCard";

export function HomePage() {
  const { user } = useAuth();
  const home = useHome();
  const greeting = user?.name ? `Welcome back, ${user.name}` : "Welcome back";

  if (home.isLoading) return <Spinner className="mx-auto mt-16" />;
  if (home.isError) return <ErrorState error={home.error} onRetry={() => home.refetch()} />;
  const data = home.data;
  if (!data) return null;
  const current = data.continue_learning;

  if (!current) {
    return (
      <>
        <PageHeader title={greeting} />
        <EmptyState
          title="Nothing to continue yet"
          description="A Space is a broad area you want to learn. A Project inside it holds your material, Tutor, quizzes and progress."
          action={
            <Link to="/spaces" className={buttonClasses()}>
              Go to Spaces
            </Link>
          }
        />
      </>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title={greeting} subtitle="Where you were, how you are doing, and what to do next." />

      <div className="grid gap-6 md:grid-cols-2">
        <Card title="Continue learning">
          <p className="text-sm text-slate-500">{current.space_name}</p>
          <p className="mb-3 text-lg font-semibold text-slate-900">{current.name}</p>
          <MasteryBar label="Progress" value={current.overall_progress} />
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge>{current.concept_count} concepts</Badge>
            {current.attention_count > 0 && (
              <Badge tone="yellow">
                {current.attention_count} {current.attention_count === 1 ? "needs" : "need"} attention
              </Badge>
            )}
          </div>
          <Link to={`/projects/${current.id}`} className={`mt-4 ${buttonClasses()}`}>
            Open project
          </Link>
        </Card>
        <RecommendationCard recommendation={data.next_action} showProject title="What to do next" />
      </div>

      <Card title="Overall progress">
        <MasteryBar label="Across all your projects" value={data.overall_progress} />
      </Card>

      <Card title="Areas requiring attention">
        {data.attention_areas.length === 0 ? (
          <p className="text-sm text-slate-600">Nothing needs attention right now.</p>
        ) : (
          <ul className="space-y-3">
            {data.attention_areas.map((area) => (
              <li key={area.concept_id}>
                <Link to={`/projects/${area.project_id}/growth`} className="block rounded-md hover:bg-slate-50">
                  <MasteryBar
                    label={`${area.concept_name} (${area.project_name})`}
                    value={area.score}
                    trend={area.label}
                  />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Recent projects">
        <ul className="divide-y divide-slate-100">
          {data.recent_projects.map((project) => (
            <li key={project.id} className="flex items-center justify-between gap-4 py-3">
              <div className="min-w-0">
                <Link to={`/projects/${project.id}`} className="font-medium text-slate-900 hover:underline">
                  {project.name}
                </Link>
                <p className="truncate text-sm text-slate-500">{project.space_name}</p>
              </div>
              <span className="shrink-0 text-sm font-medium tabular-nums text-slate-700">
                {Math.round(project.overall_progress * 100)}%
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
