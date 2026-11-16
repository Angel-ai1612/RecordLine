# RECORDLINE Accessibility and Performance Review

Review date: 2026-11-14. Scope: the integrated React/TanStack frontend after the final Graph and font fixes. This was an independent read-only gate; no production code was changed.

## Verdict

**Pass with Medium follow-ups.** No Critical or High accessibility/performance issue remains in the reviewed scope. The previous keyboard blocker in the Graph core flow is fixed and covered by a regression test. The production build and all frontend tests pass.

This verdict is based on static semantic inspection plus automated component tests and a production build. It is not a substitute for a manual screen-reader matrix or device/network performance profiling.

## Verification evidence

- `npm.cmd test -- --run`: passed, 3 test files and 17 tests in 22.93 seconds.
- `npm.cmd run build`: passed. Client output includes the Graph route at 191.87 kB (62.10 kB gzip); the shared `index` chunk is 549.93 kB (175.92 kB gzip) and still triggers Vite's 500 kB warning. CSS is 92.51 kB (16.42 kB gzip).
- `src/components/DocGraph.test.tsx` verifies Enter/Space activation for a document, entity and relationship, with accessible names asserted through button roles.
- Static inspection confirmed the custom React Flow container is not the sole keyboard target: document and entity nodes and relationship labels contain native buttons, while wrapper nodes/edges are `focusable: false` to avoid duplicate opaque focus stops.
- `rg -n 'fonts.googleapis|fonts.gstatic|preconnect' src` returned no matches. The prior Google Fonts runtime dependency has been removed.
- Reduced motion remains respected through `MotionConfig reducedMotion="user"`, `useReducedMotion` in the graph and the global `prefers-reduced-motion` rule.
- Existing declared color-token calculations remain: foreground/background 14.77:1, muted/background 6.74:1, primary/background 5.53:1, warning/background 8.02:1, paper foreground/paper 12.34:1 and paper muted/paper 5.67:1. Destructive/background remains approximately 4.23:1.

## Closed blocking finding

### A11Y-01 - Resolved - Graph inspection is keyboard operable

- **Location:** `src/components/DocGraph.tsx`, `src/components/DocGraph.test.tsx`.
- **Evidence:** document and entity nodes now render native `motion.button` controls with contextual `aria-label` values. Relationship labels render native buttons whose accessible names identify relationship type, source, target and confidence. Enter and Space call the same activation callbacks as pointer clicks. React Flow wrapper nodes and edges are removed from the tab order to avoid duplicate, opaque focus stops.
- **Regression coverage:** the keyboard test focuses each control, activates document and relationship inspection with Enter and entity inspection with Space, and asserts the matching selection callback.
- **Gate result:** the prior WCAG 2.1.1 keyboard blocker is cleared.

## Remaining findings

### A11Y-02 - Medium - Evidence dialog does not manage or contain focus

- **Location:** `src/components/EvidenceDrawer.tsx:47-113`.
- **Evidence:** the drawer uses `role="dialog"` and supports Escape, but lacks `aria-modal`, initial focus movement, focus trapping, background inertness and focus return. The scrim is pointer-clickable only. Focus can remain on the opener behind the overlay and Tab can traverse obscured application controls.
- **User impact:** keyboard and screen-reader users can lose context or interact with background controls while reviewing evidence.
- **Recommended fix:** use the installed Radix Dialog primitive or implement equivalent modal behavior, then add open/Tab/Shift+Tab/Escape/return-focus tests.

### A11Y-03 - Medium - Small destructive text misses AA contrast

- **Location:** `src/styles.css:81-82`; one visible use is `src/routes/__root.tsx:109`.
- **Evidence:** `--destructive` against `--background` remains approximately 4.23:1, below the 4.5:1 WCAG AA threshold for normal text. Some destructive/error status text is small, so the large-text exception does not apply.
- **User impact:** failed/error status text may be difficult to read for users with low vision or reduced contrast sensitivity.
- **Recommended fix:** adjust the destructive token until rendered contrast is at least 4.5:1 on every used surface, then record a browser-computed contrast check.

### A11Y-04 - Medium - Persistent navigation has no bypass link

- **Location:** `src/routes/__root.tsx:139-252`.
- **Evidence:** a semantic `<main>` exists, but there is no first-focusable skip link or stable focus target before the sidebar navigation.
- **User impact:** keyboard users must traverse repeated shell controls on every route.
- **Recommended fix:** add a `Skip to main content` link and stable `id`/focus target on the main landmark.

### PERF-01 - Medium - Shared client chunk exceeds the warning threshold

- **Location:** production build output.
- **Evidence:** `index-6zoPk9zg.js` is 549.93 kB minified and 175.92 kB gzip. Vite emits the larger-than-500-kB warning. The Graph route is separately chunked at 191.87 kB/62.10 kB gzip, so route splitting is working, but the initial shared runtime remains heavy.
- **User impact:** slower parse/compile and interaction readiness on mid-range devices, including in local-only use.
- **Recommended fix:** inspect the shared chunk with a bundle visualizer, remove graph-only or non-shell dependencies from the root graph where possible, and enforce a justified client bundle budget.

### A11Y-05 - Low - Async answer announcements are incomplete

- **Location:** `src/routes/w.$workspaceId.ask.tsx:45-75`.
- **Evidence:** pipeline status has `role="status"`, but newly appended answers are not in a deliberate live region and focus is not moved to or announced at the new result.
- **User impact:** a screen-reader user may not know when an answer has arrived or where it was inserted.
- **Recommended fix:** announce completion in a polite status region and test the submitted-question focus/announcement sequence.

## Passed checks

- Graph document, entity and relationship inspection controls have meaningful accessible names and native keyboard behavior.
- Remote Google Fonts and preconnects are absent, so this frontend no longer makes that third-party font request during private/offline operation.
- Semantic landmarks are present: global aside, labelled primary navigation, header and main.
- Page routes consistently provide an `h1`; sections use `h2` where appropriate.
- Workspace search, workspace creation, question input, workspace switcher and graph filters have labels or wrapping labels.
- Icon-only shell and evidence-close buttons have accessible labels.
- Loading skeletons expose `aria-busy`/labels; errors use `role="alert"`; empty states give direct next actions.
- Review actions use real buttons with disabled states and visible text; status is not communicated by color alone.
- Tables use header cells and responsive horizontal overflow where needed.
- Responsive rules collapse the sidebar, stack toolbars, hide nonessential table columns and move the graph inspector below the canvas on narrower screens.
- Reduced-motion handling is present in both global and Graph-specific animation paths.
- No test failure or build error was emitted. The build reports the bundle-size warning and non-blocking toolchain notices only.

## Follow-up exit criteria

1. Give the evidence dialog complete modal focus behavior and regression coverage.
2. Raise destructive text contrast to at least 4.5:1 on rendered surfaces.
3. Add a keyboard bypass link to the main landmark.
4. Profile and reduce the shared client chunk, then establish a bundle budget.
5. Run a manual keyboard and screen-reader pass before broader-than-local release.
