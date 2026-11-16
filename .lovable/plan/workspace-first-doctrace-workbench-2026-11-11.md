# Workspace-first DocTrace workbench

## What changes
- Make `/workspaces` the entry point with validated creation, workspace selection, and workspace-scoped Documents, Graph, Conflicts, Timeline, Ask, and Audit pages. Redirect `/` to `/workspaces`; retain legal pages and add compact `/about`.
- Replace the marketing shell with a collapsible fixed sidebar, workspace switcher, and slim page/status bar. Apply IBM Plex Sans/Mono, the specified cool dark surfaces, teal actions, amber warnings, and muted red errors.
- Rebuild Graph with a right inspector, Conflicts with master/detail and paired evidence, Timeline with separate date columns, and Ask with a bottom input and numbered citations.
- Give new workspaces honest empty states, Documents links, upload validation and animated processing stages. Keep evidence lookups through hooks and the existing API contract unchanged.
- Scope every mock response to its requested workspace. Keep one sample workspace and support empty workspace creation and simulated uploads without claiming real document extraction.

## Technical details
- Remove the default workspace constant/environment variable. Obtain workspace IDs from route parameters and pass them explicitly to workspace hooks; keep global workspaces and ID-based passage/document hooks appropriately parameterized.
- Add workspace creation and passage-search hooks. Preserve types, method signatures, and HTTP endpoints.
- Remove sample-specific UI text, passage mappings, and graph positioning maps. Preserve purposeful motion and reduced-motion support; add no hover styling.
- Update README and architecture rules. Add tests for workspace isolation, creation validation, and upload limits.

## Verification
- Run relevant tests and inspect automatic type/build results, fixing errors.
- Walk through creation, upload, processing, all scoped screens, evidence and review flows, sample workspace switching, About, Terms, and Privacy at desktop and approximately 1280px widths.
- Report tested routes and limitations. Live backend behavior remains unverified without a configured backend.