import { Button } from "../ui/Button";

type Props = { count: number; limit: number; offset: number; onChange: (offset: number) => void };

export function Pager({ count, limit, offset, onChange }: Props) {
  if (count <= limit) return null;
  const last = Math.min(offset + limit, count);
  return (
    <div className="mt-3 flex items-center justify-between text-sm text-slate-600">
      <span>
        {offset + 1}–{last} of {count}
      </span>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
          Previous
        </Button>
        <Button variant="secondary" size="sm" disabled={last >= count} onClick={() => onChange(offset + limit)}>
          Next
        </Button>
      </div>
    </div>
  );
}
