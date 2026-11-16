// Types mirror the backend tables one to one. Keep field names in sync with the FastAPI schemas.

export type ID = string;

export interface Workspace {
  id: ID;
  name: string;
  createdAt: string;
}

export type FileType = "pdf" | "docx" | "xlsx" | "image";
export type DocumentStatus = "queued" | "extracting" | "ocr" | "analyzing" | "ready" | "failed";

export interface Document {
  id: ID;
  workspaceId: ID;
  filename: string;
  fileType: FileType;
  status: DocumentStatus;
  uploadedAt: string;
  fileDate: string | null;
}

export interface Locator {
  page?: number;
  paragraphId?: string;
  sheet?: string;
  cell?: string;
}

export interface Passage {
  id: ID;
  documentId: ID;
  text: string;
  locator: Locator;
  ocrConfidence?: number | null | undefined;
  /** Optional character span [start, end) of the supporting text inside `text`. */
  highlight?: [number, number] | undefined;
}

export type EntityType = "person" | "organization" | "project" | "amount" | "date" | "item";

export interface Entity {
  id: ID;
  type: EntityType;
  name: string;
  documentIds: ID[];
}

export type ReviewStatus = "pending" | "confirmed" | "rejected";
export type RelationshipType = "revision_of" | "references" | "supports" | "contradicts" | "same_topic";

export interface RelationshipSignals {
  entityOverlap: number;
  semanticSimilarity: number;
  explicitReference: number;
  temporalContext: number;
}

export interface Relationship {
  id: ID;
  sourceDocId: ID;
  targetDocId: ID;
  type: RelationshipType;
  score: number;
  signals: RelationshipSignals;
  evidencePassageIds: ID[];
  reviewStatus: ReviewStatus;
}

export type FactStatus = "proposed" | "approved" | "estimated" | "stated";

export interface Fact {
  id: ID;
  documentId: ID;
  passageId: ID;
  field: string;
  rawValue: string;
  normalizedValue: string;
  unit: string | null;
  status: FactStatus;
}

export type Severity = "low" | "medium" | "high";

export interface Conflict {
  id: ID;
  field: string;
  factIds: ID[];
  explanation: string;
  severity: Severity;
  reviewStatus: ReviewStatus;
}

/** Conflict as returned by GET /workspaces/:id/conflicts, with its facts embedded. */
export interface ConflictWithFacts extends Conflict {
  facts: Fact[];
}

export interface TimelineEvent {
  id: ID;
  documentId: ID;
  passageId: ID;
  eventDate: string;
  fileDate: string | null;
  label: string;
}

export interface Citation {
  passageId: ID;
  documentId: ID;
}

export interface Answer {
  text: string;
  citations: Citation[];
  ambiguityNote?: string | undefined;
}

export interface AuditEntry {
  id: ID;
  workspaceId: ID;
  targetType: "relationship" | "conflict";
  targetId: ID;
  action: ReviewStatus;
  actor: string;
  note?: string | undefined;
  createdAt: string;
}

export interface Graph {
  documents: Document[];
  entities: Entity[];
  relationships: Relationship[];
}

export interface PassageSearchResult {
  passage: Passage;
  score: number;
}
