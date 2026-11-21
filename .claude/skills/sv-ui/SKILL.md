---
name: sv-ui
description: Add or change a control, a screen part or a user-visible string in Signal Viewer's React UI - where it belongs (TopBar / StageBar / side panel / Inspector / Settings), state and Undo, strings in en + he, RTL, themes, the test hooks e2e uses. Use for any frontend change a user sees.
---

# A control or a string in the UI

Rules: `/CLAUDE.md` ("Before changing anything" §3, "Invariants"). The practical steps:

1. **Where** - TopBar: workspace / file actions. StageBar: about the plots on screen. A side panel (the rail): a tool
   that needs room. Inspector: properties of the selection. Settings: choices made once. One place per control;
   Ctrl+K (`components/CommandPalette.tsx`) and a shortcut are the only second entry points. A panel's guided flow
   (steps) is fine inside the panel - not a dialog beside it.
2. **State** - a workspace change goes through `useApp.getState().commit((w) => { ...; return w; })` (Undo);
   UI-only state (`store/slices/ui.ts`) is `useApp.setState`. New saved fields are optional with defaults; never
   rename or repurpose one (old sessions must open). Server calls: one function in `api.ts`, one route in
   `backend/app/routes/<area>.py`.
3. **Strings** - every visible word through `useT()` / `translate(lang, key)`; the key in the area's
   `frontend/src/i18n/<area>.ts`, `en` and `he` (tsc fails when one is missing). Hebrew: plain, short, the owner's
   words when he gave them. Numbers / ids / hex inside Hebrew text: `<bdi dir="ltr">`.
4. **RTL** - `margin-inline-start`, `inset-inline-*`, `text-align: start`; a hex / code / table of bytes is
   `dir="ltr"`. Check the screen with the language set to Hebrew.
5. **Themes** - colours only from the CSS variables in `frontend/src/index.css` (`--ink`, `--muted`, `--line`,
   `--panel`, `--accent`...); a role colour used by several components goes there as a variable, both themes.
6. **Heavy parts** stay lazy (`lazyPreload` in `App.tsx`); never import Cesium / map data in the main bundle.
7. **Tests** - a logic helper with no screen: a Vitest `src/<name>.test.ts`. A flow: e2e in `tests/e2e/test_<area>.py`
   (Playwright; reach the app by `window.__sv.state()` / `window.__sv.setState(...)`, wait for the END state). Give
   new elements a stable class (`msg-step-2`, `rd-latex`) for the tests and the media script.
8. `npx tsc -b`, the area's e2e files, then `sv-flow` §3.
