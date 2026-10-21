// T38: errors the UI meets go to the app's local log (backend /api/client-error), so
// Help > "Copy error details" can include them. Nothing leaves the computer.
import { api } from "./api";

const MAX_PER_SESSION = 20;           // a loop of errors must not flood the log (the backend limits too)
let sent = 0;

export function reportError(message: string, stack?: string, where?: string): void {
  if (sent >= MAX_PER_SESSION) return;
  sent++;
  api.clientError({ message: message.slice(0, 2000), stack: (stack ?? "").slice(0, 6000), where: where ?? "" }).catch(() => { /* server gone: nothing to do */ });
}

export function installErrorReporting(): void {
  window.addEventListener("error", (e) => reportError(String(e.message || e.error || "error"), e.error?.stack, "window.onerror"));
  window.addEventListener("unhandledrejection", (e) => {
    const r = e.reason as { message?: string; stack?: string } | undefined;
    reportError(String(r?.message ?? r ?? "rejected promise"), r?.stack, "unhandled promise");
  });
}

/** Copy text: the Clipboard API, else the old way (a webview may refuse the API). */
export async function copyText(text: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(text); return true; } catch { /* fall through */ }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch { ok = false; }
  ta.remove();
  return ok;
}


/** Help > Copy error details (T38): version, system and the end of the log, to the clipboard. */
export async function copyErrorDetails(t: (k: "errorDetailsCopied" | "errorDetailsNotCopied", v?: Record<string, string>) => string,
  toast: (x: { kind: "info" | "error"; text: string }) => void): Promise<void> {
  try {
    const d = await api.diagnostics();
    if (await copyText(d.text)) toast({ kind: "info", text: t("errorDetailsCopied") });
    else toast({ kind: "error", text: t("errorDetailsNotCopied", { path: d.logFile }) });
  } catch (e) {
    toast({ kind: "error", text: String((e as Error).message) });
  }
}


/** Help > Report a problem (T66): the error details to the clipboard, then the issue form in the
 *  user's browser (opened by the backend). Nothing is sent: the user pastes and submits. */
export async function reportProblem(t: (k: "reportOpened" | "reportOpenedNoCopy" | "reportOpenHere", v?: Record<string, string>) => string,
  toast: (x: { kind: "info" | "error"; text: string; ms?: number }) => void): Promise<void> {
  let copied = false;
  try { copied = await copyText((await api.diagnostics()).text); } catch { /* the form still helps */ }
  try {
    const r = await api.reportProblem();
    if (r.opened) toast({ kind: "info", text: t(copied ? "reportOpened" : "reportOpenedNoCopy"), ms: 10000 });
    else toast({ kind: "info", text: t("reportOpenHere", { url: r.url }), ms: 20000 });
  } catch (e) {
    toast({ kind: "error", text: String((e as Error).message) });
  }
}
