import { afterEach, describe, expect, it, vi } from "vitest";
import { mockApi } from "@/api/mockApi";
import { MAX_FILE_BYTES, uploadError, workspaceNameError } from "@/lib/validation";
afterEach(() => vi.useRealTimers());
describe("Workspace rules", () => {
  it("rejects an empty name", () => expect(workspaceNameError("  ", [])).not.toBeNull());
  it("rejects duplicate names ignoring case and whitespace", () =>
    expect(workspaceNameError(" sample ", [{ name: "Sample" }])).not.toBeNull());
  it("accepts a distinct name", () =>
    expect(workspaceNameError("New", [{ name: "Sample" }])).toBeNull());
  it("enforces 25 MB upload limit", () => {
    expect(MAX_FILE_BYTES).toBe(25 * 1024 * 1024);
    expect(uploadError({ name: "file.pdf", size: 25 * 1024 * 1024 })).toBeNull();
    expect(uploadError({ name: "file.pdf", size: 25 * 1024 * 1024 + 1 })).not.toBeNull();
  });
  it("creates an empty workspace isolated from sample data and processes an upload", async () => {
    vi.useFakeTimers();
    async function resolve<T>(promise: Promise<T>) {
      await vi.runAllTimersAsync();
      return promise;
    }
    const list = await resolve(mockApi.listWorkspaces());
    expect(list.filter((w) => w.name === "Sample project (demo data)")).toHaveLength(1);
    const workspace = await resolve(mockApi.createWorkspace("Isolation test"));
    expect(await resolve(mockApi.listDocuments(workspace.id))).toEqual([]);
    expect(await resolve(mockApi.listConflicts(workspace.id))).toEqual([]);
    expect(await resolve(mockApi.getTimeline(workspace.id))).toEqual([]);
    expect(await resolve(mockApi.getAuditTrail(workspace.id))).toEqual([]);
    expect(await resolve(mockApi.searchPassages(workspace.id, "budget"))).toEqual([]);
    const graph = await resolve(mockApi.getGraph(workspace.id));
    expect(graph).toEqual({ documents: [], relationships: [], entities: [] });
    const file = new File(["content"], "test.pdf", { type: "application/pdf" });
    const doc = await resolve(mockApi.uploadDocument(workspace.id, file));
    expect(doc.status).toBe("queued");
    expect(doc.workspaceId).toBe(workspace.id);
    await vi.advanceTimersByTimeAsync(2000);
    expect((await resolve(mockApi.listDocuments(workspace.id)))[0]?.status).toBe("extracting");
    await vi.advanceTimersByTimeAsync(5000);
    expect((await resolve(mockApi.listDocuments(workspace.id)))[0]?.status).toBe("ready");
    expect((await resolve(mockApi.askQuestion(workspace.id, "budget"))).citations).toEqual([]);
  });
});
