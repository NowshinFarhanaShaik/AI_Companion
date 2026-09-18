import type { ActivityItem } from "../../api/types";
import { activityTypeLabel } from "./activityLabels";
import { formatDateTime } from "./chartTheme";

function describe(item: ActivityItem): string {
  const label = activityTypeLabel(item.type);
  const concept = item.payload.concept_name;
  return typeof concept === "string" && concept ? `${label}: ${concept}` : label;
}

export function ActivityList({ items, empty }: { items: ActivityItem[]; empty: string }) {
  if (items.length === 0) return <p className="text-sm text-slate-600">{empty}</p>;
  return (
    <ul className="divide-y divide-slate-100 text-sm">
      {items.map((item) => (
        <li key={item.id} className="flex justify-between gap-3 py-2">
          <span className="text-slate-800">{describe(item)}</span>
          <time dateTime={item.created_at} className="shrink-0 text-slate-500">
            {formatDateTime(item.created_at)}
          </time>
        </li>
      ))}
    </ul>
  );
}
