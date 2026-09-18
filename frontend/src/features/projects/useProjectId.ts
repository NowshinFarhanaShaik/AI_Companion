import { useParams } from "react-router-dom";

export function useProjectId(): string {
  const { projectId } = useParams();
  if (!projectId) throw new Error("useProjectId must be used inside a /projects/:projectId route");
  return projectId;
}
