import { Badge, type BadgeTone } from "../ui/Badge";

const toneFor: Record<string, BadgeTone> = {
  queued: "gray",
  processing: "blue",
  running: "blue",
  active: "blue",
  ready: "green",
  succeeded: "green",
  completed: "green",
  done: "green",
  ok: "green",
  improving: "green",
  stable: "gray",
  not_enough_data: "gray",
  superseded: "gray",
  needs_attention: "yellow",
  failed: "red",
  error: "red",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={toneFor[status] ?? "gray"}>{status.replaceAll("_", " ")}</Badge>;
}
