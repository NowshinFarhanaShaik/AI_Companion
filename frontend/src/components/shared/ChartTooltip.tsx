type Props = {
  active?: boolean;
  payload?: { value?: number | string }[];
  label?: number | string;
  formatValue: (value: number | string) => string;
  formatLabel: (label: number | string) => string;
};

// Recharts injects active, payload and label. The value leads; the label follows.
export function ChartTooltip({ active, payload, label, formatValue, formatLabel }: Props) {
  const value = payload?.[0]?.value;
  if (!active || value === undefined || label === undefined) return null;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
      <p className="font-semibold text-slate-900">{formatValue(value)}</p>
      <p className="text-slate-500">{formatLabel(label)}</p>
    </div>
  );
}
