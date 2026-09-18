import { Button } from "../ui/Button";

type Props = { error: unknown; onRetry?: () => void; title?: string };

export function ErrorState({ error, onRetry, title = "We couldn't load this." }: Props) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-800">
      <p className="font-medium">{title}</p>
      <p className="mt-1">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
