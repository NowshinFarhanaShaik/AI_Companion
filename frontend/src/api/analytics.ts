import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { GlobalAnalytics, ProjectAnalytics } from "./types";

export function useProjectAnalytics(projectId: string) {
  return useQuery({
    queryKey: ["analytics", "project", projectId],
    queryFn: () => api.get<ProjectAnalytics>(`/projects/${projectId}/analytics`),
  });
}

export function useGlobalAnalytics() {
  return useQuery({ queryKey: ["analytics", "global"], queryFn: () => api.get<GlobalAnalytics>("/analytics/global") });
}
