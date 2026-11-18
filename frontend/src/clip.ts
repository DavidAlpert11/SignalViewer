/**
 * CP1 (owner, 2026-11-18): a plot or a tab for a Confluence page. One copy, two flavours (app/report.py
 * build_clip_*): text/plain is the interactive page for Confluence's HTML macro (Insert -> HTML, paste -
 * zoom, the cursor, lines on and off; kept small: a 4 MB page brought the owner's editor down), text/html is
 * a picture, the statistics table and the notes without scripts - what a page without the macro, Word or an
 * e-mail keeps when it is pasted straight in (a paste never carries scripts).
 */
import { api } from "./api";
import { rangeKey, useApp, type Plot, type Tab } from "./store";
import { translate } from "./i18n";
import { pagePlots, plotSpec } from "./plotSpec";

/** Maps and 3D views stay out: their pages carry their tiles / three.js (megabytes) - saved and attached instead. */
const clipPlot = (p: Plot) => p.mode !== "3d" && !(p.objects?.length);

export async function copyForConfluence(tab: Tab, only?: Plot) {
  const st = useApp.getState(), lang = st.lang;
  const plotLabel = translate(lang, "plotTitle", { n: "{n}" });
  const all = pagePlots(tab).filter(({ p, include }) => include && (!only || p.id === only.id));
  const kept = all.filter(({ p }) => clipPlot(p));
  if (!kept.length) { st.toast({ kind: "error", text: translate(lang, all.length ? "clipNoMaps" : "clipEmpty") }); return; }
  // the notes: all of them for a tab; for one plot those within what it shows
  const range = only ? st.ranges[rangeKey(tab, only)] ?? null : null;
  const notes = (st.ws.notes ?? []).filter((n) => n.status !== "rejected" && (!range || ((n.t2 ?? n.t) >= range[0] && n.t <= range[1])))
    .map((n) => ({ t: n.t, ...(n.t2 !== undefined ? { t2: n.t2 } : {}), text: n.text }));
  const body = {
    title: only ? only.title || plotLabel.replace("{n}", String(tab.plots.indexOf(only) + 1)) : tab.name || "", lang, theme: "light", notes,
    tabs: [{ name: tab.name || "", plots: kept.map(({ p, pi }) => plotSpec(tab, p, pi, plotLabel)) }],
  };
  // ClipboardItem takes promises: the write starts inside the click (its permission) while the server builds it
  const res = api.clip(body);
  try {
    await navigator.clipboard.write([new ClipboardItem({
      "text/plain": res.then((r) => new Blob([r.html], { type: "text/plain" })),
      "text/html": res.then((r) => new Blob([r.static], { type: "text/html" })),
    })]);
    const r = await res;
    const kb = Math.max(1, Math.round(r.size / 1024));
    const left = all.length - kept.length;
    st.toast({ kind: "info", text: translate(lang, "clipDone", { size: kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb} kB` })
      + (left ? " " + translate(lang, "clipLeftOut", { n: left }) : "") });
  } catch {
    // the server's own words when it was the one that failed (a signal no longer open...), else the clipboard's
    const why = await res.then(() => null, (e: Error) => e.message);
    st.toast({ kind: "error", text: why ?? translate(lang, "clipFailed") });
  }
}
