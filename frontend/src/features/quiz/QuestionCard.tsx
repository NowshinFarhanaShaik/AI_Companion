import { useState } from "react";
import type { QuizQuestion } from "../../api/types";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Textarea } from "../../components/ui/Textarea";

const DIFFICULTY_LABEL: Record<number, string> = { 1: "Recall", 2: "Explain", 3: "Apply" };

type Props = {
  question: QuizQuestion;
  submitting?: boolean;
  onSubmit?: (answer: { selected_option?: number; answer_text?: string }) => void;
};

function optionTone(question: QuizQuestion, index: number, chosen: number | null) {
  if (question.answered && question.correct_option === index) return "border-green-500 bg-green-50";
  if (chosen === index) return question.answered ? "border-red-400 bg-red-50" : "border-indigo-500 bg-indigo-50";
  return "border-slate-200 hover:border-slate-300";
}

export function QuestionCard({ question, submitting = false, onSubmit }: Props) {
  const [selected, setSelected] = useState<number | null>(null);
  const [text, setText] = useState("");
  const isMcq = question.type === "mcq";
  const chosen = question.answered ? (question.attempt?.selected_option ?? null) : selected;
  const canSubmit = isMcq ? selected !== null : text.trim().length > 0;

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge tone="blue">{question.concept_name}</Badge>
        <Badge>{DIFFICULTY_LABEL[question.difficulty]}</Badge>
        <Badge>{isMcq ? "Multiple choice" : "Open-ended"}</Badge>
      </div>
      <p className="mb-4 text-lg font-medium text-slate-900">{question.body}</p>

      {isMcq ? (
        <div role="radiogroup" aria-label="Answer options" className="space-y-2">
          {question.options.map((option, index) => (
            <button
              key={index}
              type="button"
              role="radio"
              aria-checked={chosen === index}
              disabled={question.answered || submitting}
              onClick={() => setSelected(index)}
              className={`block w-full rounded-lg border px-4 py-3 text-left text-sm transition ${optionTone(question, index, chosen)}`}
            >
              <span className="mr-2 font-semibold text-slate-500">{String.fromCharCode(65 + index)}.</span>
              {option}
            </button>
          ))}
        </div>
      ) : question.answered ? (
        <p className="whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
          {question.attempt?.answer_text}
        </p>
      ) : (
        <Textarea
          label="Your answer"
          rows={6}
          maxLength={4000}
          value={text}
          disabled={submitting}
          placeholder="Explain in your own words. Two to five sentences is enough."
          onChange={(event) => setText(event.target.value)}
        />
      )}

      {!question.answered && onSubmit && (
        <div className="mt-4 flex items-center justify-end gap-3">
          {submitting && !isMcq && <span className="text-sm text-slate-500">Evaluating your answer…</span>}
          <Button
            loading={submitting}
            disabled={!canSubmit}
            onClick={() => onSubmit(isMcq ? { selected_option: selected ?? undefined } : { answer_text: text })}
          >
            Submit answer
          </Button>
        </div>
      )}
    </Card>
  );
}
