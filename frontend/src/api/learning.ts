import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Paginated } from "./client";
import type { GrowthData, HomeData, ProjectDashboard, Recommendation, SpaceDashboard } from "./types";

export function useGrowth(projectId: string) {
  return useQuery({
    queryKey: ["learning", "growth", projectId],
    queryFn: () => api.get<GrowthData>(`/projects/${projectId}/growth`),
  });
}

export function useActiveRecommendation(projectId: string) {
  return useQuery({
    queryKey: ["learning", "recommendation", projectId],
    queryFn: async () =>
      (await api.get<Paginated<Recommendation>>(`/projects/${projectId}/recommendations`, { status: "active", limit: 1 }))
        .items[0] ?? null,
  });
}

export function useCompleteRecommendation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (recommendationId: string) => api.post<Recommendation>(`/recommendations/${recommendationId}/complete`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["learning"] }),
  });
}

export function useProjectDashboard(projectId: string) {
  return useQuery({
    queryKey: ["learning", "dashboard", projectId],
    queryFn: () => api.get<ProjectDashboard>(`/projects/${projectId}/dashboard`),
  });
}

export function useSpaceDashboard(spaceId: string) {
  return useQuery({
    queryKey: ["learning", "space-dashboard", spaceId],
    queryFn: () => api.get<SpaceDashboard>(`/spaces/${spaceId}/dashboard`),
  });
}

export function useHome() {
  return useQuery({ queryKey: ["learning", "home"], queryFn: () => api.get<HomeData>("/home") });
}
