import type { DocumentStatus, FileType, Locator, RelationshipType } from "@/api/types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function fmtDate(iso: string | null | undefined) {
  if (!iso) return "No date";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${d} ${MONTHS[(m ?? 1) - 1]} ${y}`;
}

export function fmtLocator(l: Locator) {
  const parts: string[] = [];
  if (l.sheet && l.cell) parts.push(`${l.sheet}!${l.cell}`);
  else if (l.sheet) parts.push(`sheet ${l.sheet}`);
  if (l.page) parts.push(`p. ${l.page}`);
  if (l.paragraphId) parts.push(`¶ ${l.paragraphId}`);
  return parts.join("  ·  ") || "no locator";
}

export const FILE_LABEL: Record<FileType, string> = { pdf: "PDF", docx: "Word", xlsx: "Sheet", image: "Scan" };

export const STATUS_LABEL: Record<DocumentStatus, string> = {
  queued: "Queued",
  extracting: "Extracting text",
  ocr: "Reading scan",
  analyzing: "Finding links",
  ready: "Ready",
  failed: "Failed",
};

export const PIPELINE: DocumentStatus[] = ["queued", "extracting", "ocr", "analyzing", "ready"];

export const REL_LABEL: Record<RelationshipType, string> = {
  revision_of: "Revision of",
  references: "References",
  supports: "Supports",
  contradicts: "Contradicts",
  same_topic: "Same topic",
};

export const pct = (n: number) => `${Math.round(n * 100)}%`;
