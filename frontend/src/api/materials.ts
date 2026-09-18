import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Paginated } from "./client";
import type { Concept, Material } from "./types";

export const isProcessing = (material: Material) => material.status === "queued" || material.status === "processing";

export function useMaterials(projectId: string) {
  return useQuery({
    queryKey: ["materials", projectId],
    queryFn: () => api.get<Paginated<Material>>(`/projects/${projectId}/materials`, { limit: 100 }),
    // Poll only while something is still being processed.
    refetchInterval: (query) => (query.state.data?.items.some(isProcessing) ? 3000 : false),
  });
}

// readyCount is part of the key, so the list refetches whenever a material finishes processing.
export function useConcepts(projectId: string, readyCount: number) {
  return useQuery({
    queryKey: ["concepts", projectId, readyCount],
    queryFn: () => api.get<Paginated<Concept>>(`/projects/${projectId}/concepts`, { limit: 100 }),
  });
}

function useMaterialMutation<TInput>(projectId: string, mutationFn: (input: TInput) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["materials", projectId] }),
  });
}

export function useUploadMaterial(projectId: string) {
  return useMaterialMutation(projectId, (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.upload<Material>(`/projects/${projectId}/materials`, form);
  });
}

export function useRetryMaterial(projectId: string) {
  return useMaterialMutation(projectId, (materialId: string) => api.post<Material>(`/materials/${materialId}/retry`));
}

export function useDeleteMaterial(projectId: string) {
  return useMaterialMutation(projectId, (materialId: string) => api.delete<void>(`/materials/${materialId}`));
}
