/**
 * CP1 (owner, 2026-11-18): a plot or a tab for a Confluence page, every sample interactive (app/report.py
 * build_clip_*). The page with all the data is saved - the user drags it onto the Confluence page (an
 * attachment); the clipboard's text/plain is the HTML macro's few lines that show that attachment (zoom, the
 * cursor, lines on and off; a whole page inside the macro stalled the owner's editor), its text/html a picture,
 * the statistics table and the notes without scripts - what a page without the macro, Word or an e-mail keeps.
 */
import { api } from "./api";
import { pickPath, rangeKey, useApp, type Plot, type Tab } from "./store";
import { translate } from "./i18n";
import { pagePlots, plotSpec } from "./plotSpec";

export async function copyForConfluence(tab: Tab, only?: Plot) {
  const st = useApp.getState(), lang = st.lang;
  const plotLabel = translate(lang, "plotTitle", { n: "{n}" });
  // what a report would show (maps and 3D views too: their own offline pages, in the attachment)
  const kept = pagePlots(tab).filter(({ p, include }) => include && (!only || p.id === only.id));
  if (!kept.length) { st.toast({ kind: "error", text: translate(lang, "clipEmpty") }); return; }
  // the notes: all of them for a tab; for one plot those within what it shows
  const range = only ? st.ranges[rangeKey(tab, only)] ?? null : null;
  const notes = (st.ws.notes ?? []).filter((n) => n.status !== "rejected" && (!range || ((n.t2 ?? n.t) >= range[0] && n.t <= range[1])))
    .map((n) => ({ t: n.t, ...(n.t2 !== undefined ? { t2: n.t2 } : {}), text: n.text }));
  const title = only ? only.title || plotLabel.replace("{n}", String(tab.plots.indexOf(only) + 1)) : tab.name || "";
  const path = await pickPath({ mode: "save", title: translate(lang, "clipSave"), exts: [".html"],
    defaultName: `${(title || "signalviewer").replace(/[\\/:*?"<>|]+/g, "_").slice(0, 60)}.html` });
  if (!path) return;
  const body = { path, title, lang, theme: "light", notes, tabs: [{ name: tab.name || "", plots: kept.map(({ p, pi }) => plotSpec(tab, p, pi, plotLabel)) }] };
  // ClipboardItem takes promises: the write starts inside the click (its permission) while the server builds it
  const res = api.clip(body);
  try {
    await navigator.clipboard.write([new ClipboardItem({
      "text/plain": res.then((r) => new Blob([r.macro], { type: "text/plain" })),
      "text/html": res.then((r) => new Blob([r.static], { type: "text/html" })),
    })]);
    const r = await res;
    const kb = Math.max(1, Math.round(r.size / 1024));
    st.toast({ kind: "info", text: translate(lang, "clipDone", { name: r.name, size: kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb} kB` }) });
  } catch {
    // the server's own words when it was the one that failed (a signal no longer open...), else the clipboard's
    // (the file is saved all the same: its macro lines can be copied again)
    const r = await res.then((x) => x, (e: Error) => e);
    st.toast({ kind: "error", text: r instanceof Error ? r.message : translate(lang, "clipFailed", { name: r.name }) });
  }
}
