import { useAdminEvals } from "../../api/admin";
import { EmptyState } from "../../components/shared/EmptyState";
import { ErrorState } from "../../components/shared/ErrorState";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";

// Eval metrics are rates between 0 and 1; anything else is shown as it is.
const formatMetric = (value: unknown) =>
  typeof value === "number" && value >= 0 && value <= 1 ? `${(value * 100).toFixed(1)}%` : String(value);

export function AdminEvalsPage() {
  const evals = useAdminEvals();

  if (evals.isLoading) return <Spinner className="mx-auto mt-16" />;
  if (evals.isError) return <ErrorState error={evals.error} onRetry={() => evals.refetch()} />;
  if (!evals.data?.length) {
    return <EmptyState title="No eval runs yet" description="Run python manage.py run_evals to record one." />;
  }

  return (
    <div className="space-y-3">
      {evals.data.map((run) => (
        <Card
          key={run.id}
          title={`${run.suite} · ${new Date(run.created_at).toLocaleString()}`}
          actions={<Badge tone={run.passed ? "green" : "red"}>{run.passed ? "passed" : "failed"}</Badge>}
        >
          <dl className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
            {Object.entries(run.metrics).map(([name, value]) => (
              <div key={name}>
                <dt className="text-slate-500">{name.replaceAll("_", " ")}</dt>
                <dd className="font-medium tabular-nums text-slate-900">{formatMetric(value)}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-xs text-slate-500">
            {run.case_count} cases · commit <code>{run.git_sha || "unknown"}</code>
          </p>
          <details className="mt-2 text-xs">
            <summary className="cursor-pointer text-indigo-700">Case results</summary>
            <pre className="mt-2 max-h-64 overflow-auto rounded bg-slate-50 p-2">
              {JSON.stringify(run.case_results, null, 2)}
            </pre>
          </details>
        </Card>
      ))}
    </div>
  );
}
