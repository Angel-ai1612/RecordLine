import { createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { useDocuments, useTimeline } from "@/api/hooks";
import { useWorkspaceId } from "@/hooks/use-workspace-id";
import { useEvidence } from "@/components/EvidenceDrawer";
import { Button } from "@/components/ui/button";
import { QueryState, WorkspaceEmpty, Pipeline } from "@/components/WorkspaceState";
import { fmtDate } from "@/lib/format";
import { pageHead } from "@/lib/head";
export const Route = createFileRoute("/w/$workspaceId/timeline")({
  head: () =>
    pageHead(
      "Timeline",
      "Event dates and file dates in chronological order, linked to exact sources.",
    ),
  component: Timeline,
});
function Timeline() {
  const ws = useWorkspaceId();
  const q = useTimeline(ws);
  const docs = useDocuments(ws);
  const { open } = useEvidence();
  return (
    <div className="workbench-page">
      <h1>Timeline</h1>
      <Pipeline />
      <div className="mt-5">
        <QueryState query={q} />
        {q.data?.length ? (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Event date</th>
                  <th>File date</th>
                  <th>Event</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {q.data.map((e, i) => (
                  <motion.tr
                    key={e.id}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05 }}
                  >
                    <td className="whitespace-nowrap font-mono text-xs">{fmtDate(e.eventDate)}</td>
                    <td className="whitespace-nowrap font-mono text-xs text-muted-foreground">
                      {fmtDate(e.fileDate)}
                    </td>
                    <td>{e.label}</td>
                    <td>
                      <Button
                        variant="link"
                        className="h-auto whitespace-normal px-0 text-left font-mono text-xs"
                        onClick={() => open({ title: e.label, passageIds: [e.passageId] })}
                      >
                        {docs.data?.find((d) => d.id === e.documentId)?.filename ?? e.documentId}
                      </Button>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          !q.isLoading && !q.error && <WorkspaceEmpty title="No dated events yet" />
        )}
      </div>
    </div>
  );
}
