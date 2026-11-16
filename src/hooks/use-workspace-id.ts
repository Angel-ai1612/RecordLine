import { useParams } from "@tanstack/react-router";
export function useWorkspaceId() {
  const { workspaceId } = useParams({ strict: false });
  if (!workspaceId) throw new Error("Open a workspace first.");
  return workspaceId;
}
