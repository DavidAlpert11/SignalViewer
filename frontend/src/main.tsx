import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";
import { useApp } from "./store";

// read-only hook for the automated conformance tests (tests/e2e)
(window as unknown as { __sv: unknown }).__sv = { state: () => useApp.getState(), setState: useApp.setState };   // for the end-to-end tests

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
