import { useState } from "react";
import { useActiveRecommendation, useGrowth } from "../../api/learning";
import type { TrendLabel } from "../../api/types";
import { EmptyState } from "../../components/shared/EmptyState";
import { ErrorState } from "../../components/shared/ErrorState";
import { MasteryBar } from "../../components/shared/MasteryBar";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";
import { useProjectId } from "../projects/useProjectId";
import { MasteryChart } from "./MasteryChart";
import { RecommendationCard } from "./RecommendationCard";

const LABELS: TrendLabel[] = ["improving", "stable", "needs_attention", "not_enough_data"];

export function GrowthPage() {
  const projectId = useProjectId();
  const growth = useGrowth(projectId);
  const recommendation = useActiveRecommendation(projectId);
  const [chosenId, setChosenId] = useState<string | null>(null);

  if (growth.isLoading) return <Spinner className="mx-auto mt-16" />;
  if (growth.isError) return <ErrorState error={growth.error} onRetry={() => growth.refetch()} />;
  const { trends = [], series = [] } = growth.data ?? {};
  if (trends.length === 0) {
    return (
      <EmptyState
        title="No concepts yet"
        description="Upload a PDF in Materials. Once it is processed, its concepts and your mastery of them appear here."
      />
    );
  }
  const selected = series.find((item) => item.concept_id === chosenId) ?? series[0];

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-600">
        Mastery is an estimate that moves as you answer questions. Trends compare the last 14 days.
      </p>
      <div className="flex flex-wrap gap-2">
        {LABELS.map((label) => (
          <span key={label} className="flex items-center gap-1 text-sm text-slate-700">
            <StatusBadge status={label} />
            {trends.filter((trend) => trend.label === label).length}
          </span>
        ))}
      </div>

      <RecommendationCard recommendation={recommendation.data ?? null} />

      <Card title="Concept mastery">
        <div className="space-y-3">
          {trends.map((trend) => (
            <MasteryBar
              key={trend.concept_id}
              label={trend.name}
              value={trend.score}
              trend={trend.label}
              unpractised={trend.evidence_count === 0}
            />
          ))}
        </div>
      </Card>

      <Card title={selected ? `Mastery over time: ${selected.name}` : "Mastery over time"}>
        {selected ? (
          <>
            <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Concept">
              {series.map((item) => (
                <button
                  key={item.concept_id}
                  type="button"
                  aria-pressed={item.concept_id === selected.concept_id}
                  onClick={() => setChosenId(item.concept_id)}
                  className={`rounded-full border px-3 py-1 text-sm ${
                    item.concept_id === selected.concept_id
                      ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                      : "border-slate-300 text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  {item.name}
                </button>
              ))}
            </div>
            <MasteryChart series={selected} />
          </>
        ) : (
          <p className="text-sm text-slate-600">Take a quiz to start a history for your concepts.</p>
        )}
      </Card>
    </div>
  );
}
