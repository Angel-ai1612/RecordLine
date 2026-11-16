import { createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { useMemo, useState } from "react";
import { useGraph, usePassage, useSearchPassages } from "@/api/hooks";
import { useWorkspaceId } from "@/hooks/use-workspace-id";
import type { RelationshipType } from "@/api/types";
import { DocGraph } from "@/components/DocGraph";
import { PassageCard, useEvidence } from "@/components/EvidenceDrawer";
import { RelationshipPanel } from "@/components/Panels";
import { Button } from "@/components/ui/button";
import { WorkspaceEmpty, QueryState, Pipeline } from "@/components/WorkspaceState";
import { REL_LABEL } from "@/lib/format";
import { pageHead } from "@/lib/head";
export const Route = createFileRoute("/w/$workspaceId/graph")({
  head: () => pageHead("Graph", "Review document relationships, signal scores and exact evidence."),
  component: GraphPage,
});
const TYPES = Object.keys(REL_LABEL) as RelationshipType[];
function GraphPage() {
  const workspaceId = useWorkspaceId();
  const q = useGraph(workspaceId);
  const search = useSearchPassages(workspaceId);
  const { open } = useEvidence();
  const [type, setType] = useState<RelationshipType | "all">("all");
  const [min, setMin] = useState(0.4);
  const [entities, setEntities] = useState(true);
  const [selected, setSelected] = useState<{
    id: string;
    title: string;
    passages: string[];
    relationship?: boolean;
    node?: boolean;
  } | null>(null);
  const visible = useMemo(
    () =>
      new Set(
        q.data?.relationships
          .filter((r) => (type === "all" || r.type === type) && r.score >= min)
          .map((r) => r.id),
      ),
    [q.data, type, min],
  );
  if (q.isLoading || q.error)
    return (
      <div className="workbench-page">
        <QueryState query={q} />
      </div>
    );
  if (!q.data?.documents.length)
    return (
      <div className="workbench-page">
        <h1>Graph</h1>
        <WorkspaceEmpty title="No document graph yet" />
      </div>
    );
  const graph = q.data;
  return (
    <div>
      <div className="flex flex-wrap items-center gap-4 border-b border-hairline bg-card px-5 py-3">
        <label className="flex gap-2 items-center text-xs">
          Relationship
          <select
            value={type}
            onChange={(e) => setType(e.target.value as RelationshipType | "all")}
          >
            <option value="all">All types</option>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {REL_LABEL[t]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex gap-2 items-center text-xs">
          Minimum score
          <input
            className="w-24 accent-primary"
            type="range"
            min="0"
            max="1"
            step=".01"
            value={min}
            onChange={(e) => setMin(Number(e.target.value))}
          />
          <span className="w-8 font-mono">{Math.round(min * 100)}</span>
        </label>
        <label className="flex gap-2 items-center text-xs">
          <input
            type="checkbox"
            checked={entities}
            onChange={(e) => setEntities(e.target.checked)}
          />
          Entities
        </label>
        <span className="ml-auto font-mono text-xs text-muted-foreground">
          {visible.size} links
        </span>
      </div>
      <div className="graph-workarea grid min-h-[calc(100svh-138px)] grid-cols-1 xl:grid-cols-[minmax(0,1fr)_340px]">
        <section className="graph-canvas relative min-h-[540px]">
          <DocGraph
            graph={graph}
            visibleRelIds={visible}
            showEntities={entities}
            selectedId={selected?.id ?? null}
            onSelectRel={(r) =>
              setSelected({
                id: r.id,
                title: REL_LABEL[r.type],
                passages: r.evidencePassageIds,
                relationship: true,
              })
            }
            onSelectDoc={(d) => {
              const ids = graph.relationships
                .filter((r) => r.sourceDocId === d.id || r.targetDocId === d.id)
                .flatMap((r) => r.evidencePassageIds);
              setSelected({ id: d.id, title: d.filename, passages: [...new Set(ids)], node: true });
            }}
            onSelectEntity={async (e) => {
              setSelected({ id: e.id, title: e.name, passages: [] });
              try {
                const hits = await search.mutateAsync(e.name);
                setSelected((s) =>
                  s?.id === e.id ? { ...s, passages: hits.map((h) => h.passage.id) } : s,
                );
              } catch {
                /* Search error is shown in the inspector. */
              }
            }}
          />
          <div className="absolute bottom-4 left-5 font-mono text-[10px] text-muted-foreground">
            Dashed: suggested · Solid: confirmed · Amber: conflict
          </div>
        </section>
        <aside className="graph-inspector overflow-y-auto border-l border-hairline bg-card p-5">
          <p className="eyebrow mb-4">Inspector</p>
          {selected ? (
            <motion.div
              key={selected.id}
              {...(selected.node ? { layoutId: `node-${selected.id}` } : {})}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <h2 className="mb-4 break-all text-lg">{selected.title}</h2>
              {selected.relationship && <RelationshipPanel id={selected.id} />}
              {search.isPending && <div className="skeleton h-20" />}
              {search.error && <p className="text-destructive">Could not search evidence.</p>}
              <p className="eyebrow my-4">Evidence</p>
              <div className="grid gap-3">
                {selected.passages.map((id) => (
                  <InspectorEvidence
                    key={id}
                    passageId={id}
                    title={selected.title}
                    documentId={selected.node ? selected.id : null}
                  />
                ))}
              </div>
              {!selected.passages.length && !search.isPending && (
                <p className="text-sm text-muted-foreground">No extracted passages attached.</p>
              )}
            </motion.div>
          ) : (
            <p className="text-sm text-muted-foreground">No selection</p>
          )}
          <Pipeline />
          <div className="mt-5 border-t border-hairline pt-4">
            <p className="eyebrow mb-2">Relationships</p>
            {graph.relationships
              .filter((r) => visible.has(r.id))
              .map((r) => (
                <Button
                  variant="ghost"
                  key={r.id}
                  className="flex w-full justify-between px-0"
                  onClick={() =>
                    setSelected({
                      id: r.id,
                      title: REL_LABEL[r.type],
                      passages: r.evidencePassageIds,
                      relationship: true,
                    })
                  }
                >
                  <span>{REL_LABEL[r.type]}</span>
                  <span className="font-mono text-xs">{Math.round(r.score * 100)}</span>
                </Button>
              ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
function InspectorEvidence({
  passageId,
  title,
  documentId,
}: {
  passageId: string;
  title: string;
  documentId: string | null;
}) {
  const q = usePassage(useWorkspaceId(), passageId);
  const { open } = useEvidence();
  if (q.isLoading) return <div className="skeleton h-20" />;
  if (documentId && q.data && q.data.documentId !== documentId) return null;
  return (
    <div>
      <PassageCard passageId={passageId} />
      <Button
        variant="link"
        size="sm"
        className="mt-1"
        onClick={() => open({ title, passageIds: [passageId] })}
      >
        Open evidence
      </Button>
    </div>
  );
}
