import type { QuizQuestion } from "../../api/types";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { scoreTone } from "./scoreTone";

function PointList({ title, points, marker, color }: { title: string; points: string[]; marker: string; color: string }) {
  if (points.length === 0) return null;
  return (
    <div>
      <h3 className={`mb-1 text-sm font-semibold ${color}`}>{title}</h3>
      <ul className="space-y-1 text-sm text-slate-700">
        {points.map((point, index) => (
          <li key={index} className="flex gap-2">
            <span className={color} aria-hidden="true">
              {marker}
            </span>
            <span>{point}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function FeedbackCard({ question }: { question: QuizQuestion }) {
  const attempt = question.attempt;
  if (!attempt) return null;
  const { feedback } = attempt;

  return (
    <Card title="Feedback" actions={<Badge tone={scoreTone(attempt.score)}>{Math.round(attempt.score * 100)}%</Badge>}>
      <p className="mb-4 text-sm text-slate-800">{feedback.feedback}</p>
      <div className="grid gap-4 md:grid-cols-2">
        <PointList title="What you understood" points={feedback.understood} marker="✓" color="text-green-700" />
        <PointList title="What is missing" points={feedback.missing} marker="○" color="text-amber-700" />
        <PointList title="Misconceptions" points={feedback.misconceptions} marker="✕" color="text-red-700" />
      </div>
      {question.key_points && question.key_points.length > 0 && (
        <div className="mt-4 border-t border-slate-200 pt-3">
          <h3 className="mb-1 text-sm font-semibold text-slate-600">A complete answer covers</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            {question.key_points.map((point, index) => (
              <li key={index}>{point}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
