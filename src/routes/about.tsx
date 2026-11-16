import { createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { pageHead } from "@/lib/head";
export const Route = createFileRoute("/about")({
  head: () =>
    pageHead(
      "How DocTrace works",
      "Upload, extract, connect and verify documents with exact source evidence.",
    ),
  component: About,
});
function About() {
  return (
    <div className="workbench-page max-w-4xl">
      <h1>How DocTrace works</h1>
      <ol className="mt-6">
        {[
          ["Upload", "Add PDFs, Word files, spreadsheets and scanned images to a workspace."],
          [
            "Extract",
            "Text, cells, dates and amounts retain their source passage or cell locator.",
          ],
          [
            "Connect",
            "Review document links based on shared entities, wording, references and timing.",
          ],
          [
            "Verify",
            "Compare differing values against both sources. DocTrace flags discrepancies and never decides which value is correct.",
          ],
        ].map(([title, body], i) => (
          <motion.li
            key={title}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className="grid grid-cols-[40px_110px_1fr] gap-4 border-b border-hairline py-5"
          >
            <span className="font-mono text-primary">0{i + 1}</span>
            <h2 className="text-base">{title}</h2>
            <p className="text-muted-foreground">{body}</p>
          </motion.li>
        ))}
      </ol>
    </div>
  );
}
