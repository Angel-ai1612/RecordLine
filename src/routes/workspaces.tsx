import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useWorkspaces, useCreateWorkspace } from "@/api/hooks";
import { SkeletonRows, ErrorState } from "@/components/States";
import { Button } from "@/components/ui/button";
import { workspaceNameError } from "@/lib/validation";
import { fmtDate } from "@/lib/format";
import { pageHead } from "@/lib/head";
import { FolderSimple, Plus, ArrowRight, MagnifyingGlass } from "@phosphor-icons/react";
export const Route = createFileRoute("/workspaces")({
  head: () => pageHead("Workspaces", "Create and open document analysis workspaces."),
  component: Workspaces,
});
function Workspaces() {
  const q = useWorkspaces();
  const create = useCreateWorkspace();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const workspaces = q.data?.filter((w) => w.name.toLowerCase().includes(search.toLowerCase())) ?? [];
  return (
    <div className="workbench-page workspace-index">
      <div className="page-heading">
        <div>
          <p className="eyebrow mb-2">Document analysis</p>
          <h1>Workspaces</h1>
        </div>
        <span className="collection-count">{q.data?.length ?? 0} total</span>
      </div>
      <div className="collection-toolbar">
        <span className="text-sm font-medium">All workspaces</span>
        <label className="search-field">
          <MagnifyingGlass size={16} aria-hidden="true" />
          <input aria-label="Search workspaces" placeholder="Search workspaces" value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
      </div>
      <div className="workspace-collection">
        {q.isLoading ? (
          <SkeletonRows />
        ) : q.error ? (
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        ) : !q.data?.length ? (
          <p className="py-8 text-muted-foreground">
            No workspaces yet. Create one to start uploading documents.
          </p>
        ) : !workspaces.length ? (
          <p className="py-8 text-muted-foreground">No matching workspaces.</p>
        ) : (
          <table className="data-table workspace-table">
            <thead>
              <tr>
                <th>Workspace</th>
                <th>Created</th>
                <th><span className="sr-only">Open</span></th>
              </tr>
            </thead>
            <tbody>
              {workspaces.map((w) => (
                <tr key={w.id}>
                  <td>
                    <div className="flex items-center gap-4">
                      <span className="workspace-icon"><FolderSimple size={24} weight="regular" /></span>
                      <span className="min-w-0 break-words font-medium">{w.name}</span>
                    </div>
                  </td>
                  <td className="workspace-date font-mono text-xs text-muted-foreground">{fmtDate(w.createdAt)}</td>
                  <td className="text-right">
                    <Button asChild variant="outline" size="sm">
                      <Link to="/w/$workspaceId/documents" params={{ workspaceId: w.id }}>Open <ArrowRight /></Link>
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <section className="workspace-create">
        <div className="flex items-center gap-3">
          <Plus size={18} className="text-primary" />
          <h2 className="text-base">New workspace</h2>
        </div>
        <form
          className="mt-4 flex max-w-xl flex-wrap gap-2"
          onSubmit={async (e) => {
            e.preventDefault();
            const err = workspaceNameError(name, q.data ?? []);
            setError(err);
            if (err) return;
            try {
              const w = await create.mutateAsync(name.trim());
              await navigate({ to: "/w/$workspaceId/documents", params: { workspaceId: w.id } });
            } catch (e) {
              setError(e instanceof Error ? e.message : "Could not create workspace.");
            }
          }}
        >
          <label htmlFor="workspace-name" className="sr-only">
            Workspace name
          </label>
          <input
            id="workspace-name"
            className="min-w-0 flex-1"
            placeholder="Workspace name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            aria-invalid={!!error}
          />
          <Button disabled={create.isPending || q.isLoading || !!q.error}>
            <Plus />
            {create.isPending ? "Creating" : "Create"}
          </Button>
          {error && (
            <p role="alert" className="w-full text-sm text-destructive">
              {error}
            </p>
          )}
        </form>
      </section>
    </div>
  );
}
