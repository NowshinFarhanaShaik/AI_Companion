import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { useConceptCount, useNextQuestion, useQuizSession, useStartQuiz, useSubmitAnswer } from "../../api/quiz";
import type { QuizSession } from "../../api/types";
import { EmptyState } from "../../components/shared/EmptyState";
import { ErrorState } from "../../components/shared/ErrorState";
import { PageHeader } from "../../components/shared/PageHeader";
import { Button } from "../../components/ui/Button";
import { buttonClasses } from "../../components/ui/buttonStyles";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";
import { useProjectId } from "../projects/useProjectId";
import { FeedbackCard } from "./FeedbackCard";
import { QuestionCard } from "./QuestionCard";
import { SessionSummary } from "./SessionSummary";

const LENGTHS = [3, 5, 10];

function StartScreen({ onStarted }: { onStarted: (sessionId: string) => void }) {
  const projectId = useProjectId();
  const conceptCount = useConceptCount(projectId);
  const start = useStartQuiz(projectId);
  const [length, setLength] = useState(5);

  if (conceptCount.isLoading) return <Spinner />;
  if (conceptCount.isError) return <ErrorState error={conceptCount.error} onRetry={() => conceptCount.refetch()} />;
  const noConcepts = start.error instanceof ApiError && start.error.code === "no_concepts";
  if (conceptCount.data === 0 || noConcepts) {
    return (
      <EmptyState
        title="Upload material first"
        description="Quiz questions are written from your own documents. Upload a PDF and wait until it shows as ready."
        action={
          <Link to="../materials" relative="path" className={buttonClasses()}>
            Go to Materials
          </Link>
        }
      />
    );
  }

  return (
    <Card title="Start an adaptive quiz">
      <p className="text-sm text-slate-700">
        Questions are chosen from your {conceptCount.data} concepts using your mastery, recent mistakes and what you
        have not practised lately. You get a mix of multiple-choice and open-ended questions, with feedback after each.
      </p>
      <div className="mt-4 flex items-center gap-2" role="group" aria-label="Number of questions">
        <span className="text-sm text-slate-600">Questions:</span>
        {LENGTHS.map((option) => (
          <Button
            key={option}
            size="sm"
            variant={option === length ? "primary" : "secondary"}
            aria-pressed={option === length}
            onClick={() => setLength(option)}
          >
            {option}
          </Button>
        ))}
      </div>
      {start.isError && (
        <div className="mt-4">
          <ErrorState title="The quiz didn't start." error={start.error} onRetry={() => start.reset()} />
        </div>
      )}
      <Button
        className="mt-5"
        loading={start.isPending}
        onClick={() => start.mutate(length, { onSuccess: (session) => onStarted(session.id) })}
      >
        Start quiz
      </Button>
    </Card>
  );
}

function Progress({ session }: { session: QuizSession }) {
  const percent = (session.answered_count / session.target_question_count) * 100;
  return (
    <div>
      <p className="mb-1 flex justify-between text-xs text-slate-500">
        <span>
          {session.answered_count} of {session.target_question_count} answered
        </span>
      </p>
      <div className="h-2 rounded-full bg-slate-200">
        <div className="h-2 rounded-full bg-indigo-500 transition-all" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function ActiveSession({ sessionId, onRestart }: { sessionId: string; onRestart: () => void }) {
  const session = useQuizSession(sessionId);
  const next = useNextQuestion(sessionId);
  const submit = useSubmitAnswer(sessionId);
  const [reviewingId, setReviewingId] = useState<string | null>(null);

  if (session.isLoading) return <Spinner />;
  if (session.isError) return <ErrorState error={session.error} onRetry={() => session.refetch()} />;
  const data = session.data;
  if (!data) return null;

  const reviewing = data.questions.find((question) => question.id === reviewingId);
  if (!reviewing && data.status === "completed") return <SessionSummary session={data} onRestart={onRestart} />;
  const pending = data.questions.find((question) => !question.answered);
  const error = next.error ?? submit.error;

  return (
    <div className="space-y-4">
      <Progress session={data} />
      {reviewing ? (
        <>
          <QuestionCard question={reviewing} />
          <FeedbackCard question={reviewing} />
          <div className="flex justify-end">
            {data.status === "completed" ? (
              <Button onClick={() => setReviewingId(null)}>See results</Button>
            ) : (
              <Button
                loading={next.isPending}
                onClick={() => next.mutate(undefined, { onSuccess: () => setReviewingId(null) })}
              >
                Next question
              </Button>
            )}
          </div>
        </>
      ) : pending ? (
        <QuestionCard
          key={pending.id}
          question={pending}
          submitting={submit.isPending}
          onSubmit={(answer) =>
            submit.mutate({ questionId: pending.id, ...answer }, { onSuccess: () => setReviewingId(pending.id) })
          }
        />
      ) : (
        <Card>
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-slate-600">Ready for your next question.</p>
            <Button loading={next.isPending} onClick={() => next.mutate()}>
              Next question
            </Button>
          </div>
        </Card>
      )}
      {error && <ErrorState title="That didn't go through." error={error} />}
    </div>
  );
}

export function QuizPage() {
  const [params, setParams] = useSearchParams();
  const sessionId = params.get("session");

  return (
    <>
      <PageHeader
        title="Quiz"
        subtitle="Adaptive practice from your own material"
        actions={
          sessionId && (
            <Button variant="ghost" size="sm" onClick={() => setParams({})}>
              Leave quiz
            </Button>
          )
        }
      />
      {sessionId ? (
        <ActiveSession key={sessionId} sessionId={sessionId} onRestart={() => setParams({})} />
      ) : (
        <StartScreen onStarted={(id) => setParams({ session: id })} />
      )}
    </>
  );
}
