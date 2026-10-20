import "./localeGuard";            // must stay the first import (see the file)
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";
import { useApp } from "./store";
import { installErrorReporting } from "./errorReport";
import { loadPrefs } from "./prefs";
import { applySettings } from "./settings";

installErrorReporting();             // T38: UI errors into the local log

// read-only hook for the automated conformance tests (tests/e2e)
(window as unknown as { __sv: unknown }).__sv = { state: () => useApp.getState(), setState: useApp.setState };   // for the end-to-end tests

// T18 / F30: the user's settings first (the UI reads them while it starts)
loadPrefs().finally(() => {
  applySettings();
  createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
});
