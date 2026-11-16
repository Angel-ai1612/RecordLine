import { Button } from "./ui/button";

export function SkeletonRows({ rows = 4, height = "h-12" }: { rows?: number; height?: string }) {
  return (
    <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className={`skeleton ${height}`} style={{ animationDelay: `${i * 120}ms` }} />
      ))}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div role="alert" className="border border-destructive p-5">
      <p className="eyebrow text-destructive">Could not load</p>
      <p className="mt-2 text-sm">{error instanceof Error ? error.message : String(error)}</p>
      {onRetry && (
        <Button variant="outline" className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="border border-dashed border-hairline p-8">
      <p className="font-display text-xl">{title}</p>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">{body}</p>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="mb-5 grid gap-4 border-b border-hairline pb-4 md:grid-cols-[1fr_auto] md:items-end">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-3 text-[26px]">{title}</h1>
      </div>
      {children}
    </header>
  );
}
