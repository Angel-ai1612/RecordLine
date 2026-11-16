// MedSaathi demo workspace. Only src/api/mockApi.ts may import this file.
import type {
  AuditEntry,
  Conflict,
  Document,
  Entity,
  Fact,
  Passage,
  Relationship,
  TimelineEvent,
  Workspace,
} from "./types";

export const WS = "ws-medsaathi";

export const workspaces: Workspace[] = [{ id: WS, name: "Sample project (demo data)", createdAt: "2026-10-01T09:00:00Z" }];

export const documents: Document[] = [
  { id: "doc-proposal", workspaceId: WS, filename: "Project_Final.pdf", fileType: "pdf", status: "ready", uploadedAt: "2026-10-14T10:02:00Z", fileDate: "2026-10-01" },
  { id: "doc-notes", workspaceId: WS, filename: "meeting_notes.docx", fileType: "docx", status: "ready", uploadedAt: "2026-10-14T10:02:10Z", fileDate: "2026-10-05" },
  { id: "doc-budget", workspaceId: WS, filename: "budget_v3.xlsx", fileType: "xlsx", status: "ready", uploadedAt: "2026-10-14T10:02:20Z", fileDate: "2026-10-08" },
  { id: "doc-receipt", workspaceId: WS, filename: "IMG_2041.jpg", fileType: "image", status: "ready", uploadedAt: "2026-10-14T10:02:30Z", fileDate: "2026-10-09" },
  { id: "doc-report", workspaceId: WS, filename: "final_report_revised.pdf", fileType: "pdf", status: "ready", uploadedAt: "2026-10-14T10:02:40Z", fileDate: "2026-10-12" },
];

function p(id: string, documentId: string, text: string, span: string, locator: Passage["locator"], ocrConfidence?: number): Passage {
  const start = text.indexOf(span);
  return { id, documentId, text, locator, ocrConfidence, highlight: start >= 0 ? [start, start + span.length] : undefined };
}

export const passages: Passage[] = [
  p("pas-prop-budget", "doc-proposal", "Section 4. Budget. The MedSaathi pilot requests a total budget of 50,000 INR to cover field kits, printing of patient cards and travel to two partner clinics in Pune.", "a total budget of 50,000 INR", { page: 4, paragraphId: "p4.2" }),
  p("pas-prop-deadline", "doc-proposal", "Timeline. The complete project report will be submitted to the department review committee no later than 20 November 2026.", "no later than 20 November 2026", { page: 6, paragraphId: "p6.1" }),
  p("pas-prop-team", "doc-proposal", "Project lead: Priya Nair. Field coordination: Arjun Mehta. Faculty advisor: Dr. Kavita Rao, Department of Community Health.", "Priya Nair", { page: 1, paragraphId: "p1.3" }),
  p("pas-notes-budget", "doc-notes", "Item 2. Arjun proposed raising the budget to 65,000 INR because the clinic visits now need a second round of kit purchases. Priya said she would check with Dr. Rao. No decision recorded.", "proposed raising the budget to 65,000 INR", { paragraphId: "para-07" }),
  p("pas-notes-deadline", "doc-notes", "Item 3. The group discussed extending the submission deadline to 25 November to allow time for the second clinic visit. To be raised with the committee.", "extending the submission deadline to 25 November", { paragraphId: "para-09" }),
  p("pas-notes-ref", "doc-notes", "Attendees reviewed Project_Final.pdf section 4 before discussing the budget.", "Project_Final.pdf section 4", { paragraphId: "para-02" }),
  p("pas-budget-total", "doc-budget", "Summary!B12 | Total budget | 65,000 INR", "65,000 INR", { sheet: "Summary", cell: "B12" }),
  p("pas-budget-kits", "doc-budget", "Expenses!C4 | Field kits (2 rounds) | 38,000 INR", "38,000 INR", { sheet: "Expenses", cell: "C4" }),
  p("pas-budget-print", "doc-budget", "Expenses!C5 | Printing, patient cards | 9,500 INR", "9,500 INR", { sheet: "Expenses", cell: "C5" }),
  p("pas-budget-travel", "doc-budget", "Expenses!C6 | Travel to partner clinics | 17,500 INR", "17,500 INR", { sheet: "Expenses", cell: "C6" }),
  p("pas-receipt", "doc-receipt", "SHARMA MEDICAL SUPPLIES, PUNE. 09/10/2026. Field kit x 20. Subtotal 18,000. GST 1,800. TOTAL 19,8O0 INR. Paid: MedSaathi team.", "TOTAL 19,8O0 INR", { page: 1 }, 0.62),
  p("pas-report-budget", "doc-report", "Section 3. Expenditure. The project operated within its approved budget of 50,000 INR as stated in the original proposal.", "approved budget of 50,000 INR", { page: 3, paragraphId: "p3.1" }),
  p("pas-report-deadline", "doc-report", "This report is submitted ahead of the 20 November 2026 deadline set in the proposal.", "20 November 2026", { page: 1, paragraphId: "p1.4" }),
  p("pas-report-kits", "doc-report", "Field kits were purchased from Sharma Medical Supplies on 9 October for the first clinic round.", "Sharma Medical Supplies on 9 October", { page: 3, paragraphId: "p3.4" }),
];

export const entities: Entity[] = [
  { id: "ent-medsaathi", type: "project", name: "Pilot project", documentIds: ["doc-proposal", "doc-notes", "doc-budget", "doc-report", "doc-receipt"] },
  { id: "ent-budget", type: "amount", name: "Total budget", documentIds: ["doc-proposal", "doc-notes", "doc-budget", "doc-report"] },
  { id: "ent-deadline", type: "date", name: "Submission deadline", documentIds: ["doc-proposal", "doc-notes", "doc-report"] },
  { id: "ent-priya", type: "person", name: "Priya Nair", documentIds: ["doc-proposal", "doc-notes"] },
  { id: "ent-sharma", type: "organization", name: "Sharma Medical Supplies", documentIds: ["doc-receipt", "doc-report"] },
  { id: "ent-kits", type: "item", name: "Field kits", documentIds: ["doc-budget", "doc-receipt", "doc-report"] },
];

export const relationships: Relationship[] = [
  { id: "rel-1", sourceDocId: "doc-report", targetDocId: "doc-proposal", type: "revision_of", score: 0.91, signals: { entityOverlap: 0.88, semanticSimilarity: 0.93, explicitReference: 0.95, temporalContext: 0.8 }, evidencePassageIds: ["pas-report-budget", "pas-prop-budget"], reviewStatus: "confirmed" },
  { id: "rel-2", sourceDocId: "doc-notes", targetDocId: "doc-proposal", type: "references", score: 0.84, signals: { entityOverlap: 0.76, semanticSimilarity: 0.71, explicitReference: 1, temporalContext: 0.85 }, evidencePassageIds: ["pas-notes-ref", "pas-prop-budget"], reviewStatus: "pending" },
  { id: "rel-3", sourceDocId: "doc-budget", targetDocId: "doc-notes", type: "supports", score: 0.77, signals: { entityOverlap: 0.82, semanticSimilarity: 0.69, explicitReference: 0.3, temporalContext: 0.9 }, evidencePassageIds: ["pas-budget-total", "pas-notes-budget"], reviewStatus: "pending" },
  { id: "rel-4", sourceDocId: "doc-report", targetDocId: "doc-budget", type: "contradicts", score: 0.73, signals: { entityOverlap: 0.79, semanticSimilarity: 0.64, explicitReference: 0.1, temporalContext: 0.7 }, evidencePassageIds: ["pas-report-budget", "pas-budget-total"], reviewStatus: "pending" },
  { id: "rel-5", sourceDocId: "doc-receipt", targetDocId: "doc-budget", type: "supports", score: 0.58, signals: { entityOverlap: 0.6, semanticSimilarity: 0.52, explicitReference: 0, temporalContext: 0.75 }, evidencePassageIds: ["pas-receipt", "pas-budget-kits"], reviewStatus: "pending" },
  { id: "rel-6", sourceDocId: "doc-receipt", targetDocId: "doc-report", type: "same_topic", score: 0.46, signals: { entityOverlap: 0.55, semanticSimilarity: 0.41, explicitReference: 0, temporalContext: 0.5 }, evidencePassageIds: ["pas-receipt", "pas-report-kits"], reviewStatus: "pending" },
];

export const facts: Fact[] = [
  { id: "fact-b1", documentId: "doc-proposal", passageId: "pas-prop-budget", field: "Total budget", rawValue: "50,000 INR", normalizedValue: "50000", unit: "INR", status: "stated" },
  { id: "fact-b2", documentId: "doc-notes", passageId: "pas-notes-budget", field: "Total budget", rawValue: "65,000 INR", normalizedValue: "65000", unit: "INR", status: "proposed" },
  { id: "fact-b3", documentId: "doc-budget", passageId: "pas-budget-total", field: "Total budget", rawValue: "65,000 INR", normalizedValue: "65000", unit: "INR", status: "estimated" },
  { id: "fact-b4", documentId: "doc-report", passageId: "pas-report-budget", field: "Total budget", rawValue: "50,000 INR", normalizedValue: "50000", unit: "INR", status: "stated" },
  { id: "fact-d1", documentId: "doc-proposal", passageId: "pas-prop-deadline", field: "Submission deadline", rawValue: "20 November 2026", normalizedValue: "2026-11-20", unit: null, status: "stated" },
  { id: "fact-d2", documentId: "doc-notes", passageId: "pas-notes-deadline", field: "Submission deadline", rawValue: "25 November", normalizedValue: "2026-11-25", unit: null, status: "proposed" },
  { id: "fact-d3", documentId: "doc-report", passageId: "pas-report-deadline", field: "Submission deadline", rawValue: "20 November 2026", normalizedValue: "2026-11-20", unit: null, status: "stated" },
  { id: "fact-r1", documentId: "doc-receipt", passageId: "pas-receipt", field: "Receipt total", rawValue: "19,8O0 INR", normalizedValue: "19800", unit: "INR", status: "stated" },
];

export const conflicts: Conflict[] = [
  { id: "con-budget", field: "Total budget", factIds: ["fact-b4", "fact-b3", "fact-b2", "fact-b1"], severity: "high", reviewStatus: "pending", explanation: "final_report_revised.pdf states 50,000 INR while budget_v3.xlsx totals 65,000 INR. meeting_notes.docx records 65,000 INR only as a proposal, with no approval noted. The difference may be legitimate, for example an approved increase that the report did not pick up, and needs human review." },
  { id: "con-deadline", field: "Submission deadline", factIds: ["fact-d3", "fact-d2", "fact-d1"], severity: "medium", reviewStatus: "pending", explanation: "The proposal and the final report give 20 November 2026. meeting_notes.docx records a discussion about 25 November. No document confirms an extension. The difference may be legitimate and needs human review." },
  { id: "con-receipt", field: "Receipt total", factIds: ["fact-r1", "fact-b3"], severity: "low", reviewStatus: "pending", explanation: "The receipt total on IMG_2041.jpg was read with low OCR confidence (62%). One character may be the letter O instead of zero. Check the scanned image before relying on this amount." },
];

export const timeline: TimelineEvent[] = [
  { id: "ev-1", documentId: "doc-proposal", passageId: "pas-prop-budget", eventDate: "2026-10-01", fileDate: "2026-10-01", label: "Proposal sets budget at 50,000 INR" },
  { id: "ev-2", documentId: "doc-notes", passageId: "pas-notes-budget", eventDate: "2026-10-05", fileDate: "2026-10-05", label: "Team proposes raising budget to 65,000 INR" },
  { id: "ev-3", documentId: "doc-budget", passageId: "pas-budget-total", eventDate: "2026-10-08", fileDate: "2026-10-08", label: "Spreadsheet totals 65,000 INR" },
  { id: "ev-4", documentId: "doc-receipt", passageId: "pas-receipt", eventDate: "2026-10-09", fileDate: "2026-10-09", label: "Field kits bought from Sharma Medical Supplies" },
  { id: "ev-5", documentId: "doc-report", passageId: "pas-report-budget", eventDate: "2026-10-12", fileDate: "2026-10-12", label: "Final report restates 50,000 INR" },
  { id: "ev-6", documentId: "doc-proposal", passageId: "pas-prop-deadline", eventDate: "2026-11-20", fileDate: "2026-10-01", label: "Submission deadline in proposal" },
  { id: "ev-7", documentId: "doc-notes", passageId: "pas-notes-deadline", eventDate: "2026-11-25", fileDate: "2026-10-05", label: "Extended deadline under discussion" },
];

export const audit: AuditEntry[] = [
  { id: "aud-1", workspaceId: WS, targetType: "relationship", targetId: "rel-1", action: "confirmed", actor: "Priya Nair", note: "Report is the revised proposal.", createdAt: "2026-10-14T11:20:00Z" },
];
