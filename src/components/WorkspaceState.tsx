import { Link } from "@tanstack/react-router";
import { useDocuments } from "@/api/hooks";
import { useWorkspaceId } from "@/hooks/use-workspace-id";
import { SkeletonRows, ErrorState } from "./States";
import { STATUS_LABEL } from "@/lib/format";
import { motion } from "framer-motion";
export function WorkspaceEmpty({ title }: { title: string }) {
  const workspaceId = useWorkspaceId();
  const docs = useDocuments(workspaceId);
  return (
    <div className="py-10">
      <h2>{title}</h2>
      <p className="mt-2 text-muted-foreground">
        {docs.data?.length
          ? "No extracted results are available yet."
          : "Upload documents to start analysis."}
      </p>
      <Pipeline />
      <Link
        className="btn btn-primary mt-5"
        to="/w/$workspaceId/documents"
        params={{ workspaceId }}
      >
        Documents
      </Link>
    </div>
  );
}
export function Pipeline() {
  const docs = useDocuments(useWorkspaceId());
  const pending = docs.data?.filter((d) => d.status !== "ready" && d.status !== "failed") ?? [];
  if (!pending.length) return null;
  return (
    <div className="my-4 border border-hairline bg-card p-3" role="status">
      {pending.map((d) => (
        <div key={d.id} className="flex items-center justify-between gap-4 py-1">
          <span className="truncate">{d.filename}</span>
          <span className="font-mono text-xs text-warning">{STATUS_LABEL[d.status]}</span>
        </div>
      ))}
      <motion.div
        className="mt-2 h-0.5 bg-primary"
        initial={{ scaleX: 0 }}
        animate={{ scaleX: [0.2, 0.8, 0.2] }}
        transition={{ duration: 3, repeat: Infinity }}
      />
    </div>
  );
}
export function QueryState({
  query,
}: {
  query: { isLoading: boolean; error: unknown; refetch: () => unknown };
}) {
  if (query.isLoading) return <SkeletonRows />;
  if (query.error) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  return null;
}
