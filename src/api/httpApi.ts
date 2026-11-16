import type { DocTraceApi } from "./client";
import type { Document } from "./types";

export function createHttpApi(baseUrl: string): DocTraceApi {
  const root = baseUrl.replace(/\/$/, "");

  async function req<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${root}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers as Record<string, string> | undefined) },
    });
    if (!res.ok) throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status}`);
    return (await res.json()) as T;
  }

  return {
    listWorkspaces: () => req("/workspaces"),
    createWorkspace: (name) => req("/workspaces", { method: "POST", body: JSON.stringify({ name }) }),
    uploadDocument: (workspaceId, file, onProgress) =>
      new Promise<Document>((resolve, reject) => {
        // XMLHttpRequest is used here because fetch has no upload progress events.
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${root}/workspaces/${workspaceId}/documents`);
        xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
        xhr.onload = () =>
          xhr.status < 300 ? resolve(JSON.parse(xhr.responseText)) : reject(new Error(`Upload failed: ${xhr.status}`));
        xhr.onerror = () => reject(new Error("Upload failed: network error"));
        const form = new FormData();
        form.append("file", file);
        xhr.send(form);
      }),
    listDocuments: (ws) => req(`/workspaces/${ws}/documents`),
    getDocument: (id) => req(`/documents/${id}`),
    getPassage: (id) => req(`/passages/${id}`),
    searchPassages: (ws, q) => req(`/workspaces/${ws}/passages/search?q=${encodeURIComponent(q)}`),
    getGraph: (ws) => req(`/workspaces/${ws}/graph`),
    reviewRelationship: (id, status) =>
      req(`/relationships/${id}`, { method: "PATCH", body: JSON.stringify({ reviewStatus: status }) }),
    listConflicts: (ws) => req(`/workspaces/${ws}/conflicts`),
    reviewConflict: (id, status) =>
      req(`/conflicts/${id}`, { method: "PATCH", body: JSON.stringify({ reviewStatus: status }) }),
    getTimeline: (ws) => req(`/workspaces/${ws}/timeline`),
    askQuestion: (ws, question) => req(`/workspaces/${ws}/ask`, { method: "POST", body: JSON.stringify({ question }) }),
    getAuditTrail: (ws) => req(`/workspaces/${ws}/audit`),
  };
}
