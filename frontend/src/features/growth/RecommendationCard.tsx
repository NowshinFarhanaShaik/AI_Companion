import { Link } from "react-router-dom";
import { useCompleteRecommendation } from "../../api/learning";
import type { Recommendation, RecommendationAction } from "../../api/types";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { buttonClasses } from "../../components/ui/buttonStyles";
import { Card } from "../../components/ui/Card";

const ACTIONS: Record<RecommendationAction, { tab: string; label: string }> = {
  review_material: { tab: "materials", label: "Open materials" },
  upload_material: { tab: "materials", label: "Upload material" },
  take_quiz: { tab: "quiz", label: "Start a quiz" },
  ask_tutor: { tab: "tutor", label: "Ask the Tutor" },
};

type Props = { recommendation: Recommendation | null; showProject?: boolean; title?: string };

export function RecommendationCard({ recommendation, showProject = false, title = "Recommended next step" }: Props) {
  const complete = useCompleteRecommendation();

  if (!recommendation) {
    return (
      <Card title={title}>
        <p className="text-sm text-slate-600">
          No recommendation yet. Upload material or take a quiz and one will appear here.
        </p>
      </Card>
    );
  }

  const action = ACTIONS[recommendation.action_type];
  return (
    <Card title={title}>
      <div className="flex flex-wrap items-center gap-2">
        {recommendation.concept_name && <Badge tone="blue">{recommendation.concept_name}</Badge>}
        {showProject && <Badge>{recommendation.project_name}</Badge>}
      </div>
      <p className="mt-3 text-base text-slate-900">{recommendation.text}</p>
      {recommendation.reason && <p className="mt-1 text-sm text-slate-500">Why: {recommendation.reason}</p>}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Link to={`/projects/${recommendation.project_id}/${action.tab}`} className={buttonClasses("primary", "sm")}>
          {action.label}
        </Link>
        <Button
          variant="secondary"
          size="sm"
          loading={complete.isPending}
          onClick={() => complete.mutate(recommendation.id)}
        >
          Mark done
        </Button>
      </div>
      {complete.error && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {complete.error.message}
        </p>
      )}
    </Card>
  );
}
