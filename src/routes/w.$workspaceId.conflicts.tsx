import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { motion } from "framer-motion";
import { useConflicts } from "@/api/hooks";
import { useWorkspaceId } from "@/hooks/use-workspace-id";
import { PassageCard, useEvidence } from "@/components/EvidenceDrawer";
import { ConflictPanel } from "@/components/Panels";
import { StatusTag } from "@/components/Review";
import { Button } from "@/components/ui/button";
import { WorkspaceEmpty, QueryState, Pipeline } from "@/components/WorkspaceState";
import { pageHead } from "@/lib/head";
export const Route = createFileRoute("/w/$workspaceId/conflicts")({
  head: () =>
    pageHead(
      "Conflicts",
      "Compare conflicting facts side by side. DocTrace never decides which value is correct.",
    ),
  component: Conflicts,
});
function Conflicts() {
  const q = useConflicts(useWorkspaceId());
  const [id, setId] = useState<string | null>(null);
  const { open } = useEvidence();
  const selected = q.data?.find((c) => c.id === id) ?? q.data?.[0];
  if (q.isLoading || q.error)
    return (
      <div className="workbench-page">
        <QueryState query={q} />
      </div>
    );
  if (!selected)
    return (
      <div className="workbench-page">
        <h1>Conflicts</h1>
        <WorkspaceEmpty title="No conflicts found" />
      </div>
    );
  const first = selected.facts[0];
  const other = selected.facts.find((f) => f.normalizedValue !== first?.normalizedValue);
  const pair = first && other ? [first, other] : selected.facts.slice(0, 2);
  return (
    <div>
      <div className="border-b border-hairline px-5 py-3 text-sm text-muted-foreground">
        DocTrace flags differing values. The system does not decide which value is correct.
      </div>
      <div className="grid min-h-[calc(100svh-103px)] grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)]">
        <nav className="border-r border-hairline bg-card p-3">
          {q.data?.map((c) => (
            <Button
              key={c.id}
              variant="ghost"
              className={`mb-1 h-auto w-full flex-col items-start gap-3 whitespace-normal border p-3 text-left ${selected.id === c.id ? "border-primary bg-secondary" : "border-transparent"}`}
              onClick={() => setId(c.id)}
            >
              <span className="flex w-full justify-between gap-2">
                <span>{c.field}</span>
                <span className="font-mono text-xs text-warning">{c.severity}</span>
              </span>
              <StatusTag status={c.reviewStatus} />
            </Button>
          ))}
        </nav>
        <motion.section
          key={selected.id}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="min-w-0 p-5"
        >
          <div className="mb-5 flex items-center justify-between">
            <h1>{selected.field}</h1>
            <StatusTag status={selected.reviewStatus} />
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            {pair.map((f) => (
              <div key={f.id}>
                <div className="mb-2 flex justify-between font-mono text-xs">
                  <span>{f.rawValue}</span>
                  <span className="text-muted-foreground">{f.status}</span>
                </div>
                <PassageCard passageId={f.passageId} />
              </div>
            ))}
          </div>
          <Button
            variant="link"
            className="my-3 px-0"
            onClick={() =>
              open({
                title: selected.field,
                passageIds: pair.map((f) => f.passageId),
                extra: <ConflictPanel id={selected.id} />,
              })
            }
          >
            Open both sources
          </Button>
          <ConflictPanel id={selected.id} />
          <Pipeline />
        </motion.section>
      </div>
    </div>
  );
}
