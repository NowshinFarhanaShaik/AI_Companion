import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import type { QuizQuestion, QuizSession } from "../../api/types";
import { QuizPage } from "./QuizPage";

const state = vi.hoisted(() => ({
  session: null as unknown,
  afterAnswer: null as unknown,
  submitError: null as Error | null,
  submitted: [] as unknown[],
}));

vi.mock("../../api/quiz", () => ({
  useConceptCount: () => ({ data: 3, isLoading: false, isError: false }),
  useStartQuiz: () => ({
    mutate: (_length: number, options: { onSuccess: (session: { id: string }) => void }) =>
      options.onSuccess({ id: "session-1" }),
    isPending: false,
    isError: false,
  }),
  useQuizSession: () => ({ data: state.session, isLoading: false, isError: false }),
  useNextQuestion: () => ({ mutate: vi.fn(), isPending: false, error: null }),
  useSubmitAnswer: () => ({
    mutate: (input: unknown, options: { onSuccess: () => void }) => {
      state.submitted.push(input);
      if (state.submitError) return;
      state.session = state.afterAnswer;
      options.onSuccess();
    },
    isPending: false,
    error: state.submitError,
  }),
}));

vi.mock("../projects/useProjectId", () => ({ useProjectId: () => "project-1" }));

const question: QuizQuestion = {
  id: "question-1",
  session_id: "session-1",
  concept_id: "concept-1",
  concept_name: "Light-dependent reactions",
  type: "mcq",
  difficulty: 1,
  body: "Where do the light-dependent reactions take place?",
  options: ["Stroma", "Thylakoid membranes", "Cytoplasm", "Mitochondrial matrix"],
  answered: false,
  attempt: null,
  correct_option: null,
  explanation: null,
  key_points: null,
};

const activeSession: QuizSession = {
  id: "session-1",
  project_id: "project-1",
  status: "active",
  target_question_count: 2,
  answered_count: 0,
  completed_at: null,
  created_at: "2026-09-17T10:00:00Z",
  questions: [question],
  summary: null,
};

const answeredSession: QuizSession = {
  ...activeSession,
  answered_count: 1,
  questions: [
    {
      ...question,
      answered: true,
      correct_option: 1,
      explanation: "Photosystems sit in the thylakoid membranes.",
      attempt: {
        id: "attempt-1",
        selected_option: 1,
        answer_text: "",
        score: 1,
        evaluated_at: "2026-09-17T10:01:00Z",
        feedback: {
          understood: ["Where the light reactions happen"],
          missing: [],
          misconceptions: [],
          feedback: "Correct. Light is absorbed by the photosystems in the thylakoid membranes.",
        },
      },
    },
  ],
};

async function startQuiz() {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <QuizPage />
    </MemoryRouter>,
  );
  await user.click(screen.getByRole("button", { name: /start quiz/i }));
  await screen.findByText(question.body);
  return user;
}

beforeEach(() => {
  state.session = activeSession;
  state.afterAnswer = answeredSession;
  state.submitError = null;
  state.submitted = [];
});

describe("QuizPage", () => {
  it("submits the chosen option and shows the feedback", async () => {
    const user = await startQuiz();

    await user.click(screen.getByRole("radio", { name: /thylakoid membranes/i }));
    await user.click(screen.getByRole("button", { name: /submit answer/i }));

    expect(await screen.findByText(/Correct\. Light is absorbed/)).toBeInTheDocument();
    expect(screen.getByText("What you understood")).toBeInTheDocument();
    expect(state.submitted).toEqual([{ questionId: "question-1", selected_option: 1 }]);
    expect(screen.getByRole("button", { name: /next question/i })).toBeInTheDocument();
  });

  it("keeps Submit disabled until an option is chosen", async () => {
    await startQuiz();

    expect(screen.getByRole("button", { name: /submit answer/i })).toBeDisabled();
  });

  it("shows why a submission failed", async () => {
    state.submitError = new ApiError("Too many requests. Please wait a moment and try again.", 429, "rate_limited");
    await startQuiz();

    expect(screen.getByRole("alert")).toHaveTextContent("That didn't go through.");
    expect(screen.getByRole("alert")).toHaveTextContent("Please wait a moment");
    expect(screen.getByText(question.body)).toBeInTheDocument();
  });
});
