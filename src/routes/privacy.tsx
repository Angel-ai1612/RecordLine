import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/States";

export const Route = createFileRoute("/privacy")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Privacy Policy · DocTrace" },
      { name: "description", content: "How DocTrace handles the documents and data you upload." },
      { property: "og:title", content: "Privacy Policy · DocTrace" },
      { property: "og:description", content: "How DocTrace handles your documents." },
    ],
  }),
  component: Privacy,
});

const ITEMS = [
  ["What we store", "The files you upload, the text and cells extracted from them, the links and conflicts found, and the review decisions you make."],
  ["Sensitive content", "Project documents can include names, receipts and budgets. We treat every uploaded file as sensitive and do not use it to train models or share it outside your workspace."],
  ["Who can see it", "Data is scoped to a workspace. Only its members can view or search its documents."],
  ["Deleting your data", "You can delete any document or workspace yourself. Deletion removes the file, its passages and its search index entries."],
  ["Contact", "Questions about your data can be sent to the workspace owner or to the DocTrace team."],
];

function Privacy() {
  return (
    <div className="mx-auto max-w-[760px] px-6 py-6">
      <PageHeader eyebrow="Last updated 26 Oct 2026" title="Privacy Policy" />
      <ol className="grid gap-8">
        {ITEMS.map(([h, b], i) => (
          <li key={h} className="grid grid-cols-[40px_1fr] gap-4">
            <span className="font-mono text-sm text-muted-foreground">{i + 1}.</span>
            <div><h2 className="text-lg">{h}</h2><p className="mt-2 leading-relaxed text-muted-foreground">{b}</p></div>
          </li>
        ))}
      </ol>
    </div>
  );
}
