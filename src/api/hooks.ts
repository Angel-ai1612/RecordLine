import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { Document, ID, ReviewStatus } from "./types";

const busy = (d: Document) => d.status !== "ready" && d.status !== "failed";
const POLL_MS = 1500;

export const keys = {
  workspaces: ["workspaces"] as const,
  documents: (ws: ID) => ["documents", ws] as const,
  document: (id: ID) => ["document", id] as const,
  passage: (id: ID) => ["passage", id] as const,
  graph: (ws: ID) => ["graph", ws] as const,
  conflicts: (ws: ID) => ["conflicts", ws] as const,
  timeline: (ws: ID) => ["timeline", ws] as const,
  audit: (ws: ID) => ["audit", ws] as const,
};

export function useWorkspaces() {
  return useQuery({ queryKey: keys.workspaces, queryFn: () => api.listWorkspaces() });
}

/** Polls while any document is still processing so the backend drives status. */
export function useDocuments(ws: ID) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: keys.documents(ws),
    queryFn: () => api.listDocuments(ws),
    refetchInterval: (q) => (q.state.data?.some(busy) ? POLL_MS : false),
  });
  const statuses = query.data?.map((d) => `${d.id}:${d.status}`).join("|");
  useEffect(() => {
    if (!statuses) return;
    for (const key of [keys.graph(ws), keys.conflicts(ws), keys.timeline(ws), keys.audit(ws)])
      qc.invalidateQueries({ queryKey: key });
  }, [statuses, ws, qc]);
  return query;
}

export function useDocument(ws: ID, id: ID | undefined) {
  return useQuery({
    queryKey: [...keys.document(id ?? ""), ws],
    queryFn: () => {
      if (!id) throw new Error("Document ID required");
      return api.getDocument(id);
    },
    enabled: !!id,
  });
}

export function usePassage(ws: ID, id: ID | undefined) {
  return useQuery({
    queryKey: [...keys.passage(id ?? ""), ws],
    queryFn: () => {
      if (!id) throw new Error("Passage ID required");
      return api.getPassage(id);
    },
    enabled: !!id,
    staleTime: Infinity,
  });
}

export function useGraph(ws: ID) {
  return useQuery({
    queryKey: keys.graph(ws),
    queryFn: () => api.getGraph(ws),
    refetchInterval: (q) => (q.state.data?.documents.some(busy) ? POLL_MS : false),
  });
}

export function useConflicts(ws: ID) {
  return useQuery({ queryKey: keys.conflicts(ws), queryFn: () => api.listConflicts(ws) });
}

export function useTimeline(ws: ID) {
  return useQuery({ queryKey: keys.timeline(ws), queryFn: () => api.getTimeline(ws) });
}

export function useAuditTrail(ws: ID) {
  return useQuery({ queryKey: keys.audit(ws), queryFn: () => api.getAuditTrail(ws) });
}

export function useAsk(ws: ID) {
  return useMutation({ mutationFn: (question: string) => api.askQuestion(ws, question) });
}

export function useUpload(ws: ID) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, onProgress }: { file: File; onProgress?: (f: number) => void }) =>
      api.uploadDocument(ws, file, onProgress),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.documents(ws) });
      qc.invalidateQueries({ queryKey: keys.graph(ws) });
    },
  });
}

export function useReviewRelationship(ws: ID) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: ID; status: ReviewStatus }) =>
      api.reviewRelationship(id, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.graph(ws) });
      qc.invalidateQueries({ queryKey: keys.audit(ws) });
    },
  });
}

export function useReviewConflict(ws: ID) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: ID; status: ReviewStatus }) =>
      api.reviewConflict(id, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.conflicts(ws) });
      qc.invalidateQueries({ queryKey: keys.audit(ws) });
    },
  });
}

/** Passage search, triggered on demand (for example clicking an entity node). */
export function useSearchPassages(ws: ID) {
  return useMutation({ mutationFn: (query: string) => api.searchPassages(ws, query) });
}

export function useCreateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.createWorkspace(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.workspaces }),
  });
}
