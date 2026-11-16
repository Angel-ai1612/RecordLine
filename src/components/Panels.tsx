import { useWorkspaceId } from "@/hooks/use-workspace-id";
import { motion } from "framer-motion";
import { useConflicts, useGraph, useReviewConflict, useReviewRelationship } from "@/api/hooks";
import type { ID, RelationshipSignals } from "@/api/types";
import { REL_LABEL } from "@/lib/format";
import { Counter } from "./Counter";
import { ReviewControl } from "./Review";

const SIGNAL_LABEL: Record<keyof RelationshipSignals, string> = {
  entityOverlap: "Shared entities",
  semanticSimilarity: "Similar wording",
  explicitReference: "Names the other file",
  temporalContext: "Close in time",
};

export function RelationshipPanel({ id }: { id: ID }) {
  const { data } = useGraph(useWorkspaceId());
  const review = useReviewRelationship(useWorkspaceId());
  const rel = data?.relationships.find((r) => r.id === id);
  if (!rel) return <div className="skeleton h-40" />;
  return (
    <div className="grid gap-4 border-b border-hairline pb-4">
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <p className="eyebrow">Match strength</p>
          <Counter
            value={rel.score}
            className="mt-1 block font-display text-3xl font-mono text-foreground"
          />
        </div>
        <div>
          <p className="eyebrow">Suggested type</p>
          <p
            className={`mt-2 font-display text-base ${rel.type === "contradicts" ? "text-warning" : ""}`}
          >
            {REL_LABEL[rel.type]}
          </p>
        </div>
      </div>
      <dl className="grid gap-3">
        {(Object.keys(SIGNAL_LABEL) as (keyof RelationshipSignals)[]).map((k, i) => (
          <div key={k} className="grid grid-cols-[120px_1fr_42px] items-center gap-4">
            <dt className="text-sm text-muted-foreground">{SIGNAL_LABEL[k]}</dt>
            <dd className="h-px bg-hairline">
              <motion.div
                className="h-[3px] -translate-y-px bg-foreground"
                initial={{ width: 0 }}
                animate={{ width: `${rel.signals[k] * 100}%` }}
                transition={{ delay: 0.2 + i * 0.1, duration: 0.8 }}
              />
            </dd>
            <Counter value={rel.signals[k]} className="text-right font-mono text-xs" />
          </div>
        ))}
      </dl>
      <ReviewControl
        status={rel.reviewStatus}
        pending={review.isPending}
        onChange={(status) => review.mutate({ id, status })}
      />
    </div>
  );
}

export function ConflictPanel({ id }: { id: ID }) {
  const { data } = useConflicts(useWorkspaceId());
  const review = useReviewConflict(useWorkspaceId());
  const c = data?.find((x) => x.id === id);
  if (!c) return <div className="skeleton h-32" />;
  return (
    <div className="grid gap-6 border-b border-hairline pb-4">
      <p className="max-w-3xl text-base leading-relaxed">{c.explanation}</p>
      <div className="flex flex-wrap gap-x-8 gap-y-2 font-mono text-xs">
        {c.facts.map((f) => (
          <span key={f.id}>
            {f.rawValue} <span className="text-muted-foreground">({f.status})</span>
          </span>
        ))}
      </div>
      <p className="text-sm text-muted-foreground">
        DocTrace does not pick a correct value. Read both passages and record your decision.
      </p>
      <ReviewControl
        noun="conflict"
        status={c.reviewStatus}
        pending={review.isPending}
        onChange={(status) => review.mutate({ id, status })}
      />
    </div>
  );
}
