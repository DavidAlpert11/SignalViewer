/* RE1 (owner, 2026-11-18): the report as a document - written like Markdown, with the session's plots, tabs and
   values in it, a live preview beside it, and the same page / PDF / Word out of it. It replaces the Report side
   panel (one way to make a report): an old session's report opens as the document its form made (reportDoc.ts).
   The rail's Report button (and Ctrl+K) shows it in place of the plots; the same button goes back. */
import { useEffect, useMemo, useRef, useState } from "react";
import { activeTab, pickPath, rangeKey, useApp, type ReportMeta } from "../store";
import { translate, useT } from "../i18n";
import { api, type TexStatus } from "../api";
import { runJob } from "../files";
import { replayFileName } from "../replay";
import { Icon } from "../icons";
import { confirmAsk, openMenu } from "./Overlays";
import { clearReport } from "../clearing";
import { refFor, wordAt } from "../formulaRefs";
import { fuzzySort } from "../fuzzy";
import { duplicateLines, indentLines, moveLines, newHistory, record, redo, toggleComment, undo, type History, type Snap } from "../editText";
import { DOC_STATS, PARTS, SPECIALS, defaultDocText, docBody, docText, isLatexDoc, metaOf, plotRef, tabRef } from "../reportDoc";
import ReportParts from "./ReportParts";
import { MAX_ALL, MAX_ONE, assetBytes, assetId, htmlToMarkdown, pictureAsset, tsvToMarkdown } from "../reportPaste";
import { readyInsert } from "../reportReady";
import DemoGuide from "./DemoGuide";

type View = "write" | "both" | "show";
type Format = "html" | "pdf" | "docx" | "tex" | "texpdf";

/** RE3: the callouts' words in the report's language (the LaTeX conversion writes them as the page does) */
const calloutWords = (lang: "en" | "he") => ({ calloutNOTE: translate(lang, "rdNote"), calloutTIP: translate(lang, "rdTip"),
  calloutWARNING: translate(lang, "rdWarning"), calloutIMPORTANT: translate(lang, "rdImportant"), calloutFINDING: translate(lang, "rdFinding") });

/** RE3: a Markdown report (or a piece of one) as LaTeX - its [[...]] / {{...}} kept as written (masked while the
 *  server converts it: app/reportlatex.py to_latex). `body`: only what goes between \begin{document} and \end. */
export async function markdownToLatex(md: string, lang: "en" | "he", title: string, body = false): Promise<string> {
  const refs: string[] = [];
  const masked = md.replace(/\[\[[^\]\n]+\]\]|\{\{[\s\S]+?\}\}/g, (w) => { refs.push(w); return `\u27e6${refs.length - 1}\u27e7`; });
  const r = await api.reportToLatex(masked, lang, calloutWords(lang), title);
  let out = r.text.replace(/\u27e6(\d+)\u27e7/g, (_w, k: string) => refs[+k] ?? "");
  if (body) out = out.slice(out.indexOf("\\begin{document}") + "\\begin{document}".length, out.lastIndexOf("\\end{document}")).trim();
  return out;
}
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
  const [text, setTextRaw] = useState(stored);
  // RE4: the editor's own undo - a step per pause in typing or per piece put in, with the caret (editText.ts)
  const hist = useRef<History>(newHistory());
  const textRef = useRef(text);
  textRef.current = text;
  const selRef = useRef({ a: 0, b: 0 });
  const setText = (v: string, kind: "type" | "delete" | "put" = "put") => {
    if (v === textRef.current) return;
    const el = ed.current;
    const s = kind === "put" && el ? { a: el.selectionStart ?? 0, b: el.selectionEnd ?? 0 } : selRef.current;
    hist.current = record(hist.current, { text: textRef.current, ...s }, kind);
    textRef.current = v;
    setTextRaw(v);
  };
  /** a state of the text and its selection, put in the editor (undo, redo, the line keys) */
  const show = (s: Snap, fromHistory = false) => {
    if (!fromHistory) setText(s.text); else { textRef.current = s.text; setTextRaw(s.text); }
    typing.current = true;
    selRef.current = { a: s.a, b: s.b };
    requestAnimationFrame(() => { const el = ed.current; if (el) { el.focus(); el.setSelectionRange(s.a, s.b); } });
  };
  const [view, setView] = useState<View>(() => { try { return (localStorage.getItem("sv.rdView") as View) || "both"; } catch { return "both"; } });
  const [dir, setDir] = useState<"rtl" | "ltr">(meta.lang === "he" ? "rtl" : "ltr");
  const [html, setHtml] = useState<string | null>(null);
  const [pdf, setPdf] = useState<string | null>(null);           // RE3: a LaTeX report's preview PDF (its token)
  const [texErr, setTexErr] = useState<{ msg: string; line: number | null } | null>(null);
  const [tex, setTex] = useState<TexStatus | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const [updating, setUpdating] = useState(false);
  const [caret, setCaret] = useState(0);
  const [help, setHelp] = useState(false);
  const ed = useRef<HTMLTextAreaElement>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const scrollY = useRef(0);
  const typing = useRef(false);
  const latex = isLatexDoc(text);
  useEffect(() => { api.reportTexStatus().then(setTex).catch(() => {}); }, []);

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
        if (r.tex) {                                // RE3: typeset by this computer's LaTeX - the last good PDF stays
          if (r.pdf) setPdf(r.pdf);
          setTexErr(r.error ? { msg: r.error, line: r.line ?? null } : null);
        } else {
          setPdf(null); setTexErr(null);
          setHtml(r.html ?? "");
          useApp.setState({ reportPreviewHtml: r.html ?? "" });
        }
      } catch (e) {
        if (!gone) setProblems([String((e as Error).message)]);
      } finally { if (!gone) setUpdating(false); }
    }, isLatexDoc(text) ? 1500 : 500);
    return () => { gone = true; clearTimeout(id); };
  }, [text, view, meta.lang, meta.theme, version, ws.tabs, ws.notes, ws.conditions]);
  useEffect(() => {
    const on = (e: MessageEvent) => { if (e.source === frame.current?.contentWindow && typeof e.data?.svDocScroll === "number") scrollY.current = e.data.svDocScroll; };
    window.addEventListener("message", on);
    return () => window.removeEventListener("message", on);
  }, []);

  const setMeta = (patch: Partial<ReportMeta>) => useApp.getState().commit((w) => { w.report = { ...metaOf(w, lang), ...patch }; return w; });
  const edit = (v: string) => {
    typing.current = true;
    const d = v.length - textRef.current.length;
    setText(v, d === 1 ? "type" : d === -1 ? "delete" : "put");          // a paste, a cut, a selection replaced: a step of its own
  };
  const put = (s: string, wrap?: [string, string]) => { typing.current = true; insertAt(ed.current, s, setText, wrap); };
  const block = (s: string) => put(asBlock(ed.current, s));
  const linePrefix = (p: string) => {
    const el = ed.current; if (!el) return;
    const a = el.value.lastIndexOf("\n", (el.selectionStart ?? 0) - 1) + 1;
    el.setSelectionRange(a, a);
    put(p);
  };

  // RE2: a ready report replaces a report nobody wrote yet, else goes in at the caret (without its title)
  const ready = (doc: string) => {
    if (latex) {                                     // RE3: a ready report into a LaTeX report - as LaTeX
      void markdownToLatex(doc, meta.lang, "", true).then((x) => block(x)).catch((e) => useApp.getState().toast({ kind: "error", text: String((e as Error).message) }));
      return;
    }
    const untouched = !ws.report?.doc || text.trim() === defaultDocText({ ...ws, report: { ...meta, doc: undefined } }, lang).trim() || !text.trim();
    const r = readyInsert(doc, untouched);
    if (r.replace) { typing.current = false; setText(r.text); commitText(r.text); }
    else block(r.text.trim());
  };
  // RE2: a picture kept in the session (downscaled), written ![name](asset:<id>) where the cursor is
  const addPictures = async (files: File[]) => {
    const st = useApp.getState();
    for (const f of files.filter((x) => x.type.startsWith("image/"))) {
      try {
        const a = await pictureAsset(f, f.name || "picture");
        if (assetBytes(a) > MAX_ONE) { st.toast({ kind: "error", text: t("rpPictureBig", { name: a.name, mb: (assetBytes(a) / 1048576).toFixed(1) }) }); continue; }
        const all = useApp.getState().ws.report?.assets ?? {};
        const total = Object.values(all).reduce((n, x) => n + assetBytes(x), 0) + assetBytes(a);
        if (total > MAX_ALL) { st.toast({ kind: "error", text: t("rpPicturesFull", { mb: (MAX_ALL / 1048576).toFixed(0) }) }); return; }
        const id = await assetId(a.data);
        commitText(ed.current?.value ?? text);
        useApp.getState().commit((w) => { const m = metaOf(w, lang); w.report = { ...m, assets: { ...(m.assets ?? {}), [id]: a } }; return w; });
        block(isLatexDoc(ed.current?.value ?? text) ? `\\includegraphics[width=\\linewidth]{asset:${id}}` : `![${a.name.replace(/[[\]()]/g, " ")}](asset:${id})`);
      } catch (e) {
        st.toast({ kind: "error", text: t("rpPictureBad", { name: f.name, msg: String((e as Error).message) }) });
      }
    }
  };
  const plainPaste = useRef(false);
  const onPaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    if (plainPaste.current) { plainPaste.current = false; return; }      // Ctrl+Shift+V: as plain text
    const files = Array.from(e.clipboardData.files ?? []).filter((f) => f.type.startsWith("image/"));
    const html = e.clipboardData.getData("text/html"), plain = e.clipboardData.getData("text/plain");
    if (files.length && !plain.trim()) { e.preventDefault(); void addPictures(files); return; }
    const tsv = tsvToMarkdown(plain);
    const md = html ? htmlToMarkdown(html) : null;
    // a spreadsheet's cells: its tab-separated text has the exact numbers (its HTML has its formatting)
    const piece = tsv && (!md || /<table/i.test(html)) ? tsv : md?.text;
    if (!piece) return;
    e.preventDefault();
    if (md?.merged && piece === md.text) useApp.getState().toast({ kind: "info", text: t("rpPasteMerged") });
    put(asBlock(ed.current, piece));
  };
  const pictureInput = useRef<HTMLInputElement>(null);

  const make = async (format: Format) => {
    commitText(text);
    const ext = { html: ".html", pdf: ".pdf", docx: ".docx", tex: ".zip", texpdf: ".pdf" }[format];
    const st = useApp.getState();
    const first = st.runs.find((r) => r.format !== "derived");
    // the file is named after the report's title; an untouched default report keeps the replay page's name (RV8)
    const title = st.ws.report?.doc ? (latex ? /\\title\{([^}]*)\}/.exec(text)?.[1]?.trim() : /^#\s+(.+)$/m.exec(text)?.[1]?.trim()) || meta.title : meta.title;
    const base = title.replace(/[\\/:*?"<>|]+/g, "_").slice(0, 60);
    const name = base ? base + ext : format === "html" ? replayFileName(activeTab(st.ws).name, first?.name) : (format === "tex" ? "report-latex" : "report") + ext;
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

  // RE3: written in Markdown or in LaTeX - the text says which (its first line \documentclass); switching converts
  const setFormat = async (f: "md" | "tex") => {
    if ((f === "tex") === latex) return;
    if (f === "tex") {
      try {
        const out = await markdownToLatex(text, meta.lang, /^#\s+(.+)$/m.exec(text)?.[1]?.trim() || meta.title);
        typing.current = false; setText(out); commitText(out);
        useApp.getState().toast({ kind: "info", text: t("rdToTexDone"), ms: 9000 });
      } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
      return;
    }
    if (!await confirmAsk(t("rdToMd"), t("rdToMdAsk"), t("rdToMdOk"), true)) return;
    const fresh = defaultDocText({ ...ws, report: { ...meta, doc: undefined } }, lang);
    typing.current = false; setText(fresh); commitText(fresh);
  };
  const goLine = (n: number) => {
    const el = ed.current; if (!el) return;
    const lines = el.value.split("\n");
    const a = lines.slice(0, n - 1).join("\n").length + (n > 1 ? 1 : 0);
    el.focus(); el.setSelectionRange(a, a + (lines[n - 1]?.length ?? 0));
    el.scrollTop = Math.max(0, (n - 5) * 18);
  };

  // suggestions at the caret: inside [[ ]] the tabs and plots, inside {{ }} the statistics, signals and variables
  const suggestions = useMemo(() => {
    const before = text.slice(0, caret);
    const ref = before.lastIndexOf("[["), refEnd = before.lastIndexOf("]]");
    if (ref >= 0 && ref > refEnd && !before.slice(ref).includes("\n")) {
      const typed = before.slice(ref + 2);
      const all = [...SPECIALS, ...PARTS, ...ws.tabs.flatMap((tb) => [tabRef(ws, tb), ...tb.plots.map((_p, i) => plotRef(ws, tb, i))])];
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
    const el = e.currentTarget, a = el.selectionStart ?? 0, b = el.selectionEnd ?? a;
    selRef.current = { a, b };
    const mod = e.ctrlKey || e.metaKey, k = e.key.toLowerCase();
    const cur = { text: el.value, a, b };
    if (mod && !e.altKey && (k === "z" || k === "y")) {                // RE4: the editor's undo, not the browser's letter by letter
      e.preventDefault();
      const r = k === "z" && !e.shiftKey ? undo(hist.current, cur) : redo(hist.current, cur);
      if (r) { hist.current = r[0]; show(r[1], true); }
      return;
    }
    if (mod && !e.shiftKey && !e.altKey && (e.key === "/" || e.code === "Slash")) { e.preventDefault(); show(toggleComment(el.value, a, b, latex)); return; }
    if (mod && e.shiftKey && !e.altKey && k === "d") { e.preventDefault(); show(duplicateLines(el.value, a, b)); return; }
    if (e.altKey && !mod && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
      e.preventDefault();
      const r = moveLines(el.value, a, b, e.key === "ArrowDown");
      if (r) show(r);
      return;
    }
    if (e.key === "Tab" && !mod && !e.altKey && (e.shiftKey || (a !== b && el.value.slice(a, b).includes("\n")))) {
      e.preventDefault(); show(indentLines(el.value, a, b, e.shiftKey)); return;
    }
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "v") plainPaste.current = true;
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && (e.key === "b" || e.key === "i")) {
      e.preventDefault(); put("", latex ? (e.key === "b" ? ["\\textbf{", "}"] : ["\\emph{", "}"]) : e.key === "b" ? ["**", "**"] : ["*", "*"]);
    } else if (e.key === "Tab" && suggestions?.list.length && !e.shiftKey) {
      e.preventDefault(); accept(suggestions.list[0]);
    }
  };
  const onDrop = (e: React.DragEvent<HTMLTextAreaElement>) => {
    const pics = Array.from(e.dataTransfer.files ?? []).filter((f) => f.type.startsWith("image/"));
    if (pics.length) { e.preventDefault(); e.stopPropagation(); void addPictures(pics); return; }
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
      <div className="rd-head page-head">
        <h2 className="rd-title page-title"><Icon.Report aria-hidden="true" />{t("report")}</h2>
        <div className="seg" role="group">
          {(["write", "both", "show"] as View[]).map((v) => (
            <button key={v} className={view === v ? "on" : ""} aria-pressed={view === v} onClick={() => setView(v)}>{t(v === "write" ? "rdWrite" : v === "both" ? "rdBoth" : "rdShow")}</button>
          ))}
        </div>
        <span className="spacer" />
        <span className="rd-status" role="status">
          {updating ? t("rdUpdating") : problems.length ? <span className="rd-problems" title={problems.join("\n")}>⚠ {t("rdProblems", { n: problems.length })}</span> : null}
        </span>
        {/* Phase 3 (a first user looked for PDF and took HTML for the export): the menu names the formats it holds */}
        {/* CC8 (owner, 2026-11-26: not overloaded): one primary export - the page (Markdown) or the PDF (LaTeX) - and every
            format in Export ▾; the report's options (its language, Markdown / LaTeX, its theme, empty / automatic) in ⚙ */}
        {!latex ? <button className="btn primary replay-make" disabled={!!busy} onClick={() => make("html")}>{busy === "html" ? t("loading") : t("rdSaveHtml")}</button>
          : <button className="btn primary rd-texpdf" disabled={!!busy || !tex?.best} title={tex?.best === "tectonic" ? t("rdTexPdfBuiltin") : tex?.best ? t("rdTexPdfHint", { e: tex.best }) : tex?.hint ?? ""}
            onClick={() => make("texpdf")}>{busy === "texpdf" ? t("loading") : t("rdTexPdf")}</button>}
        <button className="btn outline rd-export" disabled={!!busy} aria-haspopup="menu" title={t("rdExportHint")}
          onClick={(e) => openMenu(e, [
            ...(!latex ? [
              { label: "HTML", run: () => make("html") },
              { label: "PDF", run: () => make("pdf") },
              { label: "Word", run: () => make("docx") },
              { label: "", sep: true, run: () => {} },
            ] : []),
            { label: t("rdTexPdf"), disabled: !tex?.best, run: () => make("texpdf") },
            { label: t("rdTexZip"), run: () => make("tex") },
          ])}>{busy ? t("loading") : latex ? t("rdExport") : t("rdExportFormats")} <Icon.Chevron width={12} height={12} /></button>
        <button className="iconbtn rd-options" title={t("rdOptions")} aria-label={t("rdOptions")} aria-haspopup="menu"
          onClick={(e) => openMenu(e, [
            { label: t("reportLang"), run: () => {}, items: [
              { label: "עברית", checked: meta.lang === "he", run: () => setMeta({ lang: "he" }) },
              { label: "English", checked: meta.lang === "en", run: () => setMeta({ lang: "en" }) }] },
            { label: t("rdFormat"), run: () => {}, items: [
              { label: "Markdown", checked: !latex, run: () => { void setFormat("md"); } },
              { label: "LaTeX", checked: latex, run: () => { void setFormat("tex"); } }] },
            { label: t("theme"), run: () => {}, items: [
              { label: t("light"), checked: meta.theme === "light", run: () => setMeta({ theme: "light" }) },
              { label: t("dark"), checked: meta.theme === "dark", run: () => setMeta({ theme: "dark" }) }] },
            { label: "", sep: true, run: () => {} },
            { label: t("rdEmpty"), run: () => { commitText(text); typing.current = false; void clearReport(); } },
            { label: t("rdReset"), run: () => { void reset(); } },
          ])}><Icon.Settings /></button>
      </div>
      <DemoGuide />
      <div className={`rd-body rd-${view}`}>
        {view !== "show" && (
          <aside className="rd-lib" aria-label={t("rdLibrary")}>
            <p className="hint">{t("rdLibHint")}</p>
            <ReportParts block={block} ready={ready} text={text}
              selected={() => { const el = ed.current; return el ? el.value.slice(el.selectionStart ?? 0, el.selectionEnd ?? 0) : ""; }} />
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
              {latex ? <>
                {tool("H", t("rdHeading"), () => put(t("rdHeading"), ["\\section{", "}"]))}
                {tool("B", t("rdBold"), () => put("", ["\\textbf{", "}"]), "rd-b")}
                {tool("I", t("rdItalic"), () => put("", ["\\emph{", "}"]), "rd-i")}
                {tool("•", t("rdBullets"), () => block("\\begin{itemize}\n  \\item \n\\end{itemize}"))}
                {tool("1.", t("rdNumbers"), () => block("\\begin{enumerate}\n  \\item \n\\end{enumerate}"))}
                {tool("▦", t("rdTable"), () => block("\\begin{tabular}{ll}\n\\toprule\n a & b \\\\\n\\midrule\n 1 & 2 \\\\\n\\bottomrule\n\\end{tabular}"))}
                {tool("∑", t("rdMath"), () => put("x", ["$", "$"]))}
                {tool("≡", t("rdEquation"), () => block("\\begin{align}\n  y &= x\n\\end{align}"))}
                {tool("↧", t("rdPageBreak"), () => block("\\newpage"))}
                {tool("🔗", t("rdLink"), () => put("text", ["\\href{https://}{", "}"]))}
              </> : <>
                {tool("H", t("rdHeading"), () => linePrefix("## "))}
                {tool("B", t("rdBold"), () => put("", ["**", "**"]), "rd-b")}
                {tool("I", t("rdItalic"), () => put("", ["*", "*"]), "rd-i")}
                {tool("•", t("rdBullets"), () => linePrefix("- "))}
                {tool("1.", t("rdNumbers"), () => linePrefix("1. "))}
                {tool("▦", t("rdTable"), () => block("| | |\n|---|---|\n| | |"))}
                {tool("∑", t("rdMath"), () => put("x", ["$", "$"]))}
                {tool("TeX", t("rdTexBlock"), () => block("```latex\n\\begin{align}\n  y &= x\n\\end{align}\n```"), "rd-texblock")}
                {tool("!", t("rdCallout"), () => block("> [!NOTE]\n> "))}
                {tool("↧", t("rdPageBreak"), () => block("\\newpage"))}
                {tool("🔗", t("rdLink"), () => put("text", ["[", "](https://)"]))}
              </>}
              {tool("🖼", t("rpPicture"), () => pictureInput.current?.click(), "rd-picture")}
              {tool(latex ? "%" : "<!>", t("rdComment"), () => { const el = ed.current; if (el) show(toggleComment(el.value, el.selectionStart ?? 0, el.selectionEnd ?? 0, latex)); }, "rd-comment")}
              {tool("↶", t("rdUndo"), () => { const el = ed.current; if (!el) return; const r = undo(hist.current, { text: el.value, a: el.selectionStart ?? 0, b: el.selectionEnd ?? 0 }); if (r) { hist.current = r[0]; show(r[1], true); } }, "rd-undo")}
              {tool("↷", t("rdRedo"), () => { const el = ed.current; if (!el) return; const r = redo(hist.current, { text: el.value, a: el.selectionStart ?? 0, b: el.selectionEnd ?? 0 }); if (r) { hist.current = r[0]; show(r[1], true); } }, "rd-redo")}
              <input ref={pictureInput} type="file" accept="image/png,image/jpeg,image/gif,image/webp" multiple hidden
                onChange={(e) => { void addPictures(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
              <span className="spacer" />
              {tool(dir === "rtl" ? "⇤" : "⇥", t("rdDirection"), () => setDir(dir === "rtl" ? "ltr" : "rtl"))}
              {tool("?", t("rdHelp"), () => setHelp(!help), help ? "on" : "")}
            </div>
            {help && <pre className="rd-help" dir="auto">{t(latex ? "rdHelpTextTex" : "rdHelpText")}</pre>}
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
              onSelect={(e) => { const el = e.target as HTMLTextAreaElement; setCaret(el.selectionStart ?? 0); selRef.current = { a: el.selectionStart ?? 0, b: el.selectionEnd ?? 0 }; }}
              onKeyDown={onKey} onDrop={onDrop} onPaste={onPaste}
              onBlur={() => { typing.current = false; commitText(text); }} />
          </section>
        )}
        {view !== "write" && latex && (
          <section className="rd-preview rd-preview-tex">
            {!tex?.best && tex && <p className="rd-tex-none hint">{tex.hint}</p>}
            {texErr && <p className="rd-tex-err" role="alert">⚠ {texErr.line ? <button className="linklike" onClick={() => goLine(texErr.line!)}>{texErr.msg}</button> : texErr.msg}</p>}
            {pdf ? <>
              <iframe key={pdf} title={t("reportPreview")} className="rd-frame rd-pdf-frame" src={`/api/report/tex/pdf/${pdf}#navpanes=0&view=FitH`} />
              <button className="linklike rd-tex-open" onClick={() => { api.reportTexOpen(pdf).catch(() => {}); }}>{t("rdTexOpen")}</button>
            </> : tex?.best && !texErr ? <p className="empty-state">{t("rdTexWorking")}</p> : null}
          </section>
        )}
        {view !== "write" && !latex && (
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
