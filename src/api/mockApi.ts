import type { DocTraceApi } from "./client";
import type { Answer, Document, FileType } from "./types";
import * as seed from "./mockData";
import { uploadError } from "../lib/validation";

// In memory state, cloned from the seed so reviews and uploads persist for the session.
const db = {
  workspaces: seed.workspaces.map((w) => ({ ...w, name: "Sample project (demo data)" })),
  documents: seed.documents.map((d) => ({ ...d })),
  relationships: seed.relationships.map((r) => ({ ...r })),
  conflicts: seed.conflicts.map((c) => ({ ...c })),
  audit: [...seed.audit],
  uploads: new Map<string, { startedAt: number; isImage: boolean; fail: boolean }>(),
};

const wait = (ms = 450) => new Promise((r) => setTimeout(r, ms));

// Simulates the backend pipeline so polling sees status move over time.
function advance(doc: Document): Document {
  const u = db.uploads.get(doc.id);
  if (!u) return doc;
  const t = (Date.now() - u.startedAt) / 1000;
  const stages: Document["status"][] = u.isImage
    ? ["queued", "extracting", "ocr", "analyzing", "ready"]
    : ["queued", "extracting", "analyzing", "ready"];
  let status: Document["status"] =
    stages[Math.min(stages.length - 1, Math.floor(t / 2))] ?? "ready";
  if (u.fail && status === "analyzing") status = "failed";
  doc.status = status;
  return doc;
}

function typeOf(name: string): FileType {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "pdf") return "pdf";
  if (ext === "doc" || ext === "docx") return "docx";
  if (ext === "xlsx") return "xlsx";
  return "image";
}

function notFound(what: string): never {
  throw new Error(`${what} not found`);
}

export const mockApi: DocTraceApi = {
  async listWorkspaces() {
    await wait();
    return db.workspaces;
  },
  async createWorkspace(name) {
    await wait();
    const clean = name.trim();
    if (!clean) throw new Error("Enter a workspace name.");
    if (db.workspaces.some((w) => w.name.toLowerCase() === clean.toLowerCase()))
      throw new Error("A workspace with this name already exists.");
    const ws = {
      id: `ws-${crypto.randomUUID()}`,
      name: clean,
      createdAt: new Date().toISOString(),
    };
    db.workspaces.push(ws);
    return ws;
  },
  async uploadDocument(workspaceId, file, onProgress) {
    if (!db.workspaces.some((w) => w.id === workspaceId)) notFound("Workspace");
    const error = uploadError(file);
    if (error) throw new Error(error);
    for (let i = 1; i <= 10; i++) {
      await wait(120);
      onProgress?.(i / 10);
    }
    const doc: Document = {
      id: `doc-${Date.now()}-${Math.floor(performance.now())}`,
      workspaceId,
      filename: file.name,
      fileType: typeOf(file.name),
      status: "queued",
      uploadedAt: new Date().toISOString(),
      fileDate: file.lastModified ? new Date(file.lastModified).toISOString().slice(0, 10) : null,
    };
    db.uploads.set(doc.id, {
      startedAt: Date.now(),
      isImage: doc.fileType === "image",
      fail: file.size > 25 * 1024 * 1024,
    });
    db.documents.push(doc);
    return { ...doc };
  },
  async listDocuments(ws) {
    await wait(700);
    return db.documents.filter((d) => d.workspaceId === ws).map((d) => ({ ...advance(d) }));
  },
  async getDocument(id) {
    await wait(200);
    const d = db.documents.find((x) => x.id === id) ?? notFound("Document");
    return { ...advance(d) };
  },
  async getPassage(id) {
    await wait(250);
    return seed.passages.find((p) => p.id === id) ?? notFound("Passage");
  },
  async searchPassages(ws, query) {
    await wait();
    const terms = query
      .toLowerCase()
      .split(/\W+/)
      .filter((t) => t.length > 2);
    const ids = new Set(db.documents.filter((d) => d.workspaceId === ws).map((d) => d.id));
    return seed.passages
      .filter((p) => ids.has(p.documentId))
      .map((passage) => ({
        passage,
        score:
          terms.filter((t) => passage.text.toLowerCase().includes(t)).length /
          Math.max(terms.length, 1),
      }))
      .filter((r) => r.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 8);
  },
  async getGraph(ws) {
    await wait(800);
    return {
      documents: db.documents.filter((d) => d.workspaceId === ws).map((d) => ({ ...advance(d) })),
      entities: seed.entities.filter((e) =>
        e.documentIds.some((id) => db.documents.some((d) => d.id === id && d.workspaceId === ws)),
      ),
      relationships: db.relationships
        .filter((r) => db.documents.some((d) => d.id === r.sourceDocId && d.workspaceId === ws))
        .map((r) => ({ ...r })),
    };
  },
  async reviewRelationship(id, status) {
    await wait(300);
    const r = db.relationships.find((x) => x.id === id) ?? notFound("Relationship");
    r.reviewStatus = status;
    db.audit.unshift({
      id: `aud-${Date.now()}`,
      workspaceId:
        db.documents.find((d) => d.id === r.sourceDocId)?.workspaceId ?? notFound("Workspace"),
      targetType: "relationship",
      targetId: id,
      action: status,
      actor: "You",
      createdAt: new Date().toISOString(),
    });
    return { ...r };
  },
  async listConflicts(ws) {
    await wait(650);
    return db.conflicts
      .map((c) => ({
        ...c,
        facts: seed.facts.filter(
          (f) =>
            c.factIds.includes(f.id) &&
            db.documents.some((d) => d.id === f.documentId && d.workspaceId === ws),
        ),
      }))
      .filter((c) => c.facts.length > 0);
  },
  async reviewConflict(id, status) {
    await wait(300);
    const c = db.conflicts.find((x) => x.id === id) ?? notFound("Conflict");
    c.reviewStatus = status;
    db.audit.unshift({
      id: `aud-${Date.now()}`,
      workspaceId:
        db.documents.find((d) => d.id === seed.facts.find((f) => f.id === c.factIds[0])?.documentId)
          ?.workspaceId ?? notFound("Workspace"),
      targetType: "conflict",
      targetId: id,
      action: status,
      actor: "You",
      createdAt: new Date().toISOString(),
    });
    return { ...c };
  },
  async getTimeline(ws) {
    await wait(600);
    return seed.timeline
      .filter((e) => db.documents.some((d) => d.id === e.documentId && d.workspaceId === ws))
      .sort((a, b) => a.eventDate.localeCompare(b.eventDate));
  },
  async askQuestion(ws, question): Promise<Answer> {
    await wait(1400);
    if (ws !== seed.WS)
      return {
        text: "No extracted passage in this workspace answers that question.",
        citations: [],
        ambiguityNote: "Demo uploads simulate processing only. They do not extract file contents.",
      };
    const q = question.toLowerCase();
    if (q.includes("budget") || q.includes("cost") || q.includes("money")) {
      return {
        text: "Two budget figures appear. The proposal sets the budget at 50,000 INR [1], and the final report repeats 50,000 INR [2]. The meeting notes record a proposal to raise it to 65,000 INR [3], and the budget spreadsheet totals 65,000 INR in cell Summary!B12 [4].",
        citations: [
          { passageId: "pas-prop-budget", documentId: "doc-proposal" },
          { passageId: "pas-report-budget", documentId: "doc-report" },
          { passageId: "pas-notes-budget", documentId: "doc-notes" },
          { passageId: "pas-budget-total", documentId: "doc-budget" },
        ],
        ambiguityNote:
          "The increase to 65,000 INR is recorded only as proposed. No document shows it was approved, so the sources disagree and a person should decide which figure applies.",
      };
    }
    if (q.includes("deadline") || q.includes("due") || q.includes("submit")) {
      return {
        text: "The proposal gives a submission deadline of 20 November 2026 [1], repeated in the final report [2]. The meeting notes mention a discussion about 25 November [3].",
        citations: [
          { passageId: "pas-prop-deadline", documentId: "doc-proposal" },
          { passageId: "pas-report-deadline", documentId: "doc-report" },
          { passageId: "pas-notes-deadline", documentId: "doc-notes" },
        ],
        ambiguityNote:
          "The 25 November date was only discussed. No document confirms an extension.",
      };
    }
    const hits = await mockApi.searchPassages(ws, question);
    if (!hits.length)
      return { text: "No passage in this workspace answers that question.", citations: [] };
    const top = hits.slice(0, 2);
    return {
      text: `The closest matching passages are ${top.map((_, i) => `[${i + 1}]`).join(" and ")}. Read them directly, this answer only points to where the topic appears.`,
      citations: top.map((h) => ({ passageId: h.passage.id, documentId: h.passage.documentId })),
      ambiguityNote: "This match is based on shared words only and may not answer the question.",
    };
  },
  async getAuditTrail(ws) {
    await wait(500);
    return db.audit.filter((a) => a.workspaceId === ws);
  },
};
