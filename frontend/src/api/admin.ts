import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Paginated } from "./client";
import type {
  AdminActivityFilters,
  AdminActivityRow,
  AdminAIUsage,
  AdminEvalRun,
  AdminHealth,
  AdminJob,
  AdminJobsSummary,
  AdminOverview,
  AdminUserDetail,
  AdminUserRow,
} from "./types";

export function useAdminOverview() {
  return useQuery({ queryKey: ["admin", "overview"], queryFn: () => api.get<AdminOverview>("/admin/overview") });
}

export function useAdminUsers(params: { q?: string; limit: number; offset: number }) {
  return useQuery({
    queryKey: ["admin", "users", params],
    queryFn: () => api.get<Paginated<AdminUserRow>>("/admin/users", params),
    placeholderData: keepPreviousData,
  });
}

export function useAdminUser(userId: string | undefined) {
  return useQuery({
    queryKey: ["admin", "user", userId],
    queryFn: () => api.get<AdminUserDetail>(`/admin/users/${userId}`),
    enabled: Boolean(userId),
  });
}

export function useAdminActivity(filters: AdminActivityFilters) {
  return useQuery({
    queryKey: ["admin", "activity", filters],
    queryFn: () => api.get<Paginated<AdminActivityRow>>("/admin/activity", filters),
    placeholderData: keepPreviousData,
  });
}

export function useAdminAIUsage(days: number) {
  return useQuery({
    queryKey: ["admin", "ai-usage", days],
    queryFn: () => api.get<AdminAIUsage>("/admin/ai-usage", { days }),
    placeholderData: keepPreviousData,
  });
}

export function useAdminEvals() {
  return useQuery({ queryKey: ["admin", "evals"], queryFn: () => api.get<AdminEvalRun[]>("/admin/evals") });
}

// Jobs and health change without user action, so these poll.
export function useAdminJobs(params: { status?: string; type?: string; limit: number; offset: number }) {
  return useQuery({
    queryKey: ["admin", "jobs", "list", params],
    queryFn: () => api.get<Paginated<AdminJob>>("/admin/jobs", params),
    placeholderData: keepPreviousData,
    refetchInterval: 5000,
  });
}

export function useAdminJobsSummary() {
  return useQuery({
    queryKey: ["admin", "jobs", "summary"],
    queryFn: () => api.get<AdminJobsSummary>("/admin/jobs/summary"),
    refetchInterval: 5000,
  });
}

export function useRetryJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => api.post<AdminJob>(`/admin/jobs/${jobId}/retry`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "jobs"] }),
  });
}

export function useAdminHealth() {
  return useQuery({
    queryKey: ["admin", "health"],
    queryFn: () => api.get<AdminHealth>("/admin/health"),
    refetchInterval: 15000,
  });
}
