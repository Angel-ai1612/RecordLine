import { createFileRoute, redirect } from "@tanstack/react-router";
import { pageHead } from "@/lib/head";
export const Route = createFileRoute("/")({
  head: () => pageHead("Document analysis", "Open a workspace to analyze documents and trace evidence."),
  beforeLoad: () => {
    throw redirect({ to: "/workspaces" });
  },
});
