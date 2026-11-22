/**
 * CP1 (owner, 2026-11-18): a plot or a tab for a Confluence page, every sample interactive (app/report.py
 * build_clip_*). The page with all the data is saved - the user drags it onto the Confluence page (an
 * attachment); the clipboard's text/plain is the HTML macro's few lines that show that attachment (zoom, the
 * cursor, lines on and off; a whole page inside the macro stalled the owner's editor), its text/html a picture,
 * the statistics table and the notes without scripts - what a page without the macro, Word or an e-mail keeps.
 * CP3: with the Signal Viewer user macro (Settings; Confluence Data Center keeps the HTML macro off) text/plain is
 * {signalviewer:file=...}, pasted with Insert > Markup.
 */
import { api } from "./api";
import { pickPath, rangeKey, useApp, type Plot, type Tab } from "./store";
import { translate } from "./i18n";
import { prompt } from "./components/Overlays";
import { pagePlots, plotSpec } from "./plotSpec";

/** What a plot or a tab sends: its title, its notes, its plots as the report would show them; null: nothing to send. */
function clipContent(tab: Tab, only?: Plot) {
  const st = useApp.getState(), lang = st.lang;
  const plotLabel = translate(lang, "plotTitle", { n: "{n}" });
  // what a report would show (maps and 3D views too: their own offline pages, in the attachment)
  const kept = pagePlots(tab).filter(({ p, include }) => include && (!only || p.id === only.id));
  if (!kept.length) { st.toast({ kind: "error", text: translate(lang, "clipEmpty") }); return null; }
  // the notes: all of them for a tab; for one plot those within what it shows
  const range = only ? st.ranges[rangeKey(tab, only)] ?? null : null;
  const notes = (st.ws.notes ?? []).filter((n) => n.status !== "rejected" && (!range || ((n.t2 ?? n.t) >= range[0] && n.t <= range[1])))
    .map((n) => ({ t: n.t, ...(n.t2 !== undefined ? { t2: n.t2 } : {}), text: n.text }));
  const title = only ? only.title || plotLabel.replace("{n}", String(tab.plots.indexOf(only) + 1)) : tab.name || "";
  return { title, lang, theme: "light", notes, macro: st.confluenceMacro,
    tabs: [{ name: tab.name || "", plots: kept.map(({ p, pi }) => plotSpec(tab, p, pi, plotLabel)) }] };
}

export async function copyForConfluence(tab: Tab, only?: Plot) {
  const st = useApp.getState(), lang = st.lang;
  const content = clipContent(tab, only);
  if (!content) return;
  const { title } = content;
  const path = await pickPath({ mode: "save", title: translate(lang, "clipSave"), exts: [".html"],
    defaultName: `${(title || "signalviewer").replace(/[\\/:*?"<>|]+/g, "_").slice(0, 60)}.html` });
  if (!path) return;
  const body = { path, ...content };
  // ClipboardItem takes promises: the write starts inside the click (its permission) while the server builds it
  const res = api.clip(body);
  try {
    await navigator.clipboard.write([new ClipboardItem({
      "text/plain": res.then((r) => new Blob([r.macro], { type: "text/plain" })),
      "text/html": res.then((r) => new Blob([r.static], { type: "text/html" })),
    })]);
    const r = await res;
    const kb = Math.max(1, Math.round(r.size / 1024));
    st.toast({ kind: "info", text: translate(lang, st.confluenceMacro === "user" ? "clipDoneUser" : "clipDone", { name: r.name, size: kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb} kB` }) });
  } catch {
    // the server's own words when it was the one that failed (a signal no longer open...), else the clipboard's
    // (the file is saved all the same: its macro lines can be copied again)
    const r = await res.then((x) => x, (e: Error) => e);
    st.toast({ kind: "error", text: r instanceof Error ? r.message : translate(lang, "clipFailed", { name: r.name }) });
  }
}

/** CP3: the user macro's template saved for the Confluence administrator (Settings). */
export async function saveConfluenceMacro() {
  const st = useApp.getState(), lang = st.lang;
  const path = await pickPath({ mode: "save", title: translate(lang, "setConfluenceSave"), exts: [".txt"], defaultName: "signalviewer-confluence-macro.txt" });
  if (!path) return;
  try {
    const m = await api.clipUserMacro();
    const r = await api.saveText(path, m.template, ".txt", false);
    st.toast({ kind: "info", text: translate(lang, "setConfluenceSaved", { path: r.path }) });
  } catch (e) {
    st.toast({ kind: "error", text: (e as Error).message });
  }
}

/** CP4 (owner, 2026-11-22: "the easiest way to throw an interactive plot straight to Confluence"): the plot or tab sent
 *  to a Confluence page - attached and its macro added by the app (Confluence's REST API, a token in Settings). The one
 *  question: which page (its link; the last one offered). */
export async function sendToConfluence(tab: Tab, only?: Plot) {
  const st = useApp.getState(), lang = st.lang;
  const tr = (k: string, v: Record<string, string | number> = {}) => translate(lang, k as never, v);
  const content = clipContent(tab, only);
  if (!content) return;
  const info = await api.confluence().catch(() => null);
  if (!info?.url || !info.hasToken) {
    st.toast({ kind: "info", text: tr("cfNotSet"), action: { label: tr("cfOpenSettings"), run: () => useApp.setState({ settingsOpen: true }) } });
    return;
  }
  const page = await prompt(tr("cfSendTitle", { what: content.title || tr("cfThis") }), tr("cfPageLabel"), info.recent[0]?.url ?? "");
  if (!page?.trim()) return;
  st.toast({ kind: "info", text: tr("cfSending", { page: info.recent.find((r) => r.url === page.trim())?.title ?? page.trim() }) });
  try {
    const r = await api.confluenceSend({ page: page.trim(), ...content });
    const kb = Math.max(1, Math.round(r.size / 1024));
    useApp.getState().toast({ kind: "info", text: tr(r.added ? "cfSent" : "cfSentAgain", { name: r.name, page: r.page, size: kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb} kB` }),
      action: { label: tr("cfOpenPage"), run: () => { void api.confluenceOpen(); } } });
  } catch (e) {
    useApp.getState().toast({ kind: "error", text: (e as Error).message });
  }
}

