import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  useRouterState,
  HeadContent,
  Scripts,
  useParams,
  type ErrorComponentProps,
} from "@tanstack/react-router";
import { MotionConfig, motion } from "framer-motion";
import { useEffect, useState, type ReactNode } from "react";
import {
  Files,
  Graph,
  WarningDiamond,
  CalendarBlank,
  ChatText,
  ListBullets,
  SidebarSimple,
  Info,
  CaretDown,
  FolderSimple,
} from "@phosphor-icons/react";
import appCss from "../styles.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";
import { EvidenceProvider } from "@/components/EvidenceDrawer";
import { usingMock } from "@/api/client";
import { useWorkspaces, useDocuments } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { STATUS_LABEL } from "@/lib/format";
function NotFoundComponent() {
  return (
    <div className="workbench-page">
      <h1>No page here</h1>
      <Link to="/workspaces" className="btn mt-4">
        All workspaces
      </Link>
    </div>
  );
}
function ErrorComponent({ error, reset }: ErrorComponentProps) {
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);
  return (
    <div className="workbench-page">
      <h1>This page did not load</h1>
      <Button
        className="mt-4"
        onClick={() => {
          router.invalidate();
          reset();
        }}
      >
        Try again
      </Button>
    </div>
  );
}
export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "DocTrace" },
      { name: "theme-color", content: "#0F1720" },
    ],
    links: [
      { rel: "stylesheet", href: appCss },
      { rel: "icon", href: "/favicon.ico" },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});
function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}
const NAV = [
  ["documents", "Documents", Files],
  ["graph", "Graph", Graph],
  ["conflicts", "Conflicts", WarningDiamond],
  ["timeline", "Timeline", CalendarBlank],
  ["ask", "Ask", ChatText],
  ["audit", "Audit", ListBullets],
] as const;
function ProcessingStatus({ workspaceId }: { workspaceId: string }) {
  const q = useDocuments(workspaceId);
  const busy = q.data?.filter((d) => !["ready", "failed"].includes(d.status)) ?? [];
  const failed = q.data?.filter((d) => d.status === "failed").length ?? 0;
  return (
    <span
      className={`font-mono text-xs ${busy.length ? "text-warning" : failed ? "text-destructive" : "text-muted-foreground"}`}
      role="status"
    >
      {q.isLoading
        ? "Loading"
        : q.error
          ? "Status unavailable"
          : busy.length
            ? `${busy.length} processing · ${STATUS_LABEL[busy[0]?.status ?? "queued"]}`
            : failed
              ? `${failed} failed`
              : q.data?.length
                ? "Ready"
                : "No documents"}
    </span>
  );
}
function Shell() {
  const [collapsed, setCollapsed] = useState(false);
  const params = useParams({ strict: false });
  const workspaceId = params.workspaceId;
  const q = useWorkspaces();
  const current = q.data?.find((w) => w.id === workspaceId);
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const router = useRouter();
  const title = workspaceId
    ? (NAV.find(([key]) => pathname.endsWith(`/${key}`))?.[1] ?? "Workspace")
    : pathname === "/about"
      ? "How DocTrace works"
      : pathname === "/terms"
        ? "Terms of Service"
        : pathname === "/privacy"
          ? "Privacy Policy"
          : "Workspaces";
  return (
    <div className="min-h-screen">
      <aside
        className={`workbench-sidebar fixed inset-y-0 left-0 z-30 flex flex-col border-r border-hairline bg-card ${collapsed ? "w-16 is-collapsed" : "w-60"}`}
      >
        <Link
          to="/workspaces"
          className="brand-link flex h-16 items-center gap-3 border-b border-hairline px-5"
          aria-label="DocTrace workspaces"
        >
          <svg
            width="24"
            height="28"
            viewBox="0 0 24 28"
            fill="none"
            className="shrink-0 text-primary"
            aria-hidden="true"
          >
            <path
              d="M3 3h10l5 5v14H3zM13 3v6h5M6 13h7M6 17h5M18 16h3v6"
              stroke="currentColor"
              strokeWidth="1.5"
            />
            <circle cx="21" cy="24" r="2" stroke="currentColor" strokeWidth="1.5" />
          </svg>
          {!collapsed && <span className="sidebar-label text-lg font-medium">DocTrace</span>}
        </Link>
        {!collapsed && (
          <div className="workspace-switcher border-b border-hairline px-4 py-5">
            <p className="eyebrow mb-2">Workspace</p>
            <div className="relative">
              <select className="w-full appearance-none pr-7 text-xs" aria-label="Switch workspace" value={workspaceId ?? ""} onChange={(e) => {
                const id = e.target.value;
                if (id) void router.navigate({ to: "/w/$workspaceId/documents", params: { workspaceId: id } });
                else void router.navigate({ to: "/workspaces" });
              }}>
                <option value="">All workspaces</option>
                {q.data?.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </select>
              <CaretDown className="pointer-events-none absolute right-2 top-3 text-muted-foreground" size={12} />
            </div>
          </div>
        )}
        <nav className="primary-navigation grid gap-1 p-3" aria-label="Main navigation">
          <Link to="/workspaces" title="All workspaces" className="nav-link flex items-center gap-3 px-3 py-2.5 text-muted-foreground" activeProps={{ className: "bg-secondary text-primary" }}>
            <FolderSimple size={18} />
            {!collapsed && <span className="sidebar-label">All workspaces</span>}
          </Link>
          {workspaceId ? (
            NAV.map(([key, label, Icon]) => (
              <Link
                key={key}
                to={`/w/$workspaceId/${key}`}
                params={{ workspaceId }}
                title={label}
                className="nav-link flex items-center gap-3 px-3 py-2.5 text-muted-foreground"
                activeProps={{ className: "bg-secondary text-primary" }}
              >
                <Icon size={18} weight="regular" />
                {!collapsed && <span className="sidebar-label">{label}</span>}
              </Link>
            ))
          ) : null}
          <Link
            to="/about"
            title="How DocTrace works"
            className="nav-link about-link flex gap-3 px-3 py-2.5 text-muted-foreground"
            activeProps={{ className: "bg-secondary text-primary" }}
          >
            <Info size={18} />
            {!collapsed && <span className="sidebar-label">How DocTrace works</span>}
          </Link>
        </nav>
        <div className="mt-auto border-t border-hairline p-3">
          {!collapsed && (
            <nav className="sidebar-label flex gap-4 text-xs text-muted-foreground">
              <Link to="/terms">Terms</Link>
              <Link to="/privacy">Privacy</Link>
            </nav>
          )}
        </div>
      </aside>
      <div className={`workbench-content ${collapsed ? "ml-16 is-collapsed" : "ml-60"}`}>
        <header className="workbench-header sticky top-0 z-20 flex min-h-16 items-center gap-3 border-b border-hairline bg-background px-5">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <SidebarSimple />
          </Button>
          <span className="header-breadcrumb text-xs text-muted-foreground">DocTrace</span>
          <span className="header-breadcrumb text-muted-foreground" aria-hidden="true">/</span>
          <span className="text-sm font-medium">{title}</span>
          <span className="ml-auto hidden max-w-72 truncate text-xs text-muted-foreground sm:block">
            {current?.name ?? ""}
          </span>
          {workspaceId && <ProcessingStatus workspaceId={workspaceId} />}
          <span className="mode-label font-mono text-[10px] text-muted-foreground">{usingMock ? "Demo data" : "Live"}</span>
        </header>
        <motion.main
          key={`${workspaceId ?? "global"}-${pathname}`}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
        >
          <Outlet />
        </motion.main>
      </div>
    </div>
  );
}
function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  return (
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user">
        <EvidenceProvider>
          <Shell />
        </EvidenceProvider>
      </MotionConfig>
    </QueryClientProvider>
  );
}
