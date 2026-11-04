/* The chart desktop (MF02): 1, 2 or 4 panes, each a chart kind with its columns - points, bubble,
   histogram, box, scatter matrix (Pearson / Spearman), broken conditions. Every pane reads the same
   sets (the keep / exclude steps, hidden groups), colours them as the lines do (`colorBy`: a group,
   holds, a column) and filters with the ONE brush (`view.filters`): a range dragged on a histogram,
   a rectangle on the points, a bar of the broken conditions - the lines, the table and every other
   pane follow. */
import { useMemo, useRef, useState } from "react";
import { api } from "../../api";
import { pickPath } from "../../store";
import { Icon } from "../../icons";
import { openMenu } from "../Overlays";
import { notify, notifyError } from "../../sweeps/notify";
import { useT, type TFn, type TKey } from "../../i18n";
import { category, FAILS, FLAG_COLS, HOLDS } from "../../sweeps/colors";
import { hasFilter, keptMask } from "../../sweeps/filters";
import type { Col, DeskPane, Filter, PaneKind } from "../../sweeps/model";
import { fmtValue, labelOf } from "../../sweeps/scales";
import { boxStats, histogram, pearson, spearman } from "../../sweeps/stats";
import { useSweeps, type Study } from "../../sweeps/state";
import { axisChoices, colLabel, groupRows, mapSpec, scaleOf, scopedColumns, shownAxes } from "../../sweeps/view";
import { MapPanel } from "./MapView";
import ParallelPlot from "./ParallelPlot";
import { ShapePane } from "./ShapePane";
import { ScatterPanel } from "./ScatterView";

export const PANE_KINDS: PaneKind[] = ["lines", "scatter", "bubble", "histogram", "box", "matrix", "map", "history", "pareto", "compare", "broken", "pca", "som"];
const KIND_KEY: Record<PaneKind, TKey> = { lines: "swPaneLines", scatter: "swPaneScatter", bubble: "swPaneBubble", histogram: "swPaneHistogram", box: "swPaneBox",
  matrix: "swPaneMatrix", map: "swPaneMap", history: "swPaneHistory", pareto: "swPaneParetoKind", compare: "swPaneCompare", broken: "swPaneBroken", pca: "swPanePca", som: "swPaneSom" };
const AUTO_KEYS: Record<string, TKey> = { all: "swGrpAll", holds: "swGrpHolds", pareto: "swGrpPareto", fails: "swGrpFails", error: "swGrpError", marked: "swGrpMarked" };
const BINS = 20;

/** The charts on screen: the study's (every one, `perRow` in a row), or two from its columns. */
const isObjective = (name: string) => name === "#goal" || /^#obj\d+$/.test(name);

export function deskOf(s: Study): { layout: 1 | 2 | 4; panes: DeskPane[]; perRow: 1 | 2 | 4 } {
  const d = s.view.desk;
  const first = firstPanes(s);
  if (!d) return { layout: 2, perRow: 2, panes: first.slice(0, 2) };
  // an older desk: always four panes, `layout` of them on screen
  if (d.perRow === undefined) return { layout: d.layout, perRow: d.layout, panes: first.map((p, i) => d.panes[i] ?? p).slice(0, d.layout) };
  return { layout: d.layout, perRow: d.perRow, panes: d.panes };
}
/** the first charts of a study: points, a histogram, a box, a matrix - from its columns */
function firstPanes(s: Study): DeskPane[] {
  const ch = axisChoices(s);
  const params = s.answer?.sets.filter((c) => c.group === "param").map((c) => c.name).filter((c) => ch.includes(c)) ?? [];
  const goal = ch.includes("#goal") ? "#goal" : s.answer?.sets.find((c) => c.group === "output")?.name ?? ch[0] ?? "";
  const first: DeskPane[] = [
    { kind: "scatter", x: params[0] ?? ch[0] ?? "", y: goal },
    { kind: "histogram", x: goal },
    { kind: "box", x: goal },
    { kind: "matrix", columns: [...params.slice(0, 4), goal].filter(Boolean), corr: "pearson" },
  ];
  return first;
}
/** a new chart: the next of the first ones not on screen, or points */
function newPane(s: Study, have: DeskPane[]): DeskPane {
  const firsts = firstPanes(s);
  return firsts.find((p) => !have.some((h) => h.kind === p.kind)) ?? { ...firsts[0] };
}

/** A chart's drawing with the colours it has on screen baked in (a copy needs no stylesheet). */
function bakedSvg(g: SVGSVGElement): SVGSVGElement {
  const copy = g.cloneNode(true) as SVGSVGElement;
  const src = [g, ...g.querySelectorAll("*")], dst = [copy, ...copy.querySelectorAll("*")];
  src.forEach((e, i) => {
    const cs = getComputedStyle(e), d = dst[i] as SVGElement;
    for (const k of ["fill", "stroke", "stroke-width", "stroke-dasharray", "opacity", "font-size", "font-family", "font-weight", "text-anchor"]) d.style.setProperty(k, cs.getPropertyValue(k));
  });
  const r = g.getBoundingClientRect();
  copy.setAttribute("width", String(r.width)); copy.setAttribute("height", String(r.height));
  if (!copy.getAttribute("viewBox")) copy.setAttribute("viewBox", `0 0 ${r.width} ${r.height}`);
  copy.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  return copy;
}
/** the chart's drawing: its largest canvas or SVG */
function mainDrawing(el: HTMLElement): HTMLCanvasElement | SVGSVGElement | null {
  const area = (e: Element) => { const r = e.getBoundingClientRect(); return r.width * r.height; };
  const c = [...el.querySelectorAll("canvas")].sort((a, b) => area(b) - area(a))[0];
  const g = [...el.querySelectorAll("svg")].filter((x) => x.getBoundingClientRect().width > 60).sort((a, b) => area(b) - area(a))[0];
  return c && (!g || area(c) >= area(g)) ? c : g ?? null;
}
const pageBg = () => getComputedStyle(document.body).backgroundColor || "#fff";

/** A chart as a PNG - `scale` times its pixels on screen (2: for a report). A drawn chart (SVG) is
 *  drawn again at that size; a canvas is scaled up. */
async function paneImage(el: HTMLElement, scale = 1): Promise<string | null> {
  const d = mainDrawing(el);
  if (!d) return null;
  const r = d.getBoundingClientRect(), k = Math.max(1, scale) * (window.devicePixelRatio || 1);
  const cv = document.createElement("canvas");
  cv.width = Math.round(r.width * k); cv.height = Math.round(r.height * k);
  const ctx = cv.getContext("2d")!;
  ctx.fillStyle = pageBg(); ctx.fillRect(0, 0, cv.width, cv.height);
  if (d instanceof HTMLCanvasElement) {
    if (scale <= 1) return d.toDataURL("image/png");
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(d, 0, 0, cv.width, cv.height);
  } else {
    const img = new Image();
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(bakedSvg(d)));
    await img.decode();
    ctx.drawImage(img, 0, 0, cv.width, cv.height);
  }
  return cv.toDataURL("image/png");
}

/** A chart as a page of its own: the drawing itself (SVG - sharp at any zoom), or a sharp picture
 *  of a canvas chart; its title and when it was made. */
async function paneHtml(el: HTMLElement, title: string): Promise<string | null> {
  const d = mainDrawing(el);
  if (!d) return null;
  const body = d instanceof HTMLCanvasElement ? `<img alt="" style="max-width:100%" src="${await paneImage(el, 2)}">`
    : new XMLSerializer().serializeToString(bakedSvg(d)).replace(/ width="[^"]*" height="[^"]*"/, ' style="width:100%;height:auto"');
  const esc = (x: string) => x.replace(/&/g, "&amp;").replace(/</g, "&lt;");
  return `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(title)}</title>
<style>body{margin:24px;font-family:system-ui,sans-serif;background:${pageBg()};color:${getComputedStyle(document.body).color}}main{max-width:1100px;margin:auto}</style></head>
<body><main><h1 style="font-size:1.2rem">${esc(title)}</h1>${body}<p style="opacity:.6;font-size:.8rem">${esc(new Date().toLocaleString())} · Signal Viewer</p></main></body></html>`;
}

/** Rows in series by the colouring: a group / category per code, holds and the others, or one. */
function seriesOf(cols: Map<string, Col>, colorBy: string | null, t: TFn): { code: (r: number) => number; names: string[]; colours: string[] } {
  const c = colorBy ? cols.get(colorBy) : undefined;
  if (c && FLAG_COLS.has(colorBy!)) return { code: (r) => (c.values[r] === 1 ? 1 : 0), names: [t("swOthers"), t("swHolds")], colours: [FAILS, HOLDS] };
  if (c && c.kind === "cat") {
    const labels = c.labels ?? [];
    // the sets in no group (#group: NaN) are a last, grey series
    return { code: (r) => (Number.isFinite(c.values[r]) ? c.values[r] : labels.length), names: [...labels, t("swNoGroup")],
      colours: [...labels.map((_, i) => category(i)), FAILS] };
  }
  return { code: () => 0, names: [""], colours: [HOLDS] };
}

export default function Desk({ study }: { study: Study }) {
  const t = useT();
  const desk = deskOf(study);
  const set = (p: Partial<typeof desk>) => useSweeps.getState().setView({ desk: { ...desk, ...p } });
  const setPane = (i: number, p: Partial<DeskPane>) => set({ panes: desk.panes.map((x, j) => (j === i ? { ...x, ...p } : x)) });
  const [big, setBig] = useState<number | null>(null);
  const shown = big !== null && desk.panes[big] ? [big] : desk.panes.map((_, i) => i);
  const add = () => set({ panes: [...desk.panes, newPane(study, desk.panes)] });
  const duplicate = (i: number) => set({ panes: [...desk.panes.slice(0, i + 1), { ...desk.panes[i] }, ...desk.panes.slice(i + 1)] });
  const remove = (i: number) => { setBig(null); set({ panes: desk.panes.filter((_, j) => j !== i) }); };
  return (
    <div className="sw-desk">
      <div className="sw-row sw-desk-bar">
        <button className="btn outline" onClick={add}><Icon.Plus width={14} height={14} /> {t("swAddChart")}</button>
        <span className="hint">{t("swDeskHint")}</span>
        <div className="sw-seg" role="radiogroup" aria-label={t("swDeskLayout")}>
          {([1, 2, 4] as const).map((n) => <button key={n} role="radio" aria-checked={desk.perRow === n} className={desk.perRow === n ? "on" : ""}
            onClick={() => { setBig(null); set({ perRow: n, layout: n }); }}>{t("swDeskPerRow", { n })}</button>)}
        </div>
      </div>
      {!desk.panes.length && <p className="empty-note">{t("swNoCharts")}</p>}
      <div className={`sw-desk-grid per${big !== null ? 1 : desk.perRow}`}>
        {shown.map((i) => (
          <Pane key={i} study={study} pane={desk.panes[i]} onChange={(p) => setPane(i, p)} big={big === i}
            onBig={() => setBig(big === i ? null : i)} onDuplicate={() => duplicate(i)} onRemove={() => remove(i)} />
        ))}
      </div>
    </div>
  );
}

function Pane({ study, pane, onChange, big, onBig, onDuplicate, onRemove }: { study: Study; pane: DeskPane; onChange: (p: Partial<DeskPane>) => void; big: boolean; onBig: () => void;
  onDuplicate: () => void; onRemove: () => void }) {
  const t = useT();
  const box = useRef<HTMLElement>(null);
  // PNG (scale 2: for a report), or the chart as a page of its own (HTML)
  const exportPng = async (scale = 1) => {
    const el = box.current;
    if (!el) return;
    const p = await pickPath({ mode: "save", title: t("swExportChart"), exts: [".png"], defaultName: `${pane.kind}${scale > 1 ? "_hires" : ""}.png` });
    if (!p) return;
    try {
      const url = await paneImage(el, scale);
      if (!url) { notify(t("swChartNoImage"), "error"); return; }
      const r = await api.saveImage(p, url);
      notify(t("swSaved", { path: r.path }));
    } catch (e) { notifyError(e); }
  };
  const exportHtml = async () => {
    const el = box.current;
    if (!el) return;
    const p = await pickPath({ mode: "save", title: t("swExportChartHtml"), exts: [".html"], defaultName: `${pane.kind}.html` });
    if (!p) return;
    try {
      const page = await paneHtml(el, `${study.name} - ${t(KIND_KEY[pane.kind])}`);
      if (!page) { notify(t("swChartNoImage"), "error"); return; }
      const r = await api.saveText(p, page, ".html", false);
      notify(t("swSaved", { path: r.path }));
    } catch (e) { notifyError(e); }
  };
  const menu = (e: React.MouseEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    openMenu({ clientX: r.left, clientY: r.bottom + 4, preventDefault() {}, stopPropagation() {} } as React.MouseEvent, [
      { label: t("swDuplicateChart"), run: onDuplicate },
      { label: t("swExportChart") + "…", run: () => exportPng(1) },
      { label: t("swExportChartHires") + "…", run: () => exportPng(2) },
      { label: t("swExportChartHtml") + "…", run: exportHtml },
      { label: t("swRemoveChart"), run: onRemove },
    ]);
  };
  const choices = axisChoices(study);
  // a group gone (deleted) is all the sets again
  const g = pane.group && (pane.group in AUTO_KEYS || study.view.groups?.some((x) => x.id === pane.group)) ? pane.group : undefined;
  const sel = (key: "x" | "y" | "size", label: TKey) => (
    <label>{t(label)} <select value={pane[key] ?? ""} onChange={(e) => onChange({ [key]: e.target.value })}>
      {choices.map((c) => <option key={c} value={c}>{colLabel(t, study, c)}</option>)}
    </select></label>
  );
  const kind = (k: PaneKind) => {
    const p: Partial<DeskPane> = { kind: k };
    if ((k === "scatter" || k === "bubble") && !pane.y) p.y = choices[1] ?? choices[0];
    if (k === "bubble" && !pane.size) p.size = choices[2] ?? choices[0];
    if ((k === "matrix" || k === "pca" || k === "som") && !pane.columns?.length) p.columns = choices.slice(0, 4);
    if (k === "map") { const ps = study.answer?.sets.filter((c) => c.group === "param").map((c) => c.name) ?? []; p.x = ps[0]; p.y = ps[1]; }
    onChange(p);
  };
  return (
    <section ref={box} className={`sw-pane${pane.inReport === false ? " sw-out-of-report" : ""}`} data-kind={pane.kind} aria-label={t(KIND_KEY[pane.kind])}>
      <div className="sw-row sw-pane-head">
        <select aria-label={t("swPaneKind")} value={pane.kind} onChange={(e) => kind(e.target.value as PaneKind)}>
          {PANE_KINDS.map((k) => <option key={k} value={k}>{t(KIND_KEY[k])}</option>)}
        </select>
        {(pane.kind === "histogram" || pane.kind === "box" || pane.kind === "history") && sel("x", "swPaneColumn")}
        <label>{t("swPaneGroup")} <select aria-label={t("swPaneGroup")} value={g ?? "all"} onChange={(e) => onChange({ group: e.target.value === "all" ? undefined : e.target.value })}>
          {Object.entries(AUTO_KEYS).map(([k, key]) => <option key={k} value={k}>{t(key)}</option>)}
          {(study.view.groups ?? []).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
        </select></label>
        {(pane.kind === "pca" || pane.kind === "som") && <MatrixColumns study={study} value={pane.columns ?? []} onChange={(columns) => onChange({ columns })} />}
        {pane.kind === "matrix" && <>
          <select aria-label={t("swCorr")} value={pane.corr ?? "pearson"} onChange={(e) => onChange({ corr: e.target.value as "pearson" | "spearman" })}>
            <option value="pearson">Pearson</option><option value="spearman">Spearman</option></select>
          <MatrixColumns study={study} value={pane.columns ?? []} onChange={(columns) => onChange({ columns })} />
        </>}
        <label className="acheck sw-in-report" title={t("swInReportHint")}><input type="checkbox" checked={pane.inReport !== false}
          onChange={(e) => onChange({ inReport: e.target.checked })} /> {t("swInReport")}</label>
        <button className="iconbtn sw-pane-big" aria-label={t(big ? "swPaneSmall" : "swPaneBig")} title={t(big ? "swPaneSmall" : "swPaneBig")} onClick={onBig}>{big ? "⤡" : "⤢"}</button>
        <button className="iconbtn sw-pane-menu" aria-label={t("swChartMenu")} title={t("swChartMenu")} onClick={menu}><Icon.More width={15} height={15} /></button>
      </div>
      {(pane.kind === "scatter" || pane.kind === "bubble") && (
        <ScatterPanel study={study} group={g} pair={{ x: pane.x ?? choices[0] ?? "", y: pane.y ?? choices[1] ?? "", size: pane.kind === "bubble" ? pane.size ?? choices[2] ?? "" : undefined }}
          onChange={(q) => onChange(q)} />
      )}
      {pane.kind === "pareto" && (study.answer?.sets.some((c) => c.name === "#obj1")
        // any two of the objectives on the axes (three or more: a pane per pair - Duplicate)
        ? <ScatterPanel study={study} group={g} pair={{ x: pane.x && isObjective(pane.x) ? pane.x : "#goal", y: pane.y && isObjective(pane.y) ? pane.y : "#obj1" }}
            onChange={(q) => onChange(q)} objectivesOnly />
        : <p className="empty-note">{t("swParetoNeedsTwo")}</p>)}
      {pane.kind === "lines" && <LinesPane study={study} group={g} />}
      {pane.kind === "map" && <MapPanel key={`${pane.x}:${pane.y}`} study={study} spec={mapSpec(study, pane)} onChange={(p) => onChange({ x: p.x ?? pane.x, y: p.y ?? pane.y })} />}
      {pane.kind === "history" && <History study={study} column={pane.x ?? choices[0]} group={g} />}
      {pane.kind === "compare" && <CompareSets study={study} group={g} />}
      {pane.kind === "histogram" && <Histogram study={study} column={pane.x ?? choices[0]} group={g} />}
      {pane.kind === "box" && <BoxPlot study={study} column={pane.x ?? choices[0]} group={g} />}
      {pane.kind === "matrix" && <Matrix study={study} columns={(pane.columns ?? []).filter((c) => choices.includes(c))} corr={pane.corr ?? "pearson"} group={g} />}
      {pane.kind === "broken" && <Broken study={study} group={g} />}
      {(pane.kind === "pca" || pane.kind === "som") && <ShapePane study={study} pane={{ ...pane, columns: (pane.columns ?? []).filter((c) => choices.includes(c)) }} group={g} onChange={onChange} />}
    </section>
  );
}

function MatrixColumns({ study, value, onChange }: { study: Study; value: string[]; onChange: (v: string[]) => void }) {
  const t = useT();
  const choices = axisChoices(study);
  return (
    <details className="sw-matrix-cols">
      <summary>{t("swColumnsOf", { n: value.length, of: choices.length })}</summary>
      <div className="sw-matrix-cols-list">
        {choices.map((c) => <label key={c} className="acheck"><input type="checkbox" checked={value.includes(c)}
          onChange={(e) => onChange(e.target.checked ? [...value, c].slice(-8) : value.filter((x) => x !== c))} />{colLabel(t, study, c)}</label>)}
      </div>
    </details>
  );
}

/** The sets on screen (scope, hidden groups) and the brush's mask over them. */
function useRows(study: Study, group?: string) {
  const { cols, n, index } = useMemo(() => scopedColumns(study), [study]);
  const kept = useMemo(() => {
    const k = keptMask(cols, study.view.filters, n), g = groupRows(study, group, cols, n, index);
    if (g) for (let r = 0; r < n; r++) k[r] &= g[r];
    return k;
  }, [cols, study, n, group, index]);
  return { cols, n, kept, index };
}

const HW = 520, HH = 260, HL = 44, HB = 34, HT = 10, HR = 10;

function extentOf(c: Col, keep?: Uint8Array): [number, number] {
  let lo = Infinity, hi = -Infinity;
  for (let i = 0; i < c.values.length; i++) if ((!keep || keep[i]) && Number.isFinite(c.values[i])) { lo = Math.min(lo, c.values[i]); hi = Math.max(hi, c.values[i]); }
  return Number.isFinite(lo) ? (lo === hi ? [lo - 0.5, hi + 0.5] : [lo, hi]) : [0, 1];
}

function Histogram({ study, column, group }: { study: Study; column: string; group?: string }) {
  const t = useT();
  const { cols, n, kept } = useRows(study, group);
  const c = cols.get(column);
  const ser = seriesOf(cols, study.view.colorBy, t);
  const [drag, setDrag] = useState<[number, number] | null>(null);
  if (!c) return <p className="empty-note">{t("swNoAxes")}</p>;
  const cat = c.kind === "cat";
  const [lo, hi] = cat ? [-0.5, (c.labels?.length ?? 1) - 0.5] : extentOf(c);
  const bins = cat ? c.labels?.length ?? 1 : BINS;
  const codes = Float32Array.from({ length: n }, (_, r) => ser.code(r));
  const h = histogram(c.values, lo, hi, bins, kept, codes, ser.names.length);
  const tot = h[0].map((_, b) => h.reduce((s, row) => s + row[b], 0));
  const max = Math.max(1, ...tot);
  const bw = (HW - HL - HR) / bins;
  const X = (v: number) => HL + ((v - lo) / (hi - lo)) * (HW - HL - HR);
  const val = (px: number) => lo + ((px - HL) / (HW - HL - HR)) * (hi - lo);
  const filtered = hasFilter(study.view.filters[column]);
  const at = (e: React.PointerEvent) => { const r = (e.currentTarget as SVGElement).getBoundingClientRect(); return ((e.clientX - r.left) / r.width) * HW; };
  const finish = () => {
    if (!drag) return;
    const [a, b] = drag; setDrag(null);
    const st = useSweeps.getState();
    if (Math.abs(b - a) < 4) { if (filtered) st.setFilter(column, null); return; }
    const u = val(Math.min(a, b)), w = val(Math.max(a, b));
    const f: Filter = cat ? { kind: "values", values: (c.labels ?? []).map((_, i) => i).filter((i) => i >= u && i <= w) }
      : { kind: "ranges", ranges: [[u, w]] };
    st.setFilter(column, f);
  };
  return (
    <div className="sw-hist">
      <svg viewBox={`0 0 ${HW} ${HH}`} className="sw-chart" role="img" aria-label={t("swPaneHistogramOf", { c: colLabel(t, study, column) })}
        onPointerDown={(e) => { (e.currentTarget as Element).setPointerCapture(e.pointerId); const x = at(e); setDrag([x, x]); }}
        onPointerMove={(e) => drag && setDrag([drag[0], at(e)])} onPointerUp={finish}>
        <line x1={HL} y1={HH - HB} x2={HW - HR} y2={HH - HB} className="sw-ax-line" />
        <line x1={HL} y1={HT} x2={HL} y2={HH - HB} className="sw-ax-line" />
        <text x={HL - 4} y={HT + 8} textAnchor="end" className="sw-ax">{max}</text>
        <text x={HL - 4} y={HH - HB} textAnchor="end" className="sw-ax">0</text>
        {tot.map((_, b) => {
          let y = HH - HB;
          return h.map((row, s) => {
            const hgt = (row[b] / max) * (HH - HB - HT);
            y -= hgt;
            return row[b] ? <rect key={`${b}:${s}`} x={HL + b * bw + 1} y={y} width={Math.max(1, bw - 2)} height={hgt} fill={ser.colours[s]}><title>{`${ser.names[s]} ${row[b]}`}</title></rect> : null;
          });
        })}
        {cat ? (c.labels ?? []).map((l, i) => <text key={i} x={HL + (i + 0.5) * bw} y={HH - HB + 14} textAnchor="middle" className="sw-ax">{l}</text>)
          : <><text x={HL} y={HH - HB + 14} textAnchor="start" className="sw-ax">{fmtValue(lo)}</text>
            <text x={HW - HR} y={HH - HB + 14} textAnchor="end" className="sw-ax">{fmtValue(hi)}</text></>}
        <text x={(HL + HW - HR) / 2} y={HH - 4} textAnchor="middle" className="sw-ax">{colLabel(t, study, column)}</text>
        {!cat && filtered && study.view.filters[column]!.kind === "ranges" && (study.view.filters[column] as { ranges: [number, number][] }).ranges.map(([a, b], k) => (
          <rect key={k} className="sw-brush-mark" x={X(Math.max(lo, Math.min(a, b)))} y={HT} width={Math.max(1, X(Math.min(hi, Math.max(a, b))) - X(Math.max(lo, Math.min(a, b))))} height={HH - HB - HT} />
        ))}
        {drag && <rect className="sw-brush-mark" x={Math.min(...drag)} y={HT} width={Math.abs(drag[1] - drag[0])} height={HH - HB - HT} />}
      </svg>
      <Legend ser={ser} />
    </div>
  );
}

function Legend({ ser }: { ser: { names: string[]; colours: string[] } }) {
  if (ser.names.length < 2) return null;
  return <div className="sw-legend">{ser.names.map((nm, i) => <span key={i}><i style={{ background: ser.colours[i] }} />{nm}</span>)}</div>;
}

function BoxPlot({ study, column, group }: { study: Study; column: string; group?: string }) {
  const t = useT();
  const { cols, n, kept } = useRows(study, group);
  const c = cols.get(column);
  const ser = seriesOf(cols, study.view.colorBy, t);
  if (!c || c.kind !== "num") return <p className="empty-note">{t("swPaneNeedsNumber")}</p>;
  const groups: number[][] = ser.names.map(() => []);
  for (let r = 0; r < n; r++) if (kept[r]) { const s = ser.code(r); if (groups[s]) groups[s].push(c.values[r]); }
  const boxes = groups.map((g, i) => ({ i, b: boxStats(g) })).filter((x) => x.b);
  const [lo, hi] = extentOf(c, kept);
  const Y = (v: number) => HH - HB - ((v - lo) / (hi - lo)) * (HH - HB - HT);
  const bw = (HW - HL - HR) / Math.max(1, boxes.length);
  return (
    <svg viewBox={`0 0 ${HW} ${HH}`} className="sw-chart" role="img" aria-label={t("swPaneBoxOf", { c: colLabel(t, study, column) })}>
      <line x1={HL} y1={HT} x2={HL} y2={HH - HB} className="sw-ax-line" />
      <text x={HL - 4} y={HT + 8} textAnchor="end" className="sw-ax">{fmtValue(hi)}</text>
      <text x={HL - 4} y={HH - HB} textAnchor="end" className="sw-ax">{fmtValue(lo)}</text>
      {boxes.map(({ i, b }, k) => {
        const cx = HL + (k + 0.5) * bw, w = Math.min(60, bw * 0.5);
        return (
          <g key={i} data-series={ser.names[i]}>
            <title>{`${ser.names[i] || colLabel(t, study, column)} · n ${b!.n} · ${fmtValue(b!.q1)} / ${fmtValue(b!.med)} / ${fmtValue(b!.q3)}`}</title>
            <line x1={cx} x2={cx} y1={Y(b!.lo)} y2={Y(b!.hi)} className="sw-ax-line" />
            <rect x={cx - w / 2} y={Y(b!.q3)} width={w} height={Math.max(1, Y(b!.q1) - Y(b!.q3))} fill={ser.colours[i]} fillOpacity={0.55} stroke={ser.colours[i]} />
            <line x1={cx - w / 2} x2={cx + w / 2} y1={Y(b!.med)} y2={Y(b!.med)} stroke={ser.colours[i]} strokeWidth={2} />
            {b!.out.slice(0, 200).map((v, j) => <circle key={j} cx={cx} cy={Y(v)} r={2} fill={ser.colours[i]} />)}
            <text x={cx} y={HH - HB + 14} textAnchor="middle" className="sw-ax">{ser.names[i]}</text>
          </g>
        );
      })}
      <text x={(HL + HW - HR) / 2} y={HH - 4} textAnchor="middle" className="sw-ax">{colLabel(t, study, column)}</text>
    </svg>
  );
}

/** Correlation as a colour: blue negative, amber positive (the palette's own two). */
const corrFill = (r: number) => (Number.isFinite(r) ? (r >= 0 ? `rgba(242,169,59,${Math.abs(r) * 0.85})` : `rgba(111,168,255,${Math.abs(r) * 0.85})`) : "transparent");

function Matrix({ study, columns, corr, group }: { study: Study; columns: string[]; corr: "pearson" | "spearman"; group?: string }) {
  const t = useT();
  const { cols, n, kept } = useRows(study, group);
  const ser = seriesOf(cols, study.view.colorBy, t);
  const cs = columns.map((c) => cols.get(c)).filter((c): c is Col => !!c);
  const k = cs.length;
  const coef = useMemo(() => cs.map((a) => cs.map((b) => (corr === "spearman" ? spearman(a.values, b.values, kept) : pearson(a.values, b.values, kept)))),
    [cs.map((c) => c.name).join("|"), corr, kept, cols]); // eslint-disable-line react-hooks/exhaustive-deps
  if (k < 2) return <p className="empty-note">{t("swMatrixPick")}</p>;
  const S = 100, PAD = 4;
  // at most 1500 points a cell: every m-th kept row
  const rows: number[] = [];
  for (let r = 0; r < n; r++) if (kept[r]) rows.push(r);
  const step = Math.max(1, Math.ceil(rows.length / 1500));
  const sample = rows.filter((_, i) => i % step === 0);
  const ext = cs.map((c) => extentOf(c, kept));
  const nx = (j: number, v: number) => PAD + ((v - ext[j][0]) / (ext[j][1] - ext[j][0])) * (S - 2 * PAD);
  const ny = (i: number, v: number) => S - PAD - ((v - ext[i][0]) / (ext[i][1] - ext[i][0])) * (S - 2 * PAD);
  return (
    <div className="sw-matrix-wrap">
      <svg viewBox={`0 0 ${k * S + 60} ${k * S + 60}`} className="sw-chart sw-matrix" role="img" aria-label={t("swPaneMatrix")}>
        {cs.map((a, i) => cs.map((b, j) => {
          const x0 = 60 + j * S, y0 = i * S;
          if (i === j) {
            const [lo, hi] = ext[i];
            const h = histogram(a.values, lo, hi, 12, kept)[0], mx = Math.max(1, ...h), w = (S - 2 * PAD) / 12;
            return <g key={`${i}${j}`} transform={`translate(${x0},${y0})`}><rect width={S} height={S} className="sw-matrix-cell" />
              {h.map((v, q) => <rect key={q} x={PAD + q * w} y={S - PAD - (v / mx) * (S - 2 * PAD)} width={w - 1} height={(v / mx) * (S - 2 * PAD)} fill={HOLDS} />)}</g>;
          }
          if (i > j) return (
            <g key={`${i}${j}`} transform={`translate(${x0},${y0})`} data-coef={coef[i][j]}>
              <rect width={S} height={S} className="sw-matrix-cell" fill={corrFill(coef[i][j])} />
              <text x={S / 2} y={S / 2 + 5} textAnchor="middle" className="sw-matrix-r">{Number.isFinite(coef[i][j]) ? coef[i][j].toFixed(2) : "–"}</text>
              <title>{`${corr === "spearman" ? "ρ" : "r"}(${colLabel(t, study, a.name)}, ${colLabel(t, study, b.name)}) = ${Number.isFinite(coef[i][j]) ? coef[i][j].toFixed(3) : "–"}`}</title>
            </g>
          );
          return (
            <g key={`${i}${j}`} transform={`translate(${x0},${y0})`}><rect width={S} height={S} className="sw-matrix-cell" />
              {sample.map((r) => { const X = nx(j, b.values[r]), Y = ny(i, a.values[r]);
                return Number.isFinite(X) && Number.isFinite(Y) ? <circle key={r} cx={X} cy={Y} r={1.4} fill={ser.colours[ser.code(r)] ?? HOLDS} /> : null; })}</g>
          );
        }))}
        {cs.map((c, i) => <text key={`l${i}`} x={56} y={i * S + S / 2} textAnchor="end" className="sw-ax">{short(colLabel(t, study, c.name))}</text>)}
        {cs.map((c, j) => <text key={`b${j}`} x={60 + j * S + S / 2} y={k * S + 14} textAnchor="middle" className="sw-ax">{short(colLabel(t, study, c.name))}</text>)}
      </svg>
    </div>
  );
}
const short = (s: string) => (s.length > 14 ? `${s.slice(0, 13)}…` : s);

/** Which condition fails how often (among the sets on screen); a bar's click keeps the sets that fail it. */
function Broken({ study, group }: { study: Study; group?: string }) {
  const t = useT();
  const { cols, n, kept } = useRows(study, group);
  const a = study.answer!;
  const list = a.conditions.map((c, i) => {
    const m = cols.get(`#c${i}.margin`), p = cols.get(`#c${i}.passed`), need = c.needed ?? 0;
    let k = 0;
    for (let r = 0; r < n; r++) if (kept[r] && (need > 0 && p ? p.values[r] < need : m ? m.values[r] < 0 : false)) k++;
    return { i, label: c.label, k, margin: m };
  });
  if (!list.length) return <p className="empty-note">{t("swBrokenNone")}</p>;
  let shown = 0;
  for (let r = 0; r < n; r++) shown += kept[r];
  const max = Math.max(1, ...list.map((x) => x.k));
  const keepFailing = (x: (typeof list)[number]) => {
    if (!x.margin) return;
    const [lo] = extentOf(x.margin);
    useSweeps.getState().setFilter(x.margin.name, { kind: "ranges", ranges: [[Math.min(lo, -1e-9), -1e-9]] });
  };
  return (
    <div className="sw-broken" role="list">
      {list.map((x) => (
        <button key={x.i} role="listitem" className="sw-broken-row" onClick={() => keepFailing(x)} title={t("swBrokenKeep")}>
          <span className="sw-broken-label mono">{x.label}</span>
          <span className="sw-broken-bar"><i style={{ width: `${(x.k / max) * 100}%` }} /></span>
          <span className="sw-broken-n">{t("swBrokenN", { k: x.k.toLocaleString(), n: shown.toLocaleString() })}</span>
        </button>
      ))}
    </div>
  );
}


/** The lines in a pane: the study's axes, the same brush (a range on an axis filters everything). */
function LinesPane({ study, group }: { study: Study; group?: string }) {
  const t = useT();
  const st = useSweeps.getState();
  const { cols, n, kept, index } = useRows(study, group);
  const axes = shownAxes(study);
  const v = study.view;
  const scale = useMemo(() => (name: string) => scaleOf(study, name, cols.get(name)), [study, cols]);
  if (!axes.length) return <p className="empty-note">{t("swNoAxes")}</p>;
  const setOf = (r: number) => (v.mode === "runs" ? cols.get("#set")?.values[r] ?? r : index ? index[r] : r);
  return (
    <ParallelPlot cols={cols} n={n} axes={axes} scaleOf={scale} reversed={v.reversed} colorBy={v.colorBy && cols.has(v.colorBy) ? v.colorBy : null}
      filters={v.filters} keep={group ? kept : null} highlight={null} labelOf={(a) => colLabel(t, study, a)} fit height={280}
      onPick={(r) => st.setView({ pinned: setOf(r) })} onFilter={(name, f) => st.setFilter(name, f)} onAxisMenu={() => {}}
      onMoveAxis={(name, to) => { const from = v.axes.indexOf(name); const target = v.axes.indexOf(axes[to]); if (from >= 0 && target >= 0) st.moveAxis(from, target); }} />
  );
}

/** A column against the sets' order (their order in the table: the order they were run in), with
 *  the best so far when the column is the goal. */
function History({ study, column, group }: { study: Study; column: string; group?: string }) {
  const t = useT();
  const { cols, n, kept } = useRows(study, group);
  const c = cols.get(column);
  if (!c || c.kind !== "num") return <p className="empty-note">{t("swPaneNeedsNumber")}</p>;
  const rows: number[] = [];
  for (let r = 0; r < n; r++) if (kept[r] && Number.isFinite(c.values[r])) rows.push(r);
  if (!rows.length) return <p className="empty-note">{t("swNoSetsShown")}</p>;
  const [lo, hi] = extentOf(c, kept);
  const X = (k: number) => HL + (rows.length > 1 ? k / (rows.length - 1) : 0.5) * (HW - HL - HR);
  const Y = (v: number) => HH - HB - ((v - lo) / (hi - lo)) * (HH - HB - HT);
  const dir = column === "#goal" ? study.question.goal?.direction : undefined;
  let best = NaN;
  const bestPts = dir ? rows.map((r, k) => { const v = c.values[r]; best = !Number.isFinite(best) || (dir === "max" ? v > best : v < best) ? v : best; return `${X(k)},${Y(best)}`; }) : [];
  return (
    <svg viewBox={`0 0 ${HW} ${HH}`} className="sw-chart" role="img" aria-label={t("swPaneHistoryOf", { c: colLabel(t, study, column) })}>
      <line x1={HL} y1={HH - HB} x2={HW - HR} y2={HH - HB} className="sw-ax-line" />
      <line x1={HL} y1={HT} x2={HL} y2={HH - HB} className="sw-ax-line" />
      <text x={HL - 4} y={HT + 8} textAnchor="end" className="sw-ax">{fmtValue(hi)}</text>
      <text x={HL - 4} y={HH - HB} textAnchor="end" className="sw-ax">{fmtValue(lo)}</text>
      {rows.map((r, k) => <circle key={r} cx={X(k)} cy={Y(c.values[r])} r={2} fill={FAILS} />)}
      {bestPts.length > 0 && <polyline points={bestPts.join(" ")} fill="none" stroke={HOLDS} strokeWidth={2} className="sw-history-best" />}
      <text x={(HL + HW - HR) / 2} y={HH - 4} textAnchor="middle" className="sw-ax">{t("swHistoryX", { c: colLabel(t, study, column) })}</text>
    </svg>
  );
}

/** Up to four sets side by side - the marked ones (the table's ticks), else the best of the group -
 *  their parameters and results, the values that differ marked. */
function CompareSets({ study, group }: { study: Study; group?: string }) {
  const t = useT();
  const a = study.answer!;
  const { kept } = useRows(study, group);
  const v = study.view;
  const rank = a.sets.find((c) => c.name === "#rank")?.values;
  let sets = v.rerun.slice(0, 4);
  if (sets.length < 2 && v.mode === "sets") {
    const order = [...Array(kept.length).keys()].filter((r) => kept[r]).sort((x, y) => (rank ? (Number.isFinite(rank[x]) ? rank[x] : 1e9) - (Number.isFinite(rank[y]) ? rank[y] : 1e9) : x - y));
    sets = order.slice(0, 4);
  }
  if (sets.length < 2) return <p className="empty-note">{t("swCompareSetsPick")}</p>;
  const rows = a.sets.filter((c) => c.group === "param" || c.group === "goal" || c.name === "#holds" || (c.group === "condition" && c.part === "worst"));
  return (
    <div className="sw-table-wrap">
      <table className="sw-table sw-compare-sets">
        <thead><tr><th />{sets.map((s) => <th key={s} className="num">{t("swSetN", { n: s + 1 })}</th>)}</tr></thead>
        <tbody>
          {rows.map((c) => {
            const vals = sets.map((s) => labelOf(c, c.values[s]));
            const differ = new Set(vals).size > 1;
            return <tr key={c.name} className={differ ? "differs" : ""}><th>{colLabel(t, study, c.name)}</th>{vals.map((x, i) => <td key={i} className="num">{x}</td>)}</tr>;
          })}
        </tbody>
      </table>
      {v.rerun.length < 2 && <p className="hint">{t("swCompareSetsHint")}</p>}
    </div>
  );
}
