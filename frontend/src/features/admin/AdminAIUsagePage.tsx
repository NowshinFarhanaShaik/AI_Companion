import { useState } from "react";
import { useAdminAIUsage } from "../../api/admin";
import type { AICallRow, AIGroupRow } from "../../api/types";
import { ErrorState } from "../../components/shared/ErrorState";
import { SimpleTable, type Column } from "../../components/shared/SimpleTable";
import { StatTile } from "../../components/shared/StatTile";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";
import { usd } from "../analytics/format";

const WINDOWS = [1, 7, 30];
const ms = (value: number | null) => (value === null ? "—" : `${Math.round(value)} ms`);

function groupColumns<K extends "feature" | "model">(key: K, header: string): Column<AIGroupRow & Record<K, string>>[] {
  return [
    { header, cell: (row) => row[key] },
    { header: "Calls", numeric: true, cell: (row) => row.calls },
    { header: "Failed", numeric: true, cell: (row) => row.errors },
    { header: "Avg. latency", numeric: true, cell: (row) => ms(row.average_latency_ms) },
    { header: "Tokens in", numeric: true, cell: (row) => row.input_tokens.toLocaleString() },
    { header: "Tokens out", numeric: true, cell: (row) => row.output_tokens.toLocaleString() },
    { header: "Est. cost", numeric: true, cell: (row) => usd(row.estimated_cost_usd) },
  ];
}

const callColumns: Column<AICallRow>[] = [
  { header: "When", cell: (row) => new Date(row.created_at).toLocaleString() },
  { header: "Feature", cell: (row) => row.feature },
  { header: "Model", cell: (row) => <code className="text-xs">{row.model}</code> },
  {
    header: "Result",
    cell: (row) =>
      row.status === "ok" ? <Badge tone="green">ok</Badge> : <Badge tone="red">{row.error_type || "error"}</Badge>,
  },
  { header: "Latency", numeric: true, cell: (row) => ms(row.latency_ms) },
  { header: "Retries", numeric: true, cell: (row) => row.retries },
  { header: "Trace", cell: (row) => <code className="text-xs">{row.trace_id.slice(0, 8) || "—"}</code> },
  { header: "User", cell: (row) => row.user_email ?? "—" },
  { header: "Project", cell: (row) => row.project_name ?? "—" },
];

export function AdminAIUsagePage() {
  const [days, setDays] = useState(7);
  const usage = useAdminAIUsage(days);

  if (usage.isLoading) return <Spinner className="mx-auto mt-16" />;
  if (usage.isError) return <ErrorState error={usage.error} onRetry={() => usage.refetch()} />;
  const data = usage.data;
  if (!data) return null;
  const { totals, latency } = data;

  return (
    <div className="space-y-4">
      <div className="flex gap-2" role="group" aria-label="Time window">
        {WINDOWS.map((option) => (
          <Button
            key={option}
            size="sm"
            variant={option === days ? "primary" : "secondary"}
            aria-pressed={option === days}
            onClick={() => setDays(option)}
          >
            {option === 1 ? "24 hours" : `${option} days`}
          </Button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatTile label="AI calls" value={totals.calls} />
        <StatTile label="Error rate" value={`${(totals.error_rate * 100).toFixed(1)}%`} hint={`${totals.errors} failed`} />
        <StatTile label="Latency p50" value={ms(latency.p50_ms)} hint="successful calls" />
        <StatTile label="Latency p95" value={ms(latency.p95_ms)} hint="successful calls" />
        <StatTile
          label="Estimated cost"
          value={usd(totals.estimated_cost_usd)}
          hint={`${(totals.input_tokens + totals.output_tokens).toLocaleString()} tokens`}
        />
      </div>
      <Card title="By feature">
        <SimpleTable
          rows={data.by_feature}
          rowKey={(row) => row.feature}
          empty="No AI calls in this window."
          columns={groupColumns("feature", "Feature")}
        />
      </Card>
      <Card title="By model">
        <SimpleTable
          rows={data.by_model}
          rowKey={(row) => row.model}
          empty="No AI calls in this window."
          columns={groupColumns("model", "Model")}
        />
      </Card>
      <Card title="Slowest calls">
        <SimpleTable rows={data.slowest} rowKey={(row) => row.id} empty="No AI calls in this window." columns={callColumns} />
      </Card>
      <Card title="Most recent failures">
        <SimpleTable
          rows={data.recent_failures}
          rowKey={(row) => row.id}
          empty="No failed calls in this window."
          columns={callColumns}
        />
      </Card>
    </div>
  );
}
