/* RE1 (owner, 2026-11-18): the report as a document - written like Markdown, with the session's plots, tabs and
   values in it, a live preview beside it, and the same page / PDF / Word out of it. It replaces the Report side
   panel (one way to make a report): an old session's report opens as the document its form made (reportDoc.ts).
   The rail's Report button (and Ctrl+K) shows it in place of the plots; the same button goes back. */
import { useEffect, useMemo, useRef, useState } from "react";
import { activeTab, pickPath, rangeKey, useApp, type ReportMeta } from "../store";
import { translate, useT } from "../i18n";
import { api } from "../api";
import { runJob } from "../files";
import { replayFileName } from "../replay";
import { Icon } from "../icons";
import { confirmAsk } from "./Overlays";
import { refFor, wordAt } from "../formulaRefs";
import { fuzzySort } from "../fuzzy";
import { DOC_STATS, SPECIALS, defaultDocText, docBody, docText, metaOf, plotRef, tabRef } from "../reportDoc";

type View = "write" | "both" | "show";
const FUNCS = [...DOC_STATS, "stretches", "holds"];

/** Commit the text (one undo step per pause in typing, or when the editor is left). */
function commitText(text: string) {
  const st = useApp.getState();
  if (docText(st.ws, st.lang) === text && st.ws.report?.doc) return;
  st.commit((w) => { w.report = { ...metaOf(w, st.lang), doc: { v: 1, text } }; return w; });
}

/** Put text at the editor's caret (the library, the value form, a toolbar button) - or at the end. */
function insertAt(el: HTMLTextAreaElement | null, text: string, setText: (s: string) => void, wrap?: [string, string]) {
  if (!el) return;
  const a = el.selectionStart ?? el.value.length, b = el.selectionEnd ?? a;
  const sel = el.value.slice(a, b);
  const piece = wrap ? wrap[0] + (sel || text) + wrap[1] : text;
  const v = el.value.slice(0, a) + piece + el.value.slice(b);
  setText(v);
  requestAnimationFrame(() => {
    el.focus();
    const at = wrap && !sel ? a + wrap[0].length : a + piece.length;
    el.setSelectionRange(at, wrap && !sel ? at + text.length : at);
  });
}

/** A block (a plot, a heading) goes on a line of its own, with an empty line around it. */
function asBlock(el: HTMLTextAreaElement | null, block: string) {
  if (!el) return block;
  const before = el.value.slice(0, el.selectionStart ?? 0);
  const after = el.value.slice(el.selectionEnd ?? 0);
  return (before && !before.endsWith("\n\n") ? (before.endsWith("\n") ? "\n" : "\n\n") : "") + block + (after.startsWith("\n\n") ? "" : after.startsWith("\n") ? "\n" : "\n\n");
}

const SCROLL_JS = "<script>(function(){addEventListener('scroll',function(){parent.postMessage({svDocScroll:scrollY},'*')});"
  + "addEventListener('message',function(e){if(e.data&&typeof e.data.svDocScrollTo==='number')scrollTo(0,e.data.svDocScrollTo)})})();</script>";

export default function ReportScreen() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const ws = useApp((s) => s.ws);
  const runs = useApp((s) => s.runs);
  const meta: ReportMeta = metaOf(ws, lang);
  const stored = docText(ws, lang);
  const [text, setText] = useState(stored);
  const [view, setView] = useState<View>(() => { try { return (localStorage.getItem("sv.rdView") as View) || "both"; } catch { return "both"; } });
  const [dir, setDir] = useState<"rtl" | "ltr">(meta.lang === "he" ? "rtl" : "ltr");
  const [html, setHtml] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const [updating, setUpdating] = useState(false);
  const [caret, setCaret] = useState(0);
  const [help, setHelp] = useState(false);
  const ed = useRef<HTMLTextAreaElement>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const scrollY = useRef(0);
  const typing = useRef(false);

  // the stored text changed from outside (undo, Add to report, a session opened): follow it
  useEffect(() => { if (!typing.current) setText(stored); }, [stored]);
  // one commit per pause in typing
  useEffect(() => {
    if (text === stored) return;
    const id = setTimeout(() => { typing.current = false; commitText(text); }, 900);
    return () => clearTimeout(id);
  }, [text, stored]);
  useEffect(() => { try { localStorage.setItem("sv.rdView", view); } catch { /* per viewer only */ } }, [view]);

  // the live preview: the page the .html file will be, a moment after the text (or the data) changes
  const version = useApp((s) => s.runs.map((r) => r.version ?? r.id).join(","));
  useEffect(() => {
    if (view === "write") return;
    let gone = false;
    const id = setTimeout(async () => {
      setUpdating(true);
      try {
        const { body, prepared } = await docBody("html", "", text);
        const r = await api.reportPreview(body);
        if (gone) return;
        setProblems(prepared.problems);
        setHtml(r.html);
        useApp.setState({ reportPreviewHtml: r.html });
      } catch (e) {
        if (!gone) setProblems([String((e as Error).message)]);
      } finally { if (!gone) setUpdating(false); }
    }, 500);
    return () => { gone = true; clearTimeout(id); };
  }, [text, view, meta.lang, meta.theme, version, ws.tabs, ws.notes, ws.conditions]);
  useEffect(() => {
    const on = (e: MessageEvent) => { if (e.source === frame.current?.contentWindow && typeof e.data?.svDocScroll === "number") scrollY.current = e.data.svDocScroll; };
    window.addEventListener("message", on);
    return () => window.removeEventListener("message", on);
  }, []);

  const setMeta = (patch: Partial<ReportMeta>) => useApp.getState().commit((w) => { w.report = { ...metaOf(w, lang), ...patch }; return w; });
  const edit = (v: string) => { typing.current = true; setText(v); };
  const put = (s: string, wrap?: [string, string]) => { typing.current = true; insertAt(ed.current, s, setText, wrap); };
  const block = (s: string) => put(asBlock(ed.current, s));
  const linePrefix = (p: string) => {
    const el = ed.current; if (!el) return;
    const a = el.value.lastIndexOf("\n", (el.selectionStart ?? 0) - 1) + 1;
    el.setSelectionRange(a, a);
    put(p);
  };

  const make = async (format: "html" | "pdf" | "docx") => {
    commitText(text);
    const ext = { html: ".html", pdf: ".pdf", docx: ".docx" }[format];
    const st = useApp.getState();
    const first = st.runs.find((r) => r.format !== "derived");
    // the file is named after the report's title; an untouched default report keeps the replay page's name (RV8)
    const title = st.ws.report?.doc ? /^#\s+(.+)$/m.exec(text)?.[1]?.trim() || meta.title : meta.title;
    const base = title.replace(/[\\/:*?"<>|]+/g, "_").slice(0, 60);
    const name = base ? base + ext : format === "html" ? replayFileName(activeTab(st.ws).name, first?.name) : "report" + ext;
    const { body, prepared } = await docBody(format, "");
    if (prepared.problems.length && !await confirmAsk(t("rdProblems", { n: prepared.problems.length }),
      translate(lang, "rdProblemsAsk", { n: prepared.problems.length, list: prepared.problems.slice(0, 8).join("\n") }), t("rdMakeAnyway"))) return;
    const path = await pickPath({ mode: "save", title: t("saveReport"), exts: [ext], defaultName: name });
    if (!path) return;
    setBusy(format);
    try {
      const r = await runJob<{ path: string }>("report", { ...body, path }, translate(lang, "creatingReport"));
      if (r) st.toast({ kind: "info", text: translate(lang, "savedTo", { path: r.path }), ms: format === "html" ? 12000 : undefined,
        ...(format === "html" ? { action: { label: translate(lang, "replayOpen"), run: () => { api.openPage(r.path).catch(() => {}); } } } : {}) });
    } catch (e) {
      st.toast({ kind: "error", text: String((e as Error).message) });
    } finally { setBusy(null); }
  };
  const reset = async () => {
    if (!await confirmAsk(t("rdReset"), t("rdResetAsk"), t("rdResetOk"), true)) return;
    const fresh = defaultDocText({ ...ws, report: { ...meta, doc: undefined } }, lang);
    typing.current = false;
    setText(fresh);
    commitText(fresh);
  };

  // suggestions at the caret: inside [[ ]] the tabs and plots, inside {{ }} the statistics, signals and variables
  const suggestions = useMemo(() => {
    const before = text.slice(0, caret);
    const ref = before.lastIndexOf("[["), refEnd = before.lastIndexOf("]]");
    if (ref >= 0 && ref > refEnd && !before.slice(ref).includes("\n")) {
      const typed = before.slice(ref + 2);
      const all = [...SPECIALS, ...ws.tabs.flatMap((tb) => [tabRef(ws, tb), ...tb.plots.map((_p, i) => plotRef(ws, tb, i))])];
      return { start: ref + 2, close: !text.slice(caret).startsWith("]]"), list: (typed ? fuzzySort(all, (x) => x, typed) : all).slice(0, 8) };
    }
    const val = before.lastIndexOf("{{"), valEnd = before.lastIndexOf("}}");
    if (val >= 0 && val > valEnd) {
      const { start, word } = wordAt(text, caret);
      if (!word) return null;
      const vars = [...text.matchAll(/\{\{\s*([A-Za-z_][\w]*)\s*=(?!=)/g)].map((m) => m[1]);
      const sigs = runs.flatMap((r) => r.signals.map((s) => refFor(runs, s.id)));
      const all = [...FUNCS.map((f) => f + "("), ...vars, ...sigs];
      return { start, close: false, list: fuzzySort(all, (x) => x, word).slice(0, 8) };
    }
    return null;
  }, [text, caret, ws, runs]);
  const accept = (s: string) => {
    if (!suggestions) return;
    const el = ed.current; if (!el) return;
    el.setSelectionRange(suggestions.start, caret);
    put(s + (suggestions.close ? "]]" : ""));
  };

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && (e.key === "b" || e.key === "i")) {
      e.preventDefault(); put("", e.key === "b" ? ["**", "**"] : ["*", "*"]);
    } else if (e.key === "Tab" && suggestions?.list.length && !e.shiftKey) {
      e.preventDefault(); accept(suggestions.list[0]);
    }
  };
  const onDrop = (e: React.DragEvent<HTMLTextAreaElement>) => {
    const s = e.dataTransfer.getData("application/x-sv-report");
    if (!s) return;
    e.preventDefault();
    const el = ed.current; if (!el) return;
    el.focus();
    // where the drop is: the browser places the caret there on dragover in a textarea
    put(asBlock(el, s));
  };

  const lib = (label: string, insert: string, title?: string, isBlock = true) => (
    <button key={insert} className="rd-lib-item" title={title ?? insert} draggable
      onDragStart={(e) => { e.dataTransfer.setData("application/x-sv-report", insert); e.dataTransfer.setData("text/plain", insert); }}
      onClick={() => (isBlock ? block(insert) : put(insert))}>{label}</button>
  );
  const tool = (label: string, title: string, run: () => void, cls = "") => (
    <button className={`iconbtn rd-tool ${cls}`} title={title} aria-label={title} onMouseDown={(e) => e.preventDefault()} onClick={run}>{label}</button>
  );

  return (
    <div className="rd" role="region" aria-label={t("report")}>
      <div className="rd-head">
        <h2 className="rd-title"><Icon.Report aria-hidden="true" />{t("report")}</h2>
        <div className="seg" role="group">
          {(["write", "both", "show"] as View[]).map((v) => (
            <button key={v} className={view === v ? "on" : ""} aria-pressed={view === v} onClick={() => setView(v)}>{t(v === "write" ? "rdWrite" : v === "both" ? "rdBoth" : "rdShow")}</button>
          ))}
        </div>
        <label className="rd-sel"><span>{t("reportLang")}</span>
          <select value={meta.lang} onChange={(e) => setMeta({ lang: e.target.value as "en" | "he" })}>
            <option value="he">עברית</option><option value="en">English</option></select></label>
        <label className="rd-sel"><span>{t("theme")}</span>
          <select value={meta.theme} onChange={(e) => setMeta({ theme: e.target.value as "light" | "dark" })}>
            <option value="light">{t("light")}</option><option value="dark">{t("dark")}</option></select></label>
        <span className="spacer" />
        <span className="rd-status" role="status">
          {updating ? t("rdUpdating") : problems.length ? <span className="rd-problems" title={problems.join("\n")}>⚠ {t("rdProblems", { n: problems.length })}</span> : null}
        </span>
        <button className="btn primary replay-make" disabled={!!busy} onClick={() => make("html")}>{busy === "html" ? t("loading") : "HTML"}</button>
        <button className="btn outline rd-pdf" disabled={!!busy} onClick={() => make("pdf")}>{busy === "pdf" ? t("loading") : "PDF"}</button>
        <button className="btn outline rd-docx" disabled={!!busy} onClick={() => make("docx")}>{busy === "docx" ? t("loading") : "Word"}</button>
        <button className="iconbtn" title={t("rdReset")} aria-label={t("rdReset")} onClick={reset}><Icon.Reset /></button>
      </div>
      <div className={`rd-body rd-${view}`}>
        {view !== "show" && (
          <aside className="rd-lib" aria-label={t("rdLibrary")}>
            <p className="hint">{t("rdLibHint")}</p>
            <h3 className="eyebrow">{t("rdLibPlots")}</h3>
            {ws.tabs.map((tb, ti) => (
              <div key={tb.id} className="rd-lib-tab">
                {lib(tb.name || `${t("tab")} ${ti + 1}`, `[[${tabRef(ws, tb)}]]`)}
                {tb.plots.map((p, pi) => p.signals.length || p.objects?.length
                  ? lib(p.title || t("plotTitle", { n: pi + 1 }), `[[${plotRef(ws, tb, pi)}]]`) : null)}
              </div>
            ))}
            <ValueForm put={(s) => put(s)} />
            <h3 className="eyebrow">{t("rdLibParts")}</h3>
            <div className="rd-lib-tab">{SPECIALS.map((s) => lib(s, `[[${s}]]`))}</div>
            {(ws.conditions ?? []).length > 0 && <>
              <h3 className="eyebrow">{t("rdLibConds")}</h3>
              <div className="rd-lib-tab">{(ws.conditions ?? []).map((c) => lib(c.name, `{{ holds("${c.name}") }}`, undefined, false))}</div>
            </>}
          </aside>
        )}
        {view !== "show" && (
          <section className="rd-editor">
            <div className="rd-toolbar" role="toolbar" aria-label={t("rdLibrary")}>
              {tool("H", t("rdHeading"), () => linePrefix("## "))}
              {tool("B", t("rdBold"), () => put("", ["**", "**"]), "rd-b")}
              {tool("I", t("rdItalic"), () => put("", ["*", "*"]), "rd-i")}
              {tool("•", t("rdBullets"), () => linePrefix("- "))}
              {tool("1.", t("rdNumbers"), () => linePrefix("1. "))}
              {tool("▦", t("rdTable"), () => block("| | |\n|---|---|\n| | |"))}
              {tool("∑", t("rdMath"), () => put("x", ["$", "$"]))}
              {tool("!", t("rdCallout"), () => block("> [!NOTE]\n> "))}
              {tool("↧", t("rdPageBreak"), () => block("\\newpage"))}
              {tool("🔗", t("rdLink"), () => put("text", ["[", "](https://)"]))}
              <span className="spacer" />
              {tool(dir === "rtl" ? "⇤" : "⇥", t("rdDirection"), () => setDir(dir === "rtl" ? "ltr" : "rtl"))}
              {tool("?", t("rdHelp"), () => setHelp(!help), help ? "on" : "")}
            </div>
            {help && <pre className="rd-help" dir="auto">{t("rdHelpText")}</pre>}
            {suggestions && suggestions.list.length > 0 && (
              <div className="rd-suggest" role="listbox">
                {suggestions.list.map((s, i) => (
                  <button key={s} role="option" aria-selected={i === 0} className={i === 0 ? "on" : ""} onMouseDown={(e) => e.preventDefault()} onClick={() => accept(s)}>{s}</button>
                ))}
                <span className="hint">{t("rdSuggest", { s: suggestions.list[0] })}</span>
              </div>
            )}
            <textarea ref={ed} className="rd-text" dir={dir} spellCheck={false} value={text} placeholder={t("rdPlaceholder")}
              aria-label={t("report")}
              onChange={(e) => { edit(e.target.value); setCaret(e.target.selectionStart ?? 0); }}
              onSelect={(e) => setCaret((e.target as HTMLTextAreaElement).selectionStart ?? 0)}
              onKeyDown={onKey} onDrop={onDrop}
              onBlur={() => { typing.current = false; commitText(text); }} />
          </section>
        )}
        {view !== "write" && (
          <section className="rd-preview">
            {html ? <iframe ref={frame} title={t("reportPreview")} sandbox="allow-scripts" className="rd-frame"
              srcDoc={html.replace("</body>", SCROLL_JS + "</body>")}
              onLoad={() => frame.current?.contentWindow?.postMessage({ svDocScrollTo: scrollY.current }, "*")} />
              : <p className="empty-state">{t("rdUpdating")}</p>}
          </section>
        )}
      </div>
    </div>
  );
}

/** The value form: a signal, a statistic, where (all / between the cursors / what a plot shows - frozen to
 *  numbers: a report must not move with the cursors) and a condition -> {{ max(Roll, 10, 60, when="Auto") }}. */
function ValueForm({ put }: { put: (s: string) => void }) {
  const t = useT();
  const runs = useApp((s) => s.runs);
  const conds = useApp((s) => s.ws.conditions) ?? [];
  const [sig, setSig] = useState("");
  const [stat, setStat] = useState<string>("max");
  const [where, setWhere] = useState<"all" | "cursors" | "shown">("all");
  const [when, setWhen] = useState("");
  const names = useMemo(() => {
    const all = runs.flatMap((r) => r.signals.map((s) => refFor(runs, s.id)));
    return (sig ? fuzzySort(all, (x) => x, sig) : all).slice(0, 200);
  }, [runs, sig]);
  const go = () => {
    const st = useApp.getState();
    if (!sig.trim()) { st.toast({ kind: "error", text: t("rdValueNoSignal") }); return; }
    let win = "";
    if (where === "cursors") {
      const c = st.cursor;
      if (!(c.on && c.dual && c.t1 !== null && c.t2 !== null)) { st.toast({ kind: "error", text: t("rdValueNoCursors") }); return; }
      win = `, ${+Math.min(c.t1, c.t2).toFixed(3)}, ${+Math.max(c.t1, c.t2).toFixed(3)}`;
    } else if (where === "shown") {
      const tab = activeTab(st.ws), p = tab?.plots[tab.active ?? 0];
      const r = p ? st.ranges[rangeKey(tab, p)] : null;
      if (r) win = `, ${+r[0].toFixed(3)}, ${+r[1].toFixed(3)}`;
    }
    put(`{{ ${stat}(${sig.trim()}${win}${when ? `, when="${when}"` : ""}) }}`);
  };
  return (
    <div className="rd-value">
      <h3 className="eyebrow">{t("rdValue")}</h3>
      <label className="afield"><span>{t("rdValueSignal")}</span>
        <input list="rd-sigs" value={sig} onChange={(e) => setSig(e.target.value)} className="rd-value-sig" /></label>
      <datalist id="rd-sigs">{names.map((n) => <option key={n} value={n} />)}</datalist>
      <div className="arow">
        <label className="afield"><span>{t("rdValueStat")}</span>
          <select value={stat} onChange={(e) => setStat(e.target.value)} className="rd-value-stat">{DOC_STATS.map((s) => <option key={s}>{s}</option>)}</select></label>
        <label className="afield"><span>{t("rdValueWindow")}</span>
          <select value={where} onChange={(e) => setWhere(e.target.value as typeof where)}>
            <option value="all">{t("rdWinAll")}</option><option value="cursors">{t("rdWinCursors")}</option><option value="shown">{t("rdWinShown")}</option></select></label>
      </div>
      {conds.length > 0 && (
        <label className="afield"><span>{t("rdValueWhen")}</span>
          <select value={when} onChange={(e) => setWhen(e.target.value)}><option value="">{t("rdValueAlways")}</option>
            {conds.map((c) => <option key={c.id}>{c.name}</option>)}</select></label>
      )}
      <button className="btn outline rd-value-insert" onClick={go}>{t("rdValueInsert")}</button>
    </div>
  );
}
