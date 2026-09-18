import { useAdminHealth } from "../../api/admin";
import type { HealthStatus } from "../../api/types";
import { ErrorState } from "../../components/shared/ErrorState";
import { Badge, type BadgeTone } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";

// Status is never colour alone: every state has a symbol and a word.
const STATUS: Record<HealthStatus, { tone: BadgeTone; label: string; headline: string }> = {
  green: { tone: "green", label: "✓ OK", headline: "All systems normal" },
  amber: { tone: "yellow", label: "! Warning", headline: "Degraded: needs a look" },
  red: { tone: "red", label: "✕ Problem", headline: "Problem: act now" },
};

export function AdminHealthPage() {
  const health = useAdminHealth();

  if (health.isLoading) return <Spinner className="mx-auto mt-16" />;
  // If the API itself is down, this error state is the health signal.
  if (health.isError) return <ErrorState error={health.error} onRetry={() => health.refetch()} />;
  const data = health.data;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <Badge tone={STATUS[data.status].tone}>{STATUS[data.status].label}</Badge>
          <p className="text-lg font-semibold text-slate-900">{STATUS[data.status].headline}</p>
          <p className="text-xs text-slate-500">
            Checked {new Date(data.checked_at).toLocaleTimeString()} · refreshes every 15 seconds
          </p>
        </div>
      </Card>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {data.checks.map((check) => (
          <Card key={check.key}>
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm text-slate-600">{check.label}</p>
              <Badge tone={STATUS[check.status].tone}>{STATUS[check.status].label}</Badge>
            </div>
            <p className="mt-1 truncate font-medium text-slate-900" title={check.value}>
              {check.key === "last_ai_success" && check.value !== "never"
                ? new Date(check.value).toLocaleString()
                : check.value}
            </p>
            {check.detail && <p className="mt-1 text-xs text-slate-500">{check.detail}</p>}
          </Card>
        ))}
      </div>
    </div>
  );
}
