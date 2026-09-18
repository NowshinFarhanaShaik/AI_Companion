import { StatusBadge } from "./StatusBadge";

type Props = { label: string; value: number; trend?: string; unpractised?: boolean };

// An unpractised concept only has its starting estimate, so its bar carries no severity colour.
export function MasteryBar({ label, value, trend, unpractised = false }: Props) {
  const percent = Math.round(Math.min(Math.max(value, 0), 1) * 100);
  const color = unpractised ? "bg-slate-300" : percent >= 70 ? "bg-green-500" : percent >= 40 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="truncate font-medium text-slate-800">{label}</span>
        <span className="flex items-center gap-2">
          {trend && <StatusBadge status={trend} />}
          <span className="tabular-nums text-slate-600">{percent}%</span>
        </span>
      </div>
      <div
        className="h-2 rounded-full bg-slate-200"
        role="progressbar"
        aria-label={label}
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
