export function pageHead(title: string, description: string) {
  return {
    meta: [
      { title: `${title} · DocTrace` },
      { name: "description", content: description },
      { property: "og:title", content: `${title} · DocTrace` },
      { property: "og:description", content: description },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  };
}
