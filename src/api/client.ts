import type {
  Answer,
  AuditEntry,
  ConflictWithFacts,
  Document,
  Graph,
  ID,
  Passage,
  PassageSearchResult,
  Relationship,
  ReviewStatus,
  Conflict,
  TimelineEvent,
  Workspace,
} from "./types";
import { mockApi } from "./mockApi";
import { createHttpApi } from "./httpApi";

export interface DocTraceApi {
  listWorkspaces(): Promise<Workspace[]>;
  createWorkspace(name: string): Promise<Workspace>;
  uploadDocument(workspaceId: ID, file: File, onProgress?: (fraction: number) => void): Promise<Document>;
  listDocuments(workspaceId: ID): Promise<Document[]>;
  getDocument(documentId: ID): Promise<Document>;
  getPassage(passageId: ID): Promise<Passage>;
  searchPassages(workspaceId: ID, query: string): Promise<PassageSearchResult[]>;
  getGraph(workspaceId: ID): Promise<Graph>;
  reviewRelationship(relationshipId: ID, status: ReviewStatus): Promise<Relationship>;
  listConflicts(workspaceId: ID): Promise<ConflictWithFacts[]>;
  reviewConflict(conflictId: ID, status: ReviewStatus): Promise<Conflict>;
  getTimeline(workspaceId: ID): Promise<TimelineEvent[]>;
  askQuestion(workspaceId: ID, question: string): Promise<Answer>;
  getAuditTrail(workspaceId: ID): Promise<AuditEntry[]>;
}

// The single switch: set VITE_API_BASE_URL to use the real backend, leave it unset for the mock.
const baseUrl = import.meta.env['VITE_API_BASE_URL'] as string | undefined;

export const api: DocTraceApi = baseUrl ? createHttpApi(baseUrl) : mockApi;
export const usingMock = !baseUrl;
