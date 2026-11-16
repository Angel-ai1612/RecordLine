import { AnimatePresence, motion } from "framer-motion";
import { X, WarningCircle } from "@phosphor-icons/react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useDocument, usePassage } from "@/api/hooks";
import type { ID } from "@/api/types";
import { useWorkspaceId } from "@/hooks/use-workspace-id";
import { Button } from "./ui/button";
import { fmtDate, fmtLocator, FILE_LABEL } from "@/lib/format";

export interface EvidenceRequest {
  title: string;
  subtitle?: string;
  passageIds: ID[];
  /** Shared layout id so the opening element morphs into the drawer. */
  layoutId?: string;
  /** Extra content such as review controls or a signal breakdown. Rendered live, so it may use hooks. */
  extra?: ReactNode;
  /** Optional labels per passage, for example a fact status. */
  labels?: Record<ID, string>;
}

const Ctx = createContext<{
  open: (r: EvidenceRequest) => void;
  close: () => void;
  current: EvidenceRequest | null;
} | null>(null);

export function useEvidence() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useEvidence must be used inside EvidenceProvider");
  return c;
}

export function EvidenceProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<EvidenceRequest | null>(null);
  const close = useCallback(() => setCurrent(null), []);
  const value = useMemo(() => ({ open: setCurrent, close, current }), [close, current]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  return (
    <Ctx.Provider value={value}>
      {children}
      <AnimatePresence>
        {current && (
          <>
            <motion.div
              key="scrim"
              className="fixed inset-0 z-40 bg-background/70"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={close}
            />
            <motion.aside
              key="drawer"
              {...(current.layoutId ? { layoutId: current.layoutId } : { initial: { x: "100%" } })}
              role="dialog"
              aria-label={`Evidence: ${current.title}`}
              className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[min(960px,100vw)] flex-col border-l border-hairline bg-card"
              animate={{ x: 0 }}
              exit={{ x: "100%", transition: { duration: 0.25 } }}
              transition={{ type: "spring", stiffness: 260, damping: 32 }}
            >
              <div className="flex items-start justify-between gap-6 border-b border-hairline px-8 py-6">
                <div>
                  <p className="eyebrow">Evidence</p>
                  <h2 className="mt-2 text-xl">{current.title}</h2>
                  {current.subtitle && (
                    <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                      {current.subtitle}
                    </p>
                  )}
                </div>
                <Button variant="outline" onClick={close} aria-label="Close evidence">
                  <X size={16} />
                </Button>
              </div>
              <div className="flex-1 overflow-y-auto px-8 py-8">
                {current.extra && <div className="mb-8">{current.extra}</div>}
                <div
                  className={`grid gap-4 ${current.passageIds.length > 1 ? "md:grid-cols-2" : ""}`}
                >
                  {current.passageIds.map((id, i) => (
                    <motion.div
                      key={id}
                      initial={{ opacity: 0, y: 14 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.15 + i * 0.08 }}
                    >
                      <PassageCard passageId={id} label={current.labels?.[id]} />
                    </motion.div>
                  ))}
                </div>
                {current.passageIds.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No passages attached to this item.
                  </p>
                )}
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </Ctx.Provider>
  );
}

export function PassageCard({
  passageId,
  label,
  documentId,
}: {
  passageId: ID;
  label?: string | undefined;
  documentId?: string;
}) {
  const { data: p, isLoading, error } = usePassage(useWorkspaceId(), passageId);
  const { data: doc } = useDocument(useWorkspaceId(), p?.documentId);
  if (isLoading) return <div className="skeleton h-48" />;
  if (error || !p)
    return (
      <div className="border border-destructive p-4 text-sm">
        Passage {passageId} could not be loaded.
      </div>
    );

  if (documentId && p.documentId !== documentId) return null;
  const [s, e] = p.highlight ?? [0, 0];
  const ocrConfidence = p.ocrConfidence;
  const hasOcrConfidence = ocrConfidence != null;
  const lowOcr = hasOcrConfidence && ocrConfidence < 0.8;
  return (
    <article className="paper-surface flex flex-col">
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-paper-border px-5 py-3">
        <span className="break-all font-mono text-xs">{doc?.filename ?? p.documentId}</span>
        <span className="shrink-0 font-mono text-[0.65rem] uppercase tracking-wider text-paper-muted">
          {doc ? `${FILE_LABEL[doc.fileType]} · ${fmtDate(doc.fileDate)}` : ""}
        </span>
      </header>
      <p className="flex-1 px-5 py-5 text-sm leading-relaxed">
        {p.highlight ? (
          <>
            {p.text.slice(0, s)}
            <mark className="bg-signal-soft px-0.5 text-paper-foreground underline decoration-signal decoration-1 underline-offset-4">
              {p.text.slice(s, e)}
            </mark>
            {p.text.slice(e)}
          </>
        ) : (
          p.text
        )}
      </p>
      <footer className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-paper-border px-5 py-3 font-mono text-xs">
        <span>{fmtLocator(p.locator)}</span>
        <span className="text-paper-muted">{p.id}</span>
        {label && <span className="uppercase tracking-wider">{label}</span>}
        {hasOcrConfidence && (
          <span className={`flex items-center gap-1 ${lowOcr ? "text-warning" : ""}`}>
            {lowOcr && <WarningCircle size={14} weight="regular" />}
            OCR {Math.round(ocrConfidence * 100)}%{lowOcr ? ", check the scan" : ""}
          </span>
        )}
      </footer>
    </article>
  );
}
