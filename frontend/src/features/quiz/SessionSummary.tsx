import { Link } from "react-router-dom";
import type { QuizSession } from "../../api/types";
import { MasteryBar } from "../../components/shared/MasteryBar";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { buttonClasses } from "../../components/ui/buttonStyles";
import { Card } from "../../components/ui/Card";
import { scoreTone } from "./scoreTone";

export function SessionSummary({ session, onRestart }: { session: QuizSession; onRestart: () => void }) {
  const { summary } = session;
  if (!summary) return null;

  return (
    <div className="space-y-4">
      <Card
        title="Quiz complete"
        actions={<Badge tone={scoreTone(summary.average_score)}>{Math.round(summary.average_score * 100)}%</Badge>}
      >
        <p className="text-sm text-slate-700">
          You answered {summary.answered_count} question{summary.answered_count === 1 ? "" : "s"}. Your concept
          mastery has been updated from these answers.
        </p>
        <div className="mt-4 space-y-3">
          {summary.by_concept.map((row) => (
            <MasteryBar
              key={row.concept_id}
              label={`${row.concept_name} (${row.question_count} question${row.question_count === 1 ? "" : "s"})`}
              value={row.average_score}
            />
          ))}
        </div>
        <div className="mt-5 flex flex-wrap gap-3">
          <Button onClick={onRestart}>Take another quiz</Button>
          <Link to="../growth" relative="path" className={buttonClasses("secondary")}>
            See growth
          </Link>
          <Link to="../tutor" relative="path" className={buttonClasses("ghost")}>
            Ask the Tutor
          </Link>
        </div>
      </Card>

      <Card title="Review your answers">
        <ol className="space-y-3">
          {session.questions.map((question, index) => (
            <li key={question.id} className="rounded-lg border border-slate-200 p-3">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-medium text-slate-900">
                  {index + 1}. {question.body}
                </p>
                {question.attempt && (
                  <Badge tone={scoreTone(question.attempt.score)}>{Math.round(question.attempt.score * 100)}%</Badge>
                )}
              </div>
              {question.attempt && <p className="mt-1 text-sm text-slate-600">{question.attempt.feedback.feedback}</p>}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
