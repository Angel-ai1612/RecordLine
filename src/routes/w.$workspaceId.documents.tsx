import { createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { UploadSimple, File } from "@phosphor-icons/react";
import { useRef, useState } from "react";
import { useDocuments, useUpload } from "@/api/hooks";
import { useWorkspaceId } from "@/hooks/use-workspace-id";
import { Button } from "@/components/ui/button";
import { QueryState } from "@/components/WorkspaceState";
import { FILE_ACCEPT, uploadError } from "@/lib/validation";
import { FILE_LABEL, PIPELINE, STATUS_LABEL, fmtDate } from "@/lib/format";
import { pageHead } from "@/lib/head";
export const Route = createFileRoute("/w/$workspaceId/documents")({
  head: () =>
    pageHead(
      "Documents",
      "Upload documents and follow extraction, OCR and analysis in this workspace.",
    ),
  component: Documents,
});
function Documents() {
  const workspaceId = useWorkspaceId();
  const docs = useDocuments(workspaceId);
  const upload = useUpload(workspaceId);
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<Record<string, number>>({});
  const send = async (files: FileList | null) => {
    if (!files) return;
    setError(null);
    for (const file of Array.from(files)) {
      const err = uploadError(file);
      if (err) {
        setError(`${file.name}: ${err}`);
        continue;
      }
      setProgress((p) => ({ ...p, [file.name]: 0 }));
      try {
        await upload.mutateAsync({
          file,
          onProgress: (v) => setProgress((p) => ({ ...p, [file.name]: v })),
        });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed.");
      } finally {
        setProgress((p) => {
          const next = { ...p };
          delete next[file.name];
          return next;
        });
      }
    }
    if (input.current) input.current.value = "";
  };
  return (
    <div className="workbench-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow mb-2">Source library</p>
          <h1>Documents</h1>
        </div>
        <span className="collection-count">{docs.data?.length ?? 0} files</span>
      </div>
      <section
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          void send(e.dataTransfer.files);
        }}
        className={`upload-surface flex flex-wrap items-center justify-between gap-5 border border-dashed bg-card p-6 ${drag ? "border-primary" : "border-hairline"} ${!docs.data?.length ? "min-h-60" : ""}`}
      >
        <div className="flex items-center gap-4">
          <span className="upload-icon">
            <UploadSimple size={28} className="text-primary" />
          </span>
          <div>
            <h2 className="text-base">Drop files here</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              PDF, Word, Excel, JPG and PNG · up to 25 MB per file
            </p>
          </div>
        </div>
        <Button onClick={() => input.current?.click()}>
          <UploadSimple />
          Choose files
        </Button>
        <input
          ref={input}
          type="file"
          hidden
          multiple
          accept={FILE_ACCEPT}
          onChange={(e) => void send(e.target.files)}
        />
      </section>
      {error && (
        <p className="mt-3 text-destructive" role="alert">
          {error}
        </p>
      )}
      {Object.entries(progress).map(([name, value]) => (
        <div key={name} className="mt-3 border border-hairline p-3">
          <div className="flex justify-between font-mono text-xs">
            <span>{name}</span>
            <span>Uploading {Math.round(value * 100)}%</span>
          </div>
          <motion.div className="mt-2 h-0.5 bg-primary" animate={{ width: `${value * 100}%` }} />
        </div>
      ))}
      <div className="mt-6">
        <div className="mb-2 flex items-center justify-between border-b border-hairline py-3">
          <h2 className="text-sm">All documents</h2>
          <span className="eyebrow">Source files</span>
        </div>
        <QueryState query={docs} />
        {docs.data?.length ? (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>File date</th>
                </tr>
              </thead>
              <tbody>
                {docs.data.map((d, i) => {
                  const stages = PIPELINE.filter((s) => s !== "ocr" || d.fileType === "image");
                  const stage = stages.indexOf(d.status);
                  const busy = !["ready", "failed"].includes(d.status);
                  return (
                    <motion.tr
                      key={d.id}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.04 }}
                    >
                      <td>
                        <div className="flex items-center gap-2">
                          <span className="document-icon">
                            <File size={18} />
                          </span>
                          <span className="break-all">{d.filename}</span>
                        </div>
                        {busy && (
                          <div className="mt-3 grid grid-cols-4 gap-2">
                            {stages.map((s, index) => (
                              <div key={s}>
                                <div className="h-0.5 bg-border">
                                  <motion.div
                                    className="h-0.5 bg-primary"
                                    animate={{
                                      width:
                                        index < stage ? "100%" : index === stage ? "60%" : "0%",
                                    }}
                                  />
                                </div>
                                <span className="mt-1 block font-mono text-[10px] text-muted-foreground">
                                  {STATUS_LABEL[s]}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="font-mono text-xs">{FILE_LABEL[d.fileType]}</td>
                      <td
                        className={`whitespace-nowrap font-mono text-xs ${busy ? "text-warning" : d.status === "failed" ? "text-destructive" : "text-primary"}`}
                      >
                        <span className="status-chip">{STATUS_LABEL[d.status]}</span>
                      </td>
                      <td className="whitespace-nowrap font-mono text-xs text-muted-foreground">
                        {fmtDate(d.fileDate)}
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          !docs.isLoading &&
          !docs.error && <p className="py-6 text-muted-foreground">No documents yet.</p>
        )}
      </div>
    </div>
  );
}
