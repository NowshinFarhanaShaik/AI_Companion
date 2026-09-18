import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Paginated } from "./client";
import type { AnswerResponse, NextQuestionResponse, QuizSession } from "./types";

const sessionKey = (sessionId: string | null) => ["quiz", "session", sessionId];

export function useConceptCount(projectId: string) {
  return useQuery({
    queryKey: ["quiz", "concept-count", projectId],
    queryFn: async () => (await api.get<Paginated<unknown>>(`/projects/${projectId}/concepts`, { limit: 1 })).count,
  });
}

export function useQuizSession(sessionId: string | null) {
  return useQuery({
    queryKey: sessionKey(sessionId),
    queryFn: () => api.get<QuizSession>(`/quiz-sessions/${sessionId}`),
    enabled: sessionId !== null,
  });
}

// Starting a quiz also fetches its first question, so the learner lands on a question straight away.
// If that first question fails, the session still opens and offers "Next question" to retry it, instead of
// leaving an empty session behind and creating another one on the next attempt.
export function useStartQuiz(projectId: string) {
  return useMutation({
    mutationFn: async (targetQuestionCount: number) => {
      const session = await api.post<QuizSession>(`/projects/${projectId}/quiz-sessions`, {
        target_question_count: targetQuestionCount,
      });
      await api.post<NextQuestionResponse>(`/quiz-sessions/${session.id}/next`).catch(() => undefined);
      return session;
    },
  });
}

// Both mutations wait for the session refetch, so the page never renders between an answer and its data.
export function useNextQuestion(sessionId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<NextQuestionResponse>(`/quiz-sessions/${sessionId}/next`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: sessionKey(sessionId) }),
  });
}

export function useSubmitAnswer(sessionId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ questionId, ...answer }: { questionId: string; selected_option?: number; answer_text?: string }) =>
      api.post<AnswerResponse>(`/questions/${questionId}/answer`, answer),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: sessionKey(sessionId) }),
  });
}
