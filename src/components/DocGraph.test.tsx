import { fireEvent, render, screen } from "@testing-library/react";
import { createElement, type ComponentType, type ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import type { Graph } from "@/api/types";

vi.mock("@xyflow/react", () => ({
  BaseEdge: () => null,
  EdgeLabelRenderer: ({ children }: { children: ReactNode }) => children,
  Handle: () => null,
  Position: { Left: "left", Right: "right", Top: "top", Bottom: "bottom" },
  ReactFlowProvider: ({ children }: { children: ReactNode }) => children,
  getBezierPath: () => ["", 0, 0],
  ReactFlow: ({
    nodes,
    edges,
    nodeTypes,
    edgeTypes,
  }: {
    nodes: TestItem[];
    edges: TestItem[];
    nodeTypes: Record<string, ComponentType<{ data: unknown }>>;
    edgeTypes: Record<string, ComponentType<{ id: string; data: unknown }>>;
  }) => (
    <div>
      {nodes.map((node) => createElement(nodeTypes[node.type]!, { key: node.id, data: node.data }))}
      {edges
        .filter((edge) => edge.type === "rel")
        .map((edge) =>
          createElement(edgeTypes[edge.type]!, { key: edge.id, id: edge.id, data: edge.data }),
        )}
    </div>
  ),
}));

type TestItem = {
  id: string;
  type: string;
  data: unknown;
};

import { DocGraph } from "./DocGraph";

const graph: Graph = {
  documents: [
    {
      id: "doc-proposal",
      workspaceId: "ws-test",
      filename: "proposal.pdf",
      fileType: "pdf",
      status: "ready",
      uploadedAt: "2026-11-03T00:00:00Z",
      fileDate: "2026-11-03",
    },
    {
      id: "doc-notes",
      workspaceId: "ws-test",
      filename: "notes.docx",
      fileType: "docx",
      status: "ready",
      uploadedAt: "2026-11-07T00:00:00Z",
      fileDate: "2026-11-07",
    },
  ],
  entities: [
    {
      id: "entity-project",
      type: "project",
      name: "MS-2026-01",
      documentIds: ["doc-proposal", "doc-notes"],
    },
  ],
  relationships: [
    {
      id: "rel-reference",
      sourceDocId: "doc-notes",
      targetDocId: "doc-proposal",
      type: "references",
      score: 0.82,
      signals: {
        entityOverlap: 1,
        semanticSimilarity: 0.7,
        explicitReference: 1,
        temporalContext: 0.9,
      },
      evidencePassageIds: ["passage-notes", "passage-proposal"],
      reviewStatus: "pending",
    },
  ],
};

describe("DocGraph keyboard inspection", () => {
  it("activates document, entity, and relationship inspectors with the keyboard", () => {
    const onSelectDoc = vi.fn();
    const onSelectEntity = vi.fn();
    const onSelectRel = vi.fn();
    render(
      <DocGraph
        graph={graph}
        onSelectDoc={onSelectDoc}
        onSelectEntity={onSelectEntity}
        onSelectRel={onSelectRel}
      />,
    );

    const documentControl = screen.getByRole("button", {
      name: /Document proposal\.pdf, Ready\. Inspect evidence/i,
    });
    const entityControl = screen.getByRole("button", {
      name: /project entity MS-2026-01\. Inspect evidence/i,
    });
    const relationshipControl = screen.getByRole("button", {
      name: /References relationship from notes\.docx to proposal\.pdf, score 82 percent\. Inspect evidence/i,
    });

    documentControl.focus();
    fireEvent.keyDown(documentControl, { key: "Enter" });
    entityControl.focus();
    fireEvent.keyDown(entityControl, { key: " " });
    relationshipControl.focus();
    fireEvent.keyDown(relationshipControl, { key: "Enter" });

    expect(onSelectDoc).toHaveBeenCalledWith(graph.documents[0]);
    expect(onSelectEntity).toHaveBeenCalledWith(graph.entities[0]);
    expect(onSelectRel).toHaveBeenCalledWith(graph.relationships[0]);
  });
});
