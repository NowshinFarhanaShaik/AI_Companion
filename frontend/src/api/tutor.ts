import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Paginated } from "./client";
import type { Conversation, TutorMessage } from "./types";

export function useConversations(projectId: string) {
  return useQuery({
    queryKey: ["tutor", "conversations", projectId],
    queryFn: () => api.get<Paginated<Conversation>>(`/projects/${projectId}/conversations`),
  });
}

export function useCreateConversation(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<Conversation>(`/projects/${projectId}/conversations`, { title: "" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tutor", "conversations", projectId] }),
  });
}

export function useMessages(conversationId: string | null) {
  return useQuery({
    queryKey: ["tutor", "messages", conversationId],
    queryFn: () => api.get<Paginated<TutorMessage>>(`/conversations/${conversationId}/messages`, { limit: 100 }),
    enabled: conversationId !== null,
  });
}

export function useSendMessage(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ conversationId, text }: { conversationId: string; text: string }) =>
      api.post<TutorMessage>(`/conversations/${conversationId}/messages`, { text }),
    // The first message also gives the conversation its title, so both lists refresh.
    onSettled: (_data, _error, { conversationId }) =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tutor", "messages", conversationId] }),
        queryClient.invalidateQueries({ queryKey: ["tutor", "conversations", projectId] }),
      ]),
  });
}
