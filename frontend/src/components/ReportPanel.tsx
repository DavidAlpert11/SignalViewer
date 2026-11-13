import { useState } from "react";
import { actions, activeTab, pickPath, rangeKey, useApp, type ReportMeta } from "../store";
import { investigationSections } from "../investigation";
import { translate, useT } from "../i18n";
import { pagePlots, plotSpec } from "../plotSpec";
import { runJob } from "../files";
import { api } from "../api";
import { makeReplay, replayInfo } from "../replay";
import { Icon } from "../icons";

const DEFAULT: ReportMeta = { title: "", intro: "", summary: "", lang: "he", theme: "light", scope: "tab" };

export default function ReportPanel() {
  const t = useT();
  const [capOpen, setCapOpen] = useState<string[]>([]);
  const lang = useApp((s) => s.lang);
  const ws = useApp((s) => s.ws);
  const meta: ReportMeta = { ...DEFAULT, lang, ...(ws.report ?? {}) };
  const [busy, setBusy] = useState<string | null>(null);
  const tabs = meta.scope === "all" ? ws.tabs : [activeTab(ws)];

  const setMeta = (patch: Partial<ReportMeta>) =>
    useApp.getState().commit((w) => { w.report = { ...DEFAULT, lang, ...(w.report ?? {}), ...patch }; return w; });

  const notes = ws.notes ?? [];
  const hasInvestigation = notes.some((n) => n.status) || (ws.conditions ?? []).length > 0 || useApp.getState().journal.length > 0;
  const withInvestigation = hasInvestigation && meta.investigation !== false;
  // 26.U4: Compare's verdict ("Report…" in Compare), first in the report
  const withVerdict = !!meta.verdict && meta.includeVerdict !== false;
  const buildBody = async (format: string, path: string) => {
    const plotLabel = translate(meta.lang, "plotTitle", { n: "{n}" });
    // occurrences plots are not drawn in reports yet (they need a condition's stretches)
    const tabSpecs = tabs.map((tab, i) => ({
      name: tab.name || `${translate(meta.lang, "tab")} ${ws.tabs.indexOf(tab) + 1 || i + 1}`,
      // L11 / 1.26: a map with objects - in 2D or in 3D - is in the report too, drawn by the server (plotSpec.ts pagePlot)
      plots: pagePlots(tab).filter(({ p, include }) => include && !p.excludeFromReport)
        .map(({ p, pi }) => plotSpec(tab, p, pi, plotLabel)),
    })).filter((tb) => tb.plots.length);
    // Investigation step 6: each finding with its view - the time plots of that tab, at that zoom
    const evidence = withInvestigation ? notes.filter((n) => n.status && n.status !== "rejected" && n.view).flatMap((n) => {
      const tab = ws.tabs.find((x) => x.id === n.view!.tab);
      if (!tab) return [];
      return tab.plots.map((p, pi) => ({ p, pi })).filter(({ p }) => (p.mode ?? "time") === "time" && p.signals.length).slice(0, 2)
        .map(({ p, pi }) => ({ ...plotSpec(tab, p, pi, plotLabel), range: n.view!.ranges[rangeKey(tab, p)] ?? (n.t2 !== undefined ? [n.t - (n.t2 - n.t), n.t2 + (n.t2 - n.t)] : null),
          title: n.text, caption: translate(meta.lang, `fs_${n.status}` as "fs_open") }));
    }) : [];
    return {
      path, format, title: meta.title, intro: meta.intro, summary: meta.summary, lang: meta.lang, theme: meta.theme,
      notes: notes.filter((n) => !n.status || !withInvestigation).map((n) => ({ t: n.t, ...(n.t2 !== undefined ? { t2: n.t2 } : {}), text: n.text })),
      sections: [
        ...(withVerdict ? [{ title: meta.verdict!.title, items: meta.verdict!.summary, table: { head: meta.verdict!.head, rows: meta.verdict!.rows } }] : []),
        ...(withInvestigation ? await investigationSections(meta.lang) : []),
      ],
      tabs: [...(evidence.length ? [{ name: translate(meta.lang, "rFindings"), plots: evidence }] : []), ...tabSpecs],
      // 1.26: an HTML report is one live page - one time for its plots, maps and 3D views (Play, the marks)
      ...(format === "html" ? { replay: replayInfo(meta.lang, false) } : {}),
    };
  };
  const preview = async () => {
    const body = await buildBody("html", "");
    if (!body.tabs.length && !body.sections.length) { useApp.getState().toast({ kind: "error", text: t("reportEmpty") }); return; }
    setBusy("preview");
    try { useApp.setState({ reportPreviewHtml: (await api.reportPreview(body)).html }); }
    catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
    finally { setBusy(null); }
  };
  const make = async (format: "html" | "pdf" | "docx") => {
    const ext = { html: ".html", pdf: ".pdf", docx: ".docx" }[format];
    const base = (meta.title || "report").replace(/[\\/:*?"<>|]+/g, "_").slice(0, 60);
    const path = await pickPath({ mode: "save", title: t("saveReport"), exts: [ext], defaultName: base + ext });
    if (!path) return;
    setBusy(format);
    try {
      const body = await buildBody(format, path);
      if (!body.tabs.length && !body.sections.length) throw new Error(t("reportEmpty"));
      const r = await runJob<{ path: string }>("report", body, translate(lang, "creatingReport"));
      if (r) useApp.getState().toast({ kind: "info", text: translate(lang, "savedTo", { path: r.path }) });
    } catch (e) {
      useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
    } finally { setBusy(null); }
  };
  return (
    <aside className="side" aria-label={t("report")}>
      <div className="side-head"><h2>{t("report")}</h2></div>
      <div className="tree analysis">
        {/* R1: the tab as a page to send - first, since it is the quickest thing to make here */}
        <section className="replay-card" aria-labelledby="replay-h">
          <h3 id="replay-h"><Icon.Send aria-hidden="true" />{t("replayTitle")}</h3>
          <p>{t("replayText")}</p>
          <button className="btn primary replay-make" disabled={!!busy} onClick={() => makeReplay()}>{t("replayMake")}</button>
        </section>
        <label className="afield"><span>{t("reportTitle")}</span>
          <input key={"t" + meta.title} defaultValue={meta.title} onBlur={(e) => e.target.value !== meta.title && setMeta({ title: e.target.value })} /></label>
        <label className="afield"><span>{t("reportIntro")}</span>
          <textarea key={"i" + meta.intro} rows={3} defaultValue={meta.intro} onBlur={(e) => e.target.value !== meta.intro && setMeta({ intro: e.target.value })} /></label>
        <div className="arow">
          <label className="afield"><span>{t("reportLang")}</span>
            <select value={meta.lang} onChange={(e) => setMeta({ lang: e.target.value as "en" | "he" })}>
              <option value="he">עברית</option><option value="en">English</option></select></label>
          <label className="afield"><span>{t("theme")}</span>
            <select value={meta.theme} onChange={(e) => setMeta({ theme: e.target.value as "light" | "dark" })}>
              <option value="light">{t("light")}</option><option value="dark">{t("dark")}</option></select></label>
        </div>
        <div className="seg wide">
          <button className={meta.scope === "tab" ? "on" : ""} onClick={() => setMeta({ scope: "tab" })}>{t("scopeTab")}</button>
          <button className={meta.scope === "all" ? "on" : ""} onClick={() => setMeta({ scope: "all" })}>{t("scopeAll")}</button>
        </div>

        {meta.verdict && (
          <label className="acheck rverdict">
            <input type="checkbox" checked={withVerdict} onChange={(e) => setMeta({ includeVerdict: e.target.checked })} />
            <span>{t("rVerdict")} <span className="muted">· {meta.verdict.title}</span></span>
          </label>
        )}
        {hasInvestigation && (
          <label className="acheck rinv">
            <input type="checkbox" className="report-investigation" checked={withInvestigation} onChange={(e) => setMeta({ investigation: e.target.checked })} />
            <span>{t("rInclude")}</span>
          </label>
        )}
        {withInvestigation && <p className="hint">{t("rIncludeHint")}</p>}
        <h3 className="alist-head">{t("reportPlots")}</h3>
        {tabs.map((tab) => pagePlots(tab).filter((x) => x.include || x.why !== "pageWhyEmpty").map(({ p, pi: idx, include, why }) => {
          if (!include) return (   // 1.26: listed with the reason it cannot be in a report, not left out without a word
            <div key={p.id} className="rplot off" title={t(why!)}>
              <label className="acheck"><input type="checkbox" checked={false} disabled />
                <span className="rplot-name">{p.title || t("plotTitle", { n: idx + 1 })}{meta.scope === "all" && tab.name ? ` · ${tab.name}` : ""} <span className="muted">· {t(why!)}</span></span></label>
            </div>
          );
          return (
            <div key={p.id} className={`rplot${p.excludeFromReport ? " off" : ""}`}>
              <label className="acheck">
                <input type="checkbox" checked={!p.excludeFromReport} onChange={(e) => actions.updatePlot(p.id, { excludeFromReport: !e.target.checked })} />
                <span className="rplot-name">{p.title || t("plotTitle", { n: idx + 1 })}{meta.scope === "all" && tab.name ? ` · ${tab.name}` : ""}</span>
              </label>
              {/* review R5: a caption box only when wanted (one under every plot made the panel a long form) */}
              {!p.excludeFromReport && (p.caption || capOpen.includes(p.id) ? (
                <textarea key={"c" + p.id + (p.caption ?? "")} rows={2} placeholder={t("captionHint")} defaultValue={p.caption ?? ""} autoFocus={!p.caption}
                  onBlur={(e) => { if (e.target.value !== (p.caption ?? "")) actions.updatePlot(p.id, { caption: e.target.value });
                    if (!e.target.value) setCapOpen((c) => c.filter((x) => x !== p.id)); }} />
              ) : <button className="linklike rplot-cap" onClick={() => setCapOpen((c) => [...c, p.id])}>{t("rAddCaption")}</button>)}
            </div>
          );
        }))}
        {tabs.every((tab) => pagePlots(tab).every((x) => !x.include)) && <p className="hint">{t("reportEmpty")}</p>}

        <label className="afield" style={{ marginTop: 12 }}><span>{t("summary")}</span>
          <textarea key={"s" + meta.summary} rows={3} defaultValue={meta.summary} onBlur={(e) => e.target.value !== meta.summary && setMeta({ summary: e.target.value })} /></label>

        <div className="arow">
          <button className="btn outline" style={{ flex: "0 0 auto" }} disabled={!!busy} onClick={preview}>{busy === "preview" ? t("loading") : t("reportPreview")}</button>
          <button className="btn primary" disabled={!!busy} onClick={() => make("html")}>{busy === "html" ? t("loading") : t("makeHtml")}</button>
        </div>
        <p className="hint" style={{ fontSize: "var(--fs-m)", margin: "6px 0 10px" }}>{t("htmlHint")}</p>
        <div className="arow">
          <button className="btn outline" disabled={!!busy} onClick={() => make("pdf")}>{busy === "pdf" ? t("loading") : "PDF"}</button>
          <button className="btn outline" disabled={!!busy} onClick={() => make("docx")}>{busy === "docx" ? t("loading") : "Word"}</button>
        </div>
      </div>
    </aside>
  );
}
