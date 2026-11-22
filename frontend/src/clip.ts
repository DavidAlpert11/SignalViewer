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
import { choose, prompt } from "./components/Overlays";
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
  // CP6: where on the page - a marker the page holds for it wins; sent again it stays where it is; else the user says
  let where = "end";
  try {
    const o = await api.confluenceOutline({ page: page.trim(), title: content.title });
    if (!o.marker && !o.shows) {
      const options = [{ value: "end", label: tr("cfWhereEnd") }, { value: "start", label: tr("cfWhereStart") },
        ...o.headings.map((h, i) => ({ value: `after:${i}`, label: `${"   ".repeat(Math.max(0, h.level - 1))}${tr("cfWhereAfter")} “${h.text}”` }))];
      const w = await choose(tr("cfWhereTitle", { page: o.page }), tr("cfWhereLabel"), options, "end", tr("cfWhereNote"));
      if (w === null) return;
      where = w;
    }
  } catch (e) {
    useApp.getState().toast({ kind: "error", text: (e as Error).message });
    return;
  }
  st.toast({ kind: "info", text: tr("cfSending", { page: info.recent.find((r) => r.url === page.trim())?.title ?? page.trim() }) });
  try {
    const r = await api.confluenceSend({ page: page.trim(), ...content, where });
    const kb = Math.max(1, Math.round(r.size / 1024));
    useApp.getState().toast({ kind: "info", text: tr(r.link ? "cfSentLink" : r.added ? "cfSent" : "cfSentAgain", { name: r.name, page: r.page, size: kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb} kB` }),
      action: { label: tr("cfOpenPage"), run: () => { void api.confluenceOpen(); } } });
  } catch (e) {
    useApp.getState().toast({ kind: "error", text: (e as Error).message });
  }
}

/* CP5 (owner, 2026-11-22: "hold the plot or the tab by its grip and drag it out - to Confluence or any file; HTML by
   default, else ask how"): a drag that leaves the window carries the plot (or the tab) three ways at once, and the
   place it is dropped takes the one it can -
   - a folder or the desktop: the interactive page as a file (DownloadURL: the system fetches it from the app at the
     drop - Chromium: Edge, Chrome, the desktop window's WebView2),
   - Word, an e-mail, an editor (Confluence's too): its picture with the title (text/html),
   - a browser (its tab strip or a page): the page itself, opened (text/uri-list - shown, not downloaded),
   - anything that takes text: its title.
   A web page cannot be given a file by a drag from another window, so a Confluence page gets the picture: after a drop
   outside the app a toast offers the other ways - Send to Confluence (live in the page), Copy for Confluence. */
let dropInside = 0;
if (typeof window !== "undefined") window.addEventListener("drop", () => { dropInside = Date.now(); }, true);

function pictureOf(ids: string[], title: string): string {
  const parts = [`<h3>${title.replace(/[<&]/g, (c) => (c === "<" ? "&lt;" : "&amp;"))}</h3>`];
  for (const id of ids) {
    const cvs = [...document.querySelectorAll<HTMLCanvasElement>(`[data-plot="${id}"] canvas`)].sort((a, b) => b.width * b.height - a.width * a.height)[0];
    if (!cvs) continue;
    try {
      parts.push(`<p><img alt="${title.replace(/"/g, "&quot;")}" width="${Math.min(900, cvs.clientWidth || cvs.width)}" src="${cvs.toDataURL("image/png")}"></p>`);
    } catch { /* a canvas that cannot be read: the title alone */ }
  }
  return parts.join("");
}

/** At the drag's start (the plot's grip, a tab): the three ways, set at once (a drag cannot wait for the server). */
export function dragOutStart(e: React.DragEvent, tab: Tab, only?: Plot, shown?: string) {
  const st = useApp.getState();
  const kept = pagePlots(tab).filter(({ p, include }) => include && (!only || p.id === only.id));
  if (!kept.length) return;
  const plotLabel = translate(st.lang, "plotTitle", { n: "{n}" });
  const title = only ? only.title || plotLabel.replace("{n}", String(tab.plots.indexOf(only) + 1)) : tab.name || shown || "Signal Viewer";
  const token = (crypto.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`);
  const name = `${title.replace(/[\\/:*?"<>|]+/g, "_").slice(0, 60) || "signalviewer"}.html`;
  const range = only ? st.ranges[rangeKey(tab, only)] ?? null : null;
  const notes = (st.ws.notes ?? []).filter((n) => n.status !== "rejected" && (!range || ((n.t2 ?? n.t) >= range[0] && n.t <= range[1])))
    .map((n) => ({ t: n.t, ...(n.t2 !== undefined ? { t2: n.t2 } : {}), text: n.text }));
  void api.dragRegister({ token, title, lang: st.lang, theme: "light", notes,
    tabs: [{ name: tab.name || "", plots: kept.map(({ p, pi }) => plotSpec(tab, p, pi, plotLabel)) }] }).catch(() => {});
  const link = `${location.origin}/api/export/drag/${token}/${encodeURIComponent(name)}`;
  e.dataTransfer.setData("DownloadURL", `text/html:${name}:${link}`);
  e.dataTransfer.setData("text/uri-list", `${link}?view=1`);          // a browser it is dropped on opens the page
  e.dataTransfer.setData("text/html", pictureOf(kept.map(({ p }) => p.id), title));
  e.dataTransfer.setData("text/plain", title);
}

/** At the drag's end: dropped outside the app - the other ways offered (the app cannot know where it went). */
export function dragOutEnd(e: React.DragEvent, tab: Tab, only?: Plot) {
  if (e.dataTransfer.dropEffect === "none" || Date.now() - dropInside < 1500) return;
  const st = useApp.getState(), tr = (k: string) => translate(st.lang, k as never);
  st.toast({ kind: "info", text: tr("dragOutDone"),
    action: { label: tr("cfSendPlot"), run: () => { void sendToConfluence(tab, only); } },
    action2: { label: tr("clipPlot"), run: () => { void copyForConfluence(tab, only); } }, ms: 12000 });
}

