import { Button } from "./ui/button";
import type { ReviewStatus } from "@/api/types";

export function ReviewControl({
  status,
  onChange,
  pending,
  noun = "link",
}: {
  status: ReviewStatus;
  onChange: (s: ReviewStatus) => void;
  pending?: boolean;
  noun?: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="eyebrow">Review</span>
      <Button
        variant="outline"
        data-active={status === "confirmed"}
        disabled={pending}
        onClick={() => onChange("confirmed")}
      >
        {noun === "link" ? "Confirm link" : "Mark reviewed"}
      </Button>
      <Button
        variant="outline"
        data-active={status === "rejected"}
        disabled={pending}
        onClick={() => onChange("rejected")}
      >
        {noun === "link" ? "Reject link" : "Dismiss"}
      </Button>
      {status !== "pending" && (
        <Button variant="outline" disabled={pending} onClick={() => onChange("pending")}>
          Reset
        </Button>
      )}
      <span className="font-mono text-xs text-muted-foreground">Status: {status}</span>
    </div>
  );
}

export function StatusTag({ status }: { status: ReviewStatus }) {
  return (
    <span
      className={`border px-1.5 py-0.5 font-mono text-[0.65rem] uppercase tracking-wider ${
        status === "pending"
          ? "border-warning text-warning"
          : status === "rejected"
            ? "border-destructive text-destructive"
            : "border-primary text-primary"
      }`}
    >
      {status}
    </span>
  );
}
