import { useState } from "react";
import { actions, activeTab, pickPath, useApp, type ReportMeta } from "../store";
import { translate, useT } from "../i18n";
import { plotSpec } from "../plotSpec";
import { runJob } from "../files";
import { api } from "../api";

const DEFAULT: ReportMeta = { title: "", intro: "", summary: "", lang: "he", theme: "light", scope: "tab" };

export default function ReportPanel() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const ws = useApp((s) => s.ws);
  const meta: ReportMeta = { ...DEFAULT, lang, ...(ws.report ?? {}) };
  const [busy, setBusy] = useState<string | null>(null);
  const tabs = meta.scope === "all" ? ws.tabs : [activeTab(ws)];

  const setMeta = (patch: Partial<ReportMeta>) =>
    useApp.getState().commit((w) => { w.report = { ...DEFAULT, lang, ...(w.report ?? {}), ...patch }; return w; });

  const buildBody = (format: string, path: string) => {
    const plotLabel = translate(meta.lang, "plotTitle", { n: "{n}" });
    return {
      path, format, title: meta.title, intro: meta.intro, summary: meta.summary, lang: meta.lang, theme: meta.theme,
      notes: (ws.notes ?? []).map((n) => ({ t: n.t, text: n.text })),
      tabs: tabs.map((tab, i) => ({
        name: tab.name || `${translate(meta.lang, "tab")} ${ws.tabs.indexOf(tab) + 1 || i + 1}`,
        plots: tab.plots.map((p, pi) => ({ p, pi })).filter(({ p }) => !p.excludeFromReport && p.signals.length)
          .map(({ p, pi }) => plotSpec(tab, p, pi, plotLabel)),
      })).filter((tb) => tb.plots.length),
    };
  };
  const preview = async () => {
    const body = buildBody("html", "");
    if (!body.tabs.length) { useApp.getState().toast({ kind: "error", text: t("reportEmpty") }); return; }
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
      const plotLabel = translate(meta.lang, "plotTitle", { n: "{n}" });
      const body = {
        path, format, title: meta.title, intro: meta.intro, summary: meta.summary, lang: meta.lang, theme: meta.theme,
      notes: (ws.notes ?? []).map((n) => ({ t: n.t, text: n.text })),
        tabs: tabs.map((tab, i) => ({
          name: tab.name || `${translate(meta.lang, "tab")} ${ws.tabs.indexOf(tab) + 1 || i + 1}`,
          plots: tab.plots.map((p, pi) => ({ p, pi })).filter(({ p }) => !p.excludeFromReport && p.signals.length)
            .map(({ p, pi }) => plotSpec(tab, p, pi, plotLabel)),
        })).filter((tb) => tb.plots.length),
      };
      if (!body.tabs.length) throw new Error(t("reportEmpty"));
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

        <h3 className="alist-head">{t("reportPlots")}</h3>
        {tabs.map((tab) => tab.plots.filter((p) => p.signals.length).map((p) => {
          const idx = tab.plots.indexOf(p);
          return (
            <div key={p.id} className={`rplot${p.excludeFromReport ? " off" : ""}`}>
              <label className="acheck">
                <input type="checkbox" checked={!p.excludeFromReport} onChange={(e) => actions.updatePlot(p.id, { excludeFromReport: !e.target.checked })} />
                <span className="rplot-name">{p.title || t("plotTitle", { n: idx + 1 })}{meta.scope === "all" && tab.name ? ` · ${tab.name}` : ""}</span>
              </label>
              {!p.excludeFromReport && (
                <textarea key={"c" + p.id + (p.caption ?? "")} rows={2} placeholder={t("captionHint")} defaultValue={p.caption ?? ""}
                  onBlur={(e) => e.target.value !== (p.caption ?? "") && actions.updatePlot(p.id, { caption: e.target.value })} />
              )}
            </div>
          );
        }))}
        {tabs.every((tab) => tab.plots.every((p) => !p.signals.length)) && <p className="hint">{t("reportEmpty")}</p>}

        <label className="afield" style={{ marginTop: 12 }}><span>{t("summary")}</span>
          <textarea key={"s" + meta.summary} rows={3} defaultValue={meta.summary} onBlur={(e) => e.target.value !== meta.summary && setMeta({ summary: e.target.value })} /></label>

        <div className="arow">
          <button className="btn outline" style={{ flex: "0 0 auto" }} disabled={!!busy} onClick={preview}>{busy === "preview" ? t("loading") : t("reportPreview")}</button>
          <button className="btn primary" disabled={!!busy} onClick={() => make("html")}>{busy === "html" ? t("loading") : t("makeHtml")}</button>
        </div>
        <p className="hint" style={{ fontSize: 12, margin: "6px 0 10px" }}>{t("htmlHint")}</p>
        <div className="arow">
          <button className="btn outline" disabled={!!busy} onClick={() => make("pdf")}>{busy === "pdf" ? t("loading") : "PDF"}</button>
          <button className="btn outline" disabled={!!busy} onClick={() => make("docx")}>{busy === "docx" ? t("loading") : "Word"}</button>
        </div>
      </div>
    </aside>
  );
}
