import { createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { useAuditTrail } from "@/api/hooks";
import { useWorkspaceId } from "@/hooks/use-workspace-id";
import { QueryState, WorkspaceEmpty, Pipeline } from "@/components/WorkspaceState";
import { pageHead } from "@/lib/head";
export const Route = createFileRoute("/w/$workspaceId/audit")({
  head: () => pageHead("Audit", "Workspace review history for links and conflicts."),
  component: Audit,
});
function Audit() {
  const q = useAuditTrail(useWorkspaceId());
  return (
    <div className="workbench-page">
      <h1>Audit</h1>
      <Pipeline />
      <div className="mt-5">
        <QueryState query={q} />
        {q.data?.length ? (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Who</th>
                  <th>Item</th>
                  <th>Decision</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {q.data.map((a, i) => (
                  <motion.tr
                    key={a.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.04 }}
                  >
                    <td className="whitespace-nowrap font-mono text-xs">
                      {a.createdAt.slice(0, 16).replace("T", " ")}
                    </td>
                    <td>{a.actor}</td>
                    <td className="font-mono text-xs">
                      {a.targetType} {a.targetId}
                    </td>
                    <td className={a.action === "rejected" ? "text-destructive" : "text-primary"}>
                      {a.action}
                    </td>
                    <td className="text-muted-foreground">{a.note ?? ""}</td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          !q.isLoading && !q.error && <WorkspaceEmpty title="No review decisions yet" />
        )}
      </div>
    </div>
  );
}
