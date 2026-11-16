import { createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { PaperPlaneTilt } from "@phosphor-icons/react";
import { Fragment, useState } from "react";
import { useAsk, useDocuments } from "@/api/hooks";
import { useWorkspaceId } from "@/hooks/use-workspace-id";
import type { Answer } from "@/api/types";
import { useEvidence } from "@/components/EvidenceDrawer";
import { Button } from "@/components/ui/button";
import { QueryState, WorkspaceEmpty, Pipeline } from "@/components/WorkspaceState";
import { SkeletonRows, ErrorState } from "@/components/States";
import { pageHead } from "@/lib/head";
export const Route = createFileRoute("/w/$workspaceId/ask")({
  head: () =>
    pageHead("Ask", "Ask workspace questions with numbered source citations and ambiguity notes."),
  component: Ask,
});
function Ask() {
  const ws = useWorkspaceId();
  const docs = useDocuments(ws);
  const ask = useAsk(ws);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<{ question: string; answer: Answer }[]>([]);
  const [pendingQuestion, setPendingQuestion] = useState("");
  if (docs.isLoading || docs.error)
    return (
      <div className="workbench-page">
        <QueryState query={docs} />
      </div>
    );
  if (!docs.data?.length)
    return (
      <div className="workbench-page">
        <h1>Ask</h1>
        <WorkspaceEmpty title="No documents to ask about yet" />
      </div>
    );
  const ready = docs.data.some((d) => d.status === "ready");
  return (
    <div className="flex min-h-[calc(100svh-56px)] flex-col">
      <div className="workbench-page flex-1">
        <h1>Ask</h1>
        <Pipeline />
        <div className="mx-auto mt-6 max-w-4xl">
          {messages.map((m, i) => (
            <div key={i} className="mb-8">
              <div className="mb-4 border-y border-hairline bg-card px-4 py-3">{m.question}</div>
              <AnswerView answer={m.answer} />
            </div>
          ))}
          {ask.isPending && (
            <div>
              <p className="mb-4 text-muted-foreground">{pendingQuestion}</p>
              <SkeletonRows rows={3} height="h-6" />
            </div>
          )}
          {ask.error && <ErrorState error={ask.error} />}
          {!messages.length && !ask.isPending && (
            <p className="text-muted-foreground">No questions yet.</p>
          )}
        </div>
      </div>
      <form
        className="sticky bottom-0 flex gap-3 border-t border-hairline bg-card p-4"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!question.trim() || !ready) return;
          const text = question.trim();
          setPendingQuestion(text);
          try {
            const answer = await ask.mutateAsync(text);
            setMessages((m) => [...m, { question: text, answer }]);
            setQuestion("");
          } catch {
            /* The mutation error appears above. */
          }
        }}
      >
        <label className="sr-only" htmlFor="question">
          Question
        </label>
        <input
          id="question"
          className="flex-1"
          placeholder="Ask about these documents"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={!ready}
        />
        <Button disabled={ask.isPending || !ready || !question.trim()}>
          <PaperPlaneTilt />
          Ask
        </Button>
      </form>
    </div>
  );
}
function AnswerView({ answer }: { answer: Answer }) {
  const docs = useDocuments(useWorkspaceId());
  const { open } = useEvidence();
  const name = (id: string) => docs.data?.find((d) => d.id === id)?.filename ?? id;
  const cite = (n: number) => {
    const c = answer.citations[n - 1];
    if (c)
      open({ title: `Citation ${n}`, subtitle: name(c.documentId), passageIds: [c.passageId] });
  };
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
      <p className="leading-7">
        {answer.text.split(/(\[\d+\])/g).map((part, i) => {
          const m = part.match(/^\[(\d+)\]$/);
          return m ? (
            <Button
              key={i}
              variant="outline"
              size="sm"
              className="mx-1 h-6 border-primary px-2 font-mono text-primary"
              aria-label={`Open citation ${m[1]}`}
              onClick={() => cite(Number(m[1]))}
            >
              {m[1]}
            </Button>
          ) : (
            <Fragment key={i}>{part}</Fragment>
          );
        })}
      </p>
      {answer.ambiguityNote && (
        <div className="mt-4 border border-warning p-3">
          <p className="font-mono text-xs text-warning">Evidence is ambiguous</p>
          <p className="mt-2 text-sm">{answer.ambiguityNote}</p>
        </div>
      )}
      <ol className="mt-4">
        {answer.citations.map((c, i) => (
          <li key={c.passageId} className="border-b border-hairline">
            <Button
              variant="link"
              className="h-auto whitespace-normal px-0 py-2 font-mono text-xs"
              onClick={() => cite(i + 1)}
            >
              {i + 1}. {name(c.documentId)}
            </Button>
          </li>
        ))}
      </ol>
    </motion.div>
  );
}
