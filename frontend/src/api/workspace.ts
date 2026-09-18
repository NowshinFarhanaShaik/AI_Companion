import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Paginated } from "./client";
import type { Project, Space } from "./types";

export function useSpaces() {
  return useQuery({ queryKey: ["spaces"], queryFn: () => api.get<Paginated<Space>>("/spaces", { limit: 100 }) });
}

export function useSpace(spaceId: string) {
  return useQuery({ queryKey: ["spaces", spaceId], queryFn: () => api.get<Space>(`/spaces/${spaceId}`) });
}

export function useCreateSpace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description: string }) => api.post<Space>("/spaces", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["spaces"] }),
  });
}

export function useProjects(spaceId: string) {
  return useQuery({
    queryKey: ["projects", "by-space", spaceId],
    queryFn: () => api.get<Paginated<Project>>(`/spaces/${spaceId}/projects`, { limit: 100 }),
  });
}

export function useProject(projectId: string) {
  return useQuery({ queryKey: ["projects", projectId], queryFn: () => api.get<Project>(`/projects/${projectId}`) });
}

export function useCreateProject(spaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description: string; learning_goal: string }) =>
      api.post<Project>(`/spaces/${spaceId}/projects`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", "by-space", spaceId] });
      queryClient.invalidateQueries({ queryKey: ["spaces"] });
    },
  });
}
