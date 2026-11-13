import "./localeGuard";            // must stay the first import (see the file)
import "./polyfills";              // before any code that calls them (old offline engines)
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
// W0 (2026-11-13): one stylesheet per lane of the round, after the global one - a line each
// by area, after index.css (the same order as before: welcome, Sweeps' study, app, plots, the review's touches)
import "./styles/welcome.css";
import "./styles/study.css";
import "./styles/app.css";
import "./styles/plots.css";
import "./styles/review.css";
import App from "./App";
import { useApp } from "./store";
import { installErrorReporting } from "./errorReport";
import { loadPrefs } from "./prefs";
import { loadMyPlaces } from "./places";
import { loadMapPrefs } from "./mapDefaults";
import { applySettings } from "./settings";
import { watchNewerOnDisk } from "./fileTimes";
import { watchReadAs } from "./readAs";
import { installClosePrompt } from "./unsaved";
import { maybeStartTour } from "./components/Tour";

installErrorReporting();             // T38: UI errors into the local log
installClosePrompt();                // W10: ask before closing with unsaved work

// read-only hook for the automated conformance tests (tests/e2e)
(window as unknown as { __sv: unknown }).__sv = { state: () => useApp.getState(), setState: useApp.setState };   // for the end-to-end tests

// T18 / F30: the user's settings first (the UI reads them while it starts)
loadPrefs().finally(() => {
  applySettings();
  maybeStartTour();                  // W13.8: once, for a new user
  watchNewerOnDisk();          // Q123: a file saved again on the disk - its time turns amber, click to read it
  watchReadAs();               // 26.A5: the user's "read as a state / a value" -> the backend
  void loadMyPlaces();         // P7: My places (the app's places.json)
  loadMapPrefs();              // P8: Settings > Map and objects
  createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
});
