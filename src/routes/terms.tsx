import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/States";

export const Route = createFileRoute("/terms")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Terms of Service · DocTrace" },
      { name: "description", content: "Plain terms for using DocTrace with your project documents." },
      { property: "og:title", content: "Terms of Service · DocTrace" },
      { property: "og:description", content: "Plain terms for using DocTrace." },
    ],
  }),
  component: Terms,
});

const ITEMS = [
  ["Your documents", "You keep ownership of every file you upload. You confirm you have the right to upload it. Uploaded documents may contain sensitive information, so only add files you are allowed to share with your workspace members."],
  ["Workspaces", "Each document belongs to one workspace. Only members of that workspace can see its files, passages, links and answers."],
  ["Deleting", "You can delete a document or a whole workspace at any time. Deleting removes the file and everything extracted from it."],
  ["What DocTrace does not do", "DocTrace points out where documents differ. It never decides which value is correct. Check the cited passages before relying on any result, especially OCR text from scans."],
  ["Changes", "If these terms change, we will show the new version here with its date before it applies."],
];

function Terms() {
  return (
    <div className="mx-auto max-w-[760px] px-6 py-6">
      <PageHeader eyebrow="Last updated 26 Oct 2026" title="Terms of Service" />
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
