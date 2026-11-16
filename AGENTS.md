<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history, force pushing, or rebasing/amending/squashing commits
> that are already pushed, as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->
- Screens read data only through hooks in src/api/hooks.ts; only hooks.ts (and the usingMock badge in __root.tsx) import src/api/client.ts, where mock vs HTTP is chosen by VITE_API_BASE_URL. Why: backend swap must touch one env var and one file.
- Only src/api/mockApi.ts imports src/api/mockData.ts. Why: keeps demo data out of components.

- Workspace IDs come from API workspace rows and scoped route parameters; workspace hooks require an explicit ID with no default. Why: workspaces must remain interchangeable without backend contract changes.
- The global root shell owns the workbench sidebar; flat workspace leaf routes use /w/$workspaceId paths. Why: global pages remain available without selecting a workspace.
- Mock API responses filter by requested workspace and never synthesize extracted file content. Why: demo uploads must not leak sample evidence or claim real analysis.
- Workbench controls use the shared Button with no hover variants. Why: keep purposeful motion and consistent states without hover styling.
- Shared workbench presentation is defined in src/styles.css, with collection layouts in leaf pages. Why: navigation, tables and compact-screen behavior stay consistent across analysis views.
