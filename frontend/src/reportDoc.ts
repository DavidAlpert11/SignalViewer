/* RE1 (owner, 2026-11-18): the report as a document the user writes - Markdown, with the session's plots, tabs
   and values in it:
     [[Attitude.Roll]]          a plot (tab name or tab2, then plot title or plot1); [[Attitude]] the whole tab
     [[Roll | 10..60, no table]] options after |: a time window, "no table", "table only"
     [[notes]] [[findings]] [[investigation]] [[process]] [[verdict]]
     {{ max(Roll) }}  {{ rms(Roll - RollDes, when="Auto") :.2f }}  {{ peak = max(Roll) }} then {{ peak * 2 }}
   Signals are written by name, as in formulas (formulaRefs.ts) - so the text reads well and the same report
   works on the next recording; they are resolved here to stable ids "<runId>/<name>" for the server, which
   computes every value on all the data (backend/svcore/docfields.py) and draws the page / PDF / Word
   (backend/app/reportdoc.py). What cannot be found is said in place, never left out without a word. */
import { activeTab, signalName, TRACE_COLORS, useApp, type ReportMeta, type Tab, type Workspace } from "./store";
import { translate, type TKey } from "./i18n";
import { pagePlot, pagePlots, plotSpec } from "./plotSpec";
import { resolveFormula } from "./formulaRefs";
import { processSection } from "./reportProcess";
import { investigationSections } from "./investigation";
import { replayInfo } from "./replay";
import { usedAssets } from "./reportPaste";
import { effectiveBase } from "./mapBase";

type Lang = "en" | "he";
export const REPORT_DEFAULT: ReportMeta = { title: "", intro: "", summary: "", lang: "he", theme: "light", scope: "tab" };
/** the statistics a value can take, and the other functions of a value (svcore/docfields.py) */
export const DOC_STATS = ["max", "min", "mean", "rms", "std", "range", "first", "final", "samples", "duration", "tmax", "tmin", "absmax", "integral"] as const;
const DOC_FUNCS = [...DOC_STATS, "stretches", "holds", "abs", "sqrt", "round", "floor", "ceil", "log10", "log", "exp"];
export const SPECIALS = ["notes", "findings", "investigation", "process", "verdict"] as const;
/** RE2: the ready-made parts - each finds what it needs in the open files by the signals' names and writes its
 *  sentence, tables and plots on the server (backend/app/reportparts.py). `[[tracking]]`, `[[tracking roll | tol 2]]`. */
export const PARTS = ["toc", "overview", "tracking", "navigation", "states", "trajectory", "moments", "differences", "messages", "summary"] as const;
export type PartName = typeof PARTS[number];
const MARK = (n: number) => `\u27e6${n}\u27e7`;

export const metaOf = (ws: Workspace, lang: Lang): ReportMeta => ({ ...REPORT_DEFAULT, lang, ...(ws.report ?? {}) });

/** How a tab is written in a reference: its name when it is unique and simple, else tab<n>. */
export function tabRef(ws: Workspace, tab: Tab): string {
  const i = ws.tabs.indexOf(tab);
  const n = (tab.name ?? "").trim();
  const same = ws.tabs.filter((t) => (t.name ?? "").trim().toLowerCase() === n.toLowerCase()).length;
  const reserved = [...SPECIALS, ...PARTS, "plot"] as readonly string[];
  return n && same === 1 && !/[[\]|.]/.test(n) && !reserved.includes(n.toLowerCase().split(/\s+/)[0]) && !/^tab\s*\d+$/i.test(n) ? n : `tab${i + 1}`;
}

/** [[tab.plot]] for a plot: its title when it is unique in its tab, else plot<n>. */
export function plotRef(ws: Workspace, tab: Tab, pi: number): string {
  const p = tab.plots[pi];
  const n = (p?.title ?? "").trim();
  const same = tab.plots.filter((x) => (x.title ?? "").trim().toLowerCase() === n.toLowerCase()).length;
  const name = n && same === 1 && !/[[\]|]/.test(n) && !/^plot\s*\d+$/i.test(n) ? n : `plot${pi + 1}`;
  return `${tabRef(ws, tab)}.${name}`;
}

/** The document an old session's report becomes (the Report panel's form, 1.30 and earlier): the same parts in
 *  the same order - so a report made before RE1 opens as the same report, now editable as text. */
export function defaultDocText(ws: Workspace, lang: Lang): string {
  const meta = metaOf(ws, lang);
  const t = (k: TKey) => translate(meta.lang, k);
  const st = useApp.getState();
  const hasInvestigation = (ws.notes ?? []).some((n) => n.status) || (ws.conditions ?? []).length > 0 || st.journal.length > 0;
  const tabs = meta.scope === "all" ? ws.tabs : [activeTab(ws)].filter(Boolean) as Tab[];
  const out: string[] = [];
  out.push(`# ${meta.title.trim() || t("report")}`);
  if (meta.intro.trim()) out.push(meta.intro.trim());
  out.push("[[process]]");
  if (meta.verdict && meta.includeVerdict !== false) out.push("[[verdict]]");
  if (hasInvestigation && meta.investigation !== false) out.push("[[investigation]]");
  for (const tab of tabs) if (pagePlots(tab).some((x) => x.include && !x.p.excludeFromReport)) out.push(`[[${tabRef(ws, tab)}]]`);
  out.push(`## ${t("summary")}`);
  out.push(meta.summary.trim() || t("rdSummaryHint"));
  if ((ws.notes ?? []).some((n) => !n.status)) out.push("[[notes]]");
  return out.join("\n\n") + "\n";
}

/** The text of the session's report: what the user wrote, else the default made from the old form. */
export const docText = (ws: Workspace, lang: Lang) => ws.report?.doc?.text ?? defaultDocText(ws, lang);

/** Add a piece at the end of the report (a plot's "Add to report", Compare's verdict) - inside a commit. */
export function appendToDoc(ws: Workspace, lang: Lang, piece: string): Workspace {
  const text = docText(ws, lang).replace(/\s*$/, "");
  ws.report = { ...metaOf(ws, lang), doc: { v: 1, text: `${text}\n\n${piece}\n` } };
  return ws;
}

// ------------------------------------------------------------------------------------------------ resolve

export interface DocItem { kind: "value" | "plots" | "notes" | "sections" | "error" | "special" | "part"; [k: string]: unknown }
export interface Prepared { text: string; items: DocItem[]; problems: string[]; plots: number }

function findTab(ws: Workspace, name: string): Tab | undefined {
  const n = name.trim().toLowerCase();
  const m = /^tab\s*(\d+)$/.exec(n);
  return ws.tabs.find((t) => (t.name ?? "").trim().toLowerCase() === n) ?? (m ? ws.tabs[+m[1] - 1] : undefined);
}

function findPlot(tab: Tab, name: string, plotLabel: string): number {
  const n = name.trim().toLowerCase();
  const m = /^plot\s*(\d+)$/.exec(n);
  let i = tab.plots.findIndex((p) => (p.title ?? "").trim().toLowerCase() === n);
  if (i < 0 && m && +m[1] >= 1 && +m[1] <= tab.plots.length) i = +m[1] - 1;
  if (i < 0) i = tab.plots.findIndex((_p, k) => plotLabel.replace("{n}", String(k + 1)).toLowerCase() === n);   // "Plot 2" as shown
  return i;
}

/** [[...]] -> what to draw. Exported for the tests. */
export interface Special { kind: "special"; special: string; opts: string[] }
export function resolveRef(ws: Workspace, raw: string, lang: Lang): DocItem | Special {
  const t = (k: TKey, p?: Record<string, string | number>) => translate(lang, k, p);
  const [target, ...rest] = raw.split("|");
  const opts = rest.join("|").split(",").map((x) => x.trim().toLowerCase()).filter(Boolean);
  const name = target.trim();
  if ((SPECIALS as readonly string[]).includes(name.toLowerCase())) return { kind: "special", special: name.toLowerCase(), opts };
  const head = name.split(/\s+/)[0].toLowerCase();
  if ((PARTS as readonly string[]).includes(head) && !findTab(ws, name)) {
    // the options keep their case (a reference object's or a file's name)
    const raw2 = rest.join("|").split(",").map((x) => x.trim()).filter(Boolean);
    const st = useApp.getState();
    const runs = st.runs.filter((r) => r.format !== "derived").map((r) => r.id);
    // the map layer the app shows: a part's map is drawn on it (from the tiles kept), as a plot's map is
    return { kind: "part", part: head, arg: name.slice(head.length).trim(), opts: raw2, runs, src: raw,
      mapBase: effectiveBase(st.geoBase, st.offlineOnly || st.offlineForced),
      ...(head === "messages" && ws.messageStreams?.length ? { streams: ws.messageStreams } : {}) };
  }
  if (head === "plot" && name.length > 5 && !findTab(ws, name)) return plotRefItem(name.slice(5).trim(), opts, raw, lang);
  const plotLabel = translate(lang, "plotTitle", { n: "{n}" });
  let tab = findTab(ws, name), pi: number | null = null;
  if (!tab) {                                         // tab.plot: the first dot that splits into a tab and its plot
    for (let k = name.indexOf("."); k > 0; k = name.indexOf(".", k + 1)) {
      const tb = findTab(ws, name.slice(0, k));
      if (!tb) continue;
      const i = findPlot(tb, name.slice(k + 1), plotLabel);
      if (i >= 0) { tab = tb; pi = i; break; }
      return { kind: "error", error: t("rdNoPlot", { plot: name.slice(k + 1).trim(), tab: name.slice(0, k).trim() }), src: raw };
    }
  }
  if (!tab) return { kind: "error", error: t("rdNoTab", { name }), src: raw };
  let range: [number, number] | null | undefined;
  let table: "only" | "none" | undefined;
  for (const o of opts) {
    const m = /^(-?[\d.]+)\s*(?:\.\.|–|-|to)\s*(-?[\d.]+)\s*s?$/.exec(o);
    if (m && isFinite(+m[1]) && isFinite(+m[2]) && +m[2] > +m[1]) range = [+m[1], +m[2]];
    else if (o === "all") range = null;
    else if (o === "no table" || o === "notable") table = "none";
    else if (o === "table" || o === "table only") table = "only";
    else return { kind: "error", error: t("rdBadOption", { opt: o }), src: raw };
  }
  const chosen = pi === null ? pagePlots(tab).filter((x) => x.include && !x.p.excludeFromReport) : [{ p: tab.plots[pi], pi, ...pagePlot(tab.plots[pi]) }];
  if (pi !== null && !chosen[0].include) return { kind: "error", error: `${chosen[0].p.title || plotLabel.replace("{n}", String(pi + 1))}: ${t(chosen[0].why!)}`, src: raw };
  if (!chosen.length) return { kind: "error", error: t("rdEmptyTab", { name }), src: raw };
  const plots = chosen.map(({ p, pi: i }) => ({ ...plotSpec(tab!, p, i, plotLabel), ...(range !== undefined ? { range } : {}) }));
  return { kind: "plots", plots, ...(table ? { table } : {}), tab: tab.name || `${translate(lang, "tab")} ${ws.tabs.indexOf(tab) + 1}`, src: raw };
}

/** RE2: `[[plot Roll, RollDes | 10..60]]` - a plot made in the text from signal names, in no tab: what the
 *  ready-made parts write when expanded, and a quick plot without building a tab. A name in several open files is
 *  drawn from each (a comparison); `{file:name}` one file's; `plot xy Lon, Lat` an X-Y. */
function plotRefItem(body: string, opts: string[], raw: string, lang: Lang): DocItem {
  const t = (k: TKey, p?: Record<string, string | number>) => translate(lang, k, p);
  const runs = useApp.getState().runs.filter((r) => r.format !== "derived");
  let xy = false;
  if (/^xy\s/i.test(body)) { xy = true; body = body.slice(3).trim(); }
  const noUnit = (n: string) => n.replace(/ \[[^\]]*\]$/, "").toLowerCase();
  const ids: string[] = [];
  for (let name of body.split(",").map((x) => x.trim()).filter(Boolean)) {
    let pool = runs;
    const m = /^\{([^:}]+):([^}]+)\}$/.exec(name);
    if (m) { pool = runs.filter((r) => r.name === m[1].trim() || r.id === m[1].trim()); name = m[2].trim(); }
    else name = name.replace(/^\{|\}$/g, "");
    let hits = pool.flatMap((r) => r.signals.filter((s) => s.name === name).map((s) => s.id));
    if (!hits.length) hits = pool.flatMap((r) => r.signals.filter((s) => noUnit(s.name) === noUnit(name)).map((s) => s.id));
    if (!hits.length) return { kind: "error", error: t("rdNoSignal", { name }), src: raw };
    ids.push(...hits.filter((h) => !ids.includes(h)));
  }
  if (!ids.length || (xy && ids.length < 2)) return { kind: "error", error: t("rdPlotEmpty"), src: raw };
  let range: [number, number] | null = null;
  let table: "only" | "none" | undefined;
  for (const o of opts) {
    const w = /^(-?[\d.]+)\s*(?:\.\.|–|-|to)\s*(-?[\d.]+)\s*s?$/.exec(o), a = /^around\s+(-?[\d.]+)\s*s?$/.exec(o);
    if (w && +w[2] > +w[1]) range = [+w[1], +w[2]];
    else if (a) range = [+a[1] - 10, +a[1] + 10];
    else if (o === "no table" || o === "notable") table = "none";
    else if (o === "table" || o === "table only") table = "only";
    else if (o !== "all") return { kind: "error", error: t("rdBadOption", { opt: o }), src: raw };
  }
  const st = useApp.getState();
  const isState = (id: string) => !!st.runs.flatMap((r) => r.signals).find((s) => s.id === id)?.labels;
  const lines = (xy ? ids.slice(1) : ids).map((id, k) => ({ id, label: signalName(st.runs, id), color: TRACE_COLORS[k % TRACE_COLORS.length],
    width: 1.5, scale: 1, offset: 0, state: isState(id), tOffset: 0 }));
  const title = (xy ? ids.slice(1) : ids).map((id) => signalName(st.runs, id, false)).filter((v, i, a) => a.indexOf(v) === i).join(", ");
  const plot = { title, caption: "", mode: xy ? "xy" : "time", range, signals: lines,
    ...(xy ? { xSignal: ids[0], xLabel: signalName(st.runs, ids[0], false) } : {}) };
  return { kind: "plots", plots: [plot], ...(table ? { table } : {}), tab: "", src: raw };
}

const FMT = /\s:\s*([<>^=]?[+\- ]?#?0?\d*[,_]?(?:\.\d+)?[bcdeEfFgGnosxX%]?)\s*$/;

/** {{...}} -> a value for the server: the formula with v0, v1... and the signals' ids. Exported for the tests. */
export function resolveValue(ws: Workspace, raw: string, vars: string[], lang: Lang): DocItem & { assign?: string } {
  const t = (k: string, p?: Record<string, string | number>) => translate(lang, k as TKey, p);
  let body = raw.trim(), fmt = "", assign: string | undefined;
  const f = FMT.exec(body);
  if (f && f[1] && !/[{}]/.test(f[1])) { fmt = f[1]; body = body.slice(0, f.index).trim(); }
  const a = /^([A-Za-z_\u0590-\u05FF][\w\u0590-\u05FF]*)\s*=(?!=)\s*([\s\S]+)$/.exec(body);
  if (a) { assign = a[1]; body = a[2]; }
  // quoted names (a condition's) and when= are not signals: masked while the names are resolved
  const strings: string[] = [];
  const masked = body.replace(/"([^"]*)"|'([^']*)'/g, (_w, d: string | undefined, s: string | undefined) => {
    strings.push(d ?? s ?? ""); return `\uE000${strings.length - 1}\uE000`;
  }).replace(/\bwhen\s*=/g, "\uE001");
  const res = resolveFormula(masked, useApp.getState().runs, t, { funcs: DOC_FUNCS, names: vars, noSignalOk: true });
  const back = (s: string) => s.replace(/\uE001/g, "when=").replace(/\uE000(\d+)\uE000/g, (_w, k: string) => JSON.stringify(strings[+k]));
  const conds: Record<string, unknown> = {};
  for (const name of strings) {
    const c = (ws.conditions ?? []).find((x) => x.name === name);
    if (!c) continue;
    conds[name] = c.combine ? { error: t("rdCombined", { name }) } : { text: c.text, exit: c.exit ?? "", minDur: c.minDur ?? 0, mergeGap: c.mergeGap ?? 0 };
  }
  const names = Object.fromEntries(res.sources.map((id, k) => [`v${k}`, signalName(useApp.getState().runs, id, false)]));
  if (res.error) return { kind: "value", error: res.error, src: raw, ...(assign ? { assign } : {}) };
  return { kind: "value", expr: back(res.expr), sources: res.sources, conds, names, fmt, src: raw, ...(assign ? { assign } : {}) };
}

/** RE3: a report written in LaTeX - its first line that is not a comment is \documentclass (app/reportlatex.py). */
export const isLatexDoc = (text: string) => /^\s*(%[^\n]*\n\s*)*\\documentclass/.test(text);

/** Code (``` blocks and `spans`) is shown as written: no references in it. In LaTeX: verbatim, \verb and comments. */
function codeRanges(text: string): [number, number][] {
  const out: [number, number][] = [];
  const re = isLatexDoc(text)
    ? /\\begin\{(verbatim|lstlisting|minted)\*?\}[\s\S]*?\\end\{\1\*?\}|\\verb(.)[^\n]*?\2|(?<!\\)%[^\n]*/g
    : /^(```|~~~)[^\n]*\n[\s\S]*?(^\1[^\n]*$|$(?![\s\S]))|`[^`\n]+`/gm;
  for (let m = re.exec(text); m; m = re.exec(text)) out.push([m.index, m.index + m[0].length]);
  return out;
}

/** The text with every [[...]] / {{...}} replaced by a marker, and what each stands for. */
export async function prepareDoc(ws: Workspace, text: string, lang: Lang): Promise<Prepared> {
  const meta = metaOf(ws, lang);
  const items: DocItem[] = [];
  const problems: string[] = [];
  const vars: string[] = [];
  const code = codeRanges(text);
  const inCode = (i: number) => code.some(([a, b]) => i >= a && i < b);
  const specials: { k: number; name: string; opts: string[] }[] = [];
  const st = useApp.getState();
  // {{ the value }}: its opening pair is the last of a run of braces - in LaTeX \textbf{{{ max(Roll) }}} is bold
  const out = text.replace(/\[\[([^\]\n]+)\]\]|\{\{(?!\{)([\s\S]+?)\}\}/g, (whole, ref: string | undefined, value: string | undefined, at: number) => {
    if (inCode(at)) return whole;
    const k = items.length;
    if (ref !== undefined) {
      const r = resolveRef(ws, ref, meta.lang);
      if (r.kind === "special") { const sp = r as Special; specials.push({ k, name: sp.special, opts: sp.opts }); items.push({ kind: "error", error: "" }); }
      else items.push(r as DocItem);
    } else {
      const v = resolveValue(ws, value!, vars, meta.lang);
      if (v.assign) vars.push(v.assign);
      items.push(v);
    }
    if (items[k].error) problems.push(`${whole.slice(0, 60)}: ${items[k].error as string}`);
    return MARK(k);
  });
  // the generated parts, as the Report panel made them
  const tr = (key: TKey) => translate(meta.lang, key);
  // the process in brief names the tabs the report shows, each once
  const shown: { name: string; plots: { title?: string }[] }[] = [];
  for (const x of items.filter((i) => i.kind === "plots")) {
    const same = shown.find((s) => s.name === x.tab);
    if (same) same.plots.push(...(x.plots as { title?: string }[])); else shown.push({ name: x.tab as string, plots: [...(x.plots as { title?: string }[])] });
  }
  const hasInvestigation = (ws.notes ?? []).some((n) => n.status) || (ws.conditions ?? []).length > 0 || st.journal.length > 0;
  for (const { k, name } of specials) {
    if (name === "notes") items[k] = { kind: "notes", notes: (ws.notes ?? []).filter((n) => !n.status).map((n) => ({ t: n.t, ...(n.t2 !== undefined ? { t2: n.t2 } : {}), text: n.text })) };
    else if (name === "findings") items[k] = { kind: "notes", notes: (ws.notes ?? []).filter((n) => n.status && n.status !== "rejected")
      .map((n) => ({ t: n.t, ...(n.t2 !== undefined ? { t2: n.t2 } : {}), text: `${n.text} (${tr(`fs_${n.status}` as TKey)})` })) };
    else if (name === "process") items[k] = { kind: "sections", sections: [processSection(meta.lang, meta, shown, !!meta.verdict && meta.includeVerdict !== false, hasInvestigation)] };
    else if (name === "investigation") items[k] = { kind: "sections", sections: await investigationSections(meta.lang) };
    else if (name === "verdict") items[k] = meta.verdict ? { kind: "sections", sections: [{ title: meta.verdict.title, items: meta.verdict.summary, table: { head: meta.verdict.head, rows: meta.verdict.rows } }] }
      : { kind: "error", error: tr("rdNoVerdict") };
    if (items[k].error) problems.push(`[[${name}]]: ${items[k].error as string}`);
  }
  return { text: out, items, problems, plots: items.filter((x) => x.kind === "plots").reduce((n, x) => n + (x.plots as unknown[]).length, 0) };
}

/** The body the server takes (preview, the job of a file). */
export async function docBody(format: "html" | "pdf" | "docx" | "tex" | "texpdf", path: string, typed?: string) {
  const st = useApp.getState();
  const meta = metaOf(st.ws, st.lang);
  const text = typed ?? docText(st.ws, st.lang);     // the preview: the text being typed, before it is committed
  const p = await prepareDoc(st.ws, text, meta.lang);
  const tr = (k: TKey) => translate(meta.lang, k);
  const title = /^#\s+(.+)$/m.exec(text)?.[1]?.trim() || meta.title;
  return {
    body: { path, format, title, lang: meta.lang, theme: meta.theme, text: p.text, items: p.items,
      notes: (st.ws.notes ?? []).filter((n) => n.status !== "rejected").map((n) => ({ t: n.t, ...(n.t2 !== undefined ? { t2: n.t2 } : {}), text: n.text })),
      assets: usedAssets(text, meta.assets),
      words: { calloutNOTE: tr("rdNote"), calloutTIP: tr("rdTip"), calloutWARNING: tr("rdWarning"), calloutIMPORTANT: tr("rdImportant"), calloutFINDING: tr("rdFinding") },
      ...(format === "html" && p.plots ? { replay: replayInfo(meta.lang, false) } : {}) },
    prepared: p,
  };
}

/** A plot's / tab's "Add to report" (and Ctrl+K): its reference at the end of the report, said with a way to it. */
export function addToReport(tab: Tab, pi?: number) {
  const st = useApp.getState();
  const ref = `[[${pi === undefined ? tabRef(st.ws, tab) : plotRef(st.ws, tab, pi)}]]`;
  st.commit((w) => appendToDoc(w, st.lang, ref));
  st.toast({ kind: "info", text: translate(st.lang, "rdAdded", { ref }), action: { label: translate(st.lang, "report"), run: () => useApp.setState({ panel: "report" }) } });
}
