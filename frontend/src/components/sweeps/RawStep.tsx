/* Step 1 - the data (owner, 2026-11-02). Every table read is a table of its own; merging is a step
   of its own whose result is a NEW table (the tables merged stay). The middle only shows - the table
   picked in the list, as a table (page by page, sortable) or as a parallel plot; every action is in
   the side panel: the tables (tick to merge, show, export, close), the merge, and which table the
   next steps work on (Continue with). */
import { useEffect, useMemo, useState } from "react";
import { pickPath } from "../../store";
import { useT, type TFn } from "../../i18n";
import { Icon } from "../../icons";
import { sweepApi, type MergeSpec } from "../../sweeps/api";
import { decodeCol } from "../../sweeps/decode";
import type { Col, Filter } from "../../sweeps/model";
import { keptMask } from "../../sweeps/filters";
import { fmtValue, labelOf } from "../../sweeps/scales";
import { useSweeps, type RawView, type Study, type StudyTable } from "../../sweeps/state";
import { groupLabel, presetChoices } from "../../sweeps/view";
import { PRESET_KEY } from "./PlotToolbar";
import AxisMenu from "./AxisMenu";
import ColumnPicker from "./ColumnPicker";
import ParallelPlot from "./ParallelPlot";
import { NO_ZOOM, zoomAt } from "../../sweeps/zoom";
import { notify, notifyError } from "../../sweeps/notify";

const TABLE_EXTS = [".csv", ".tsv", ".txt", ".parquet", ".pq", ".xlsx", ".xls"];
const stem = (n: string) => n.replace(/\.[^.]+$/, "");

/** The roles of a table's columns: the study's for the table in use, the guess for the others. */
function rolesOf(s: Study, tb: StudyTable) {
  if (tb.id === s.tableId) {
    const removed = new Set(s.question.removed);
    return new Map(s.columns.map((c) => [c.name, removed.has(c.name) ? "ignore" as const : c.role]));
  }
  return new Map(tb.opened.columns.map((c) => [c.name, c.role]));
}

export function RawSide({ study }: { study: Study }) {
  const t = useT();
  return (
    <div className="sw-side-step">
      <p className="sw-step-intro">{t("swRawIntro")}</p>
      <TablesBox study={study} />
      <MergeBox study={study} />
      <ContinueWith study={study} />
    </div>
  );
}

/** Tables in this study: tick to merge, a click shows it in the middle, download, close. */
function TablesBox({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const add = async () => {
    const p = await pickPath({ mode: "open", title: t("swAddTable"), exts: TABLE_EXTS });
    if (p) st.addTable(p).catch(notifyError);
  };
  return (
    <section className="sw-hide-box sw-tables" aria-label={t("swTables")}>
      <b>{t("swTables")}</b>
      <ul className="sw-table-list">
        {study.tables.map((tb, i) => {
          const picked = study.picked.includes(tb.id);
          return (
            <li key={tb.id} className={`sw-table-item${i === study.shown ? " on" : ""}${i === study.use ? " used" : ""}`}>
              <input type="checkbox" checked={picked} aria-label={t("swTickToMerge", { n: tb.name })} title={t("swTickToMerge", { n: tb.name })}
                onChange={() => st.setPicked(picked ? study.picked.filter((x) => x !== tb.id) : [...study.picked, tb.id])} />
              <button className="sw-table-name" title={tb.name} onClick={() => st.setShown(i)} aria-current={i === study.shown ? "true" : undefined}>
                {tb.merged && <Icon.Merge width={13} height={13} />}<span className="sw-ellipsis">{tb.name}</span>
              </button>
              <span className="hint sw-table-rows">{tb.opened.rows.toLocaleString()}</span>
              <button className="iconbtn sm" title={t("swExportDataHint")} aria-label={`${t("swExportDataHint")}: ${tb.name}`}
                onClick={() => exportTable(t, study, tb)}><Icon.Download width={14} height={14} /></button>
              <button className="iconbtn sm" title={t("swCloseTableN", { n: tb.name })} aria-label={t("swCloseTableN", { n: tb.name })}
                onClick={() => st.closeTable(i)}><Icon.X width={13} height={13} /></button>
            </li>
          );
        })}
      </ul>
      <button className="btn outline" onClick={add}><Icon.Plus width={14} height={14} /> {t("swAddTable")}</button>
    </section>
  );
}

/** A table to a file: the OS-like save dialog at once, CSV or HTML with the parallel plot (the one
 *  chosen first follows the tab on screen); the plot as it was left. */
async function exportTable(t: TFn, study: Study, tb: StudyTable) {
  const st = useSweeps.getState();
  const html = st.dataTab === "plot";
  const p = await pickPath({ mode: "save", title: t("swExportDataHint"), exts: [".csv", ".html"],
    types: [{ label: "CSV (*.csv)", ext: ".csv" }, { label: t("swHtmlWithPlot"), ext: ".html" }], type: html ? 1 : 0,
    defaultName: stem(tb.name) + (html ? ".html" : ".csv") });
  if (!p) return;
  const format = p.toLowerCase().endsWith(".html") ? "html" : "csv";
  const v = st.rawViews[tb.id];
  try {
    const r = await sweepApi.exportTable(tb.id, p, format, format === "csv" ? {} : {
      title: tb.name, axes: v?.axes ?? defaultAxes(study, tb),
      labels: { "#shown": t("swShown", { n: "{n}", of: "{of}" }), "#clear": t("swRepClear"), "#hint": t("swRepHtmlHint"), "#colour": t("swColourByThis"), "#resetZoom": t("swResetZoom") },
      view: { colorBy: v?.colorBy ?? null, filters: v?.filters ?? {}, zoom: st.zooms[tb.id] ?? NO_ZOOM } });
    notify(t("swExported", { n: r.rows, path: r.path }));
    st.journal("export", { path: r.path, n: r.rows });
  } catch (e) { notifyError(e); }
}

const defaultAxes = (s: Study, tb: StudyTable) => {
  const role = rolesOf(s, tb);
  return tb.opened.columns.filter((c) => !c.constant && !c.empty && role.get(c.name) !== "id" && role.get(c.name) !== "ignore").map((c) => c.name).slice(0, 12);
};

/** Merge: always here; it answers the tables ticked above. Its result is a new table. */
function MergeBox({ study }: { study: Study }) {
  const t = useT();
  const parts = study.tables.filter((x) => study.picked.includes(x.id));
  const [how, setHow] = useState<"concat" | "join">("concat");
  const [keys, setKeys] = useState<string[]>([]);
  const [addSource, setAddSource] = useState(true);
  const [source, setSource] = useState("_source");
  const [dedupe, setDedupe] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pv, setPv] = useState<{ rows: number; partial: string[]; common: string[]; error: string } | null>(null);
  const spec: MergeSpec = { names: parts.map((x) => x.name), how, keys, source: how === "concat" && addSource ? source.trim() : "", dedupe };
  const key = JSON.stringify([parts.map((x) => x.id), spec]);
  useEffect(() => {
    if (parts.length < 2) { setPv(null); return; }
    let live = true;
    const h = window.setTimeout(() => sweepApi.combinePreview(parts.map((x) => x.id), spec).then((r) => live && setPv(r)).catch(() => live && setPv(null)), 150);
    return () => { live = false; window.clearTimeout(h); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  if (parts.length < 2) return <section className="sw-hide-box" aria-label={t("swMergeTitle")}><b>{t("swMergeTitle")}</b><p className="hint">{t("swMergeTickTwo")}</p></section>;
  const create = async () => {
    setBusy(true);
    try { await useSweeps.getState().mergeTables(parts.map((x) => x.id), spec); notify(t("swMergedNew", { n: parts.length })); }
    catch (e) { notifyError(e); }
    finally { setBusy(false); }
  };
  return (
    <section className="sw-hide-box sw-merge" aria-label={t("swMergeTitle")}>
      <b>{t("swMergeTitle")} <span className="hint">({parts.length})</span></b>
      <label className="sw-row">{t("swMergeHow")}
        <select value={how} onChange={(e) => setHow(e.target.value as "concat" | "join")} aria-label={t("swMergeHow")}>
          <option value="concat">{t("swMergeConcat")}</option><option value="join">{t("swMergeJoin")}</option>
        </select></label>
      {how === "join" && (
        <div className="sw-join-keys"><span className="hint">{t("swJoinKeys")}</span>
          <div className="sw-hold-values">{(pv?.common ?? []).map((c) => {
            const on = keys.includes(c);
            return <button key={c} className={`sw-pill${on ? " on" : ""}`} aria-pressed={on} title={c}
              onClick={() => setKeys(on ? keys.filter((x) => x !== c) : [...keys, c])}>{c}</button>;
          })}</div></div>
      )}
      {how === "concat" && (
        <label className="acheck" title={t("swAddSourceHint")}>
          <input type="checkbox" checked={addSource} onChange={(e) => setAddSource(e.target.checked)} /> {t("swAddSource")}
          {addSource && <input className="sw-source-name" value={source} aria-label={t("swSourceName")} spellCheck={false} dir="ltr"
            onChange={(e) => setSource(e.target.value)} />}
        </label>
      )}
      <label className="acheck"><input type="checkbox" checked={dedupe} onChange={(e) => setDedupe(e.target.checked)} /> {t("swRemoveDuplicates")}</label>
      {pv && (pv.error ? <p className="sw-warn">{pv.error}</p> : (
        <p className="hint sw-merge-preview">{t("swMergePreview", { n: pv.rows.toLocaleString() })}
          {pv.partial.length > 0 && <> {t("swMergePartial", { list: pv.partial.join(", ") })}</>}</p>
      ))}
      <button className="btn primary" disabled={busy || !!pv?.error || (how === "join" && !keys.length) || (how === "concat" && addSource && !source.trim())}
        onClick={create}>{t("swCreateMerged")}</button>
    </section>
  );
}

/** Which table the next steps work on - one table or a merged one - and on to Columns. */
function ContinueWith({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  return (
    <div className="sw-step-foot sw-continue">
      <label className="sw-continue-pick"><span>{t("swContinueWith")}</span>
        <select value={study.use} onChange={(e) => st.useTable(Number(e.target.value))} aria-label={t("swContinueWith")}>
          {study.tables.map((tb, i) => <option key={tb.id} value={i}>{tb.name}</option>)}
        </select></label>
      <button className="btn primary" onClick={() => st.setView({ step: "roles" })}>{t("swStepColumns")} →</button>
    </div>
  );
}

export function RawCenter({ study }: { study: Study }) {
  const t = useT();
  const tab = useSweeps((s) => s.dataTab);
  const tb = study.tables[study.shown] ?? study.tables[study.use];
  if (!tb) return null;
  return (
    <>
      <div className="sw-center-tabs" role="tablist">
        <button role="tab" aria-selected={tab === "table"} className={tab === "table" ? "on" : ""} onClick={() => useSweeps.setState({ dataTab: "table" })}>{t("swRawTable")}</button>
        <button role="tab" aria-selected={tab === "plot"} className={tab === "plot" ? "on" : ""} onClick={() => useSweeps.setState({ dataTab: "plot" })}>{t("swRawPlot")}</button>
        <span className="sw-tabs-name sw-ellipsis" title={tb.name}>{tb.merged && <Icon.Merge width={13} height={13} />} {tb.name}</span>
      </div>
      {tab === "table" ? <RawTable key={tb.id} study={study} tb={tb} /> : <RawPlot key={tb.id} study={study} tb={tb} />}
    </>
  );
}

const PAGE = 100;

function RawTable({ study, tb }: { study: Study; tb: StudyTable }) {
  const t = useT();
  const pickedRun = useSweeps((s) => s.rawViews[tb.id]?.picked ?? null);
  const [picked, setPicked] = useState<string[] | null>(null);          // null: every column
  const [page, setPage] = useState(() => (pickedRun !== null ? Math.floor(pickedRun / PAGE) : 0));
  const [sort, setSort] = useState<{ c: string; desc: boolean } | null>(null);
  const [data, setData] = useState<{ total: number; columns: string[]; rows: (string | number | null)[][]; index: number[] } | null>(null);
  useEffect(() => {
    let live = true;
    sweepApi.rows(tb.id, page * PAGE, PAGE, sort?.c, sort?.desc).then((r) => live && setData(r)).catch(() => {});
    return () => { live = false; };
  }, [tb.id, tb.opened.rows, page, sort]);
  const role = rolesOf(study, tb);
  if (!data) return <p className="hint">{t("swReading")}</p>;
  const pages = Math.max(1, Math.ceil(data.total / PAGE));
  // the columns to show: all of them (as read, the removed ones too), or those picked
  const shownNames = picked ? picked.filter((c) => data.columns.includes(c)) : data.columns;
  const show = shownNames.map((c) => data.columns.indexOf(c));
  return (
    <div className="sw-raw">
      <div className="sw-row">
        <button className="btn outline" disabled={page === 0} onClick={() => setPage(page - 1)}>←</button>
        <span className="hint">{t("swRawRows", { a: (page * PAGE + 1).toLocaleString(), b: Math.min(data.total, (page + 1) * PAGE).toLocaleString(), n: data.total.toLocaleString() })}</span>
        <button className="btn outline" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>→</button>
        <span className="hint">{t("swRawSortHint")}</span>
        {pickedRun !== null && !data.index.includes(pickedRun) && !sort && (
          <button className="linklike" onClick={() => setPage(Math.floor(pickedRun / PAGE))}>{t("swGoToPicked")}</button>)}
        <ColumnPicker options={rawOptions(t, study, tb, data.columns)} value={shownNames} onChange={setPicked}
          presets={presetChoices(t, study, data.columns, PRESET_KEY, ["params-goal"])} />
      </div>
      <div className="sw-table-wrap">
        <table className="sw-table sw-sticky-first">
          <thead><tr>{show.map((j) => data.columns[j]).map((c) => (
            <th key={c} className={`sw-th-${role.get(c) ?? "output"}`} title={c} onClick={() => setSort(sort?.c === c ? { c, desc: !sort.desc } : { c, desc: false })}>
              <span className="sw-ellipsis">{c}</span>{sort?.c === c ? (sort.desc ? " ▼" : " ▲") : ""}</th>
          ))}</tr></thead>
          <tbody>{data.rows.map((r, i) => (
            <tr key={i} className={data.index[i] === pickedRun ? "sw-picked-row" : ""}>{show.map((j) => [r[j], j] as const).map(([v, j]) => <td key={j} className={`${typeof v === "number" ? "num" : ""}${role.get(data.columns[j]) === "ignore" ? " sw-dim" : ""}`}>
              {v === null ? "–" : typeof v === "number" ? fmtValue(v) : String(v)}</td>)}</tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}

/** Every run as a line - before roles or goals. A click on a column's name colours by it (its menu:
 *  right-click); the wheel zooms, a drag pans while zoomed; a click on a line shows that run. What
 *  is left stays when the tab or the table changes (the store's rawViews / zooms). */
export function RawPlot({ study, tb }: { study: Study; tb: StudyTable }) {
  const t = useT();
  const st = useSweeps.getState();
  const saved = useSweeps((s) => s.rawViews[tb.id]);
  const zoom = useSweeps((s) => s.zooms[tb.id]) ?? NO_ZOOM;
  const [cols, setCols] = useState<Map<string, Col> | null>(null);
  const [n, setN] = useState(0);
  const [menu, setMenu] = useState<{ name: string; at: DOMRect } | null>(null);
  const [err, setErr] = useState("");
  const v: RawView = saved ?? { axes: defaultAxes(study, tb), filters: {}, colorBy: null, scales: {}, reversed: {}, picked: null };
  const put = (p: Partial<RawView>) => st.setRawView(tb.id, { ...v, ...p });
  useEffect(() => {
    let live = true;
    sweepApi.raw(tb.id).then((r) => {
      if (!live) return;
      setCols(new Map(r.columns.map((w) => { const c = decodeCol(w, "run"); return [c.name, c] as [string, Col]; })));
      setN(r.n);
    }).catch((e) => live && setErr((e as Error).message));
    return () => { live = false; };
  }, [tb.id, tb.opened.rows]);
  const rowCol = cols?.get("#row")?.values;
  // the run picked, by its row of the table, drawn thick
  const highlight = useMemo(() => {
    if (!rowCol || v.picked === null || v.picked === undefined) return null;
    const h = new Uint8Array(n);
    for (let i = 0; i < n; i++) if (rowCol[i] === v.picked) h[i] = 1;
    return h;
  }, [rowCol, v.picked, n]);
  const shown = useMemo(() => { if (!cols) return 0; const m = keptMask(cols, v.filters, n); let k = 0; for (let i = 0; i < n; i++) k += m[i]; return k; }, [cols, v.filters, n]);
  if (!cols) return <p className="hint">{err || t("swReading")}</p>;
  const axes = v.axes.filter((a) => cols.has(a));
  const scaleOf = (a: string) => v.scales[a] ?? tb.opened.columns.find((c) => c.name === a)?.scale ?? "linear";
  const setFilter = (a: string, f: Filter | null) => { const x = { ...v.filters }; if (f) x[a] = f; else delete x[a]; put({ filters: x }); };
  const pickedAt = v.picked !== null && v.picked !== undefined && highlight ? highlight.indexOf(1) : -1;
  return (
    <>
      <div className="sw-plotbar">
        <ColumnPicker options={rawOptions(t, study, tb, [...cols.keys()].filter((c) => c !== "#row"))} value={axes} onChange={(a) => put({ axes: a })}
          presets={presetChoices(t, study, [...cols.keys()], PRESET_KEY, ["params-goal"])} />
        <span className="hint">{v.colorBy ? `${t("swColourBy")}: ${v.colorBy}` : t("swRawColourHint")}</span>
        <span className="hint sw-count">{t("swShown", { n: shown.toLocaleString(), of: n.toLocaleString() })}</span>
        {Object.keys(v.filters).length > 0 && <button className="btn outline" onClick={() => put({ filters: {} })}>{t("swClearFilters", { n: Object.keys(v.filters).length })}</button>}
        <ZoomButtons zoom={zoom} onZoom={(z) => st.setZoom(tb.id, z)} />
      </div>
      <ParallelPlot sliderLabel={(a, b, k) => t("swAxesOnScreen", { a, b, n: k })} cols={cols} n={n} axes={axes} scaleOf={scaleOf} reversed={v.reversed}
        colorBy={v.colorBy && cols.has(v.colorBy) ? v.colorBy : null} filters={v.filters} highlight={highlight}
        labelOf={(a) => a} onPick={(r) => put({ picked: rowCol ? rowCol[r] : r })} onFilter={setFilter}
        onAxisClick={(a) => put({ colorBy: v.colorBy === a ? null : a })}
        onAxisMenu={(name, at) => setMenu({ name, at })} zoom={zoom} onZoom={(z) => st.setZoom(tb.id, z)}
        onMoveAxis={(name, to) => { const a = axes.filter((x) => x !== name); a.splice(to, 0, name); put({ axes: a }); }} height={460} />
      {pickedAt >= 0 && (
        <div className="sw-run-values" role="region" aria-label={t("swPickedRun")}>
          <b>{t("swPickedRun")} #{v.picked}</b>
          <button className="iconbtn sm" aria-label={t("swDismiss")} onClick={() => put({ picked: null })}><Icon.X width={12} height={12} /></button>
          <dl>{axes.map((a) => { const c = cols.get(a)!; return <div key={a}><dt title={a}>{a}</dt><dd>{labelOf(c, c.values[pickedAt])}</dd></div>; })}</dl>
          <span className="hint">{t("swPickedInTable")}</span>
        </div>
      )}
      {menu && cols.get(menu.name) && (
        <AxisMenu col={cols.get(menu.name)!} label={menu.name} at={menu.at} scale={scaleOf(menu.name)} reversed={!!v.reversed[menu.name]}
          filter={v.filters[menu.name]} colouring={v.colorBy === menu.name}
          onScale={(s) => put({ scales: { ...v.scales, [menu.name]: s } })} onReverse={() => put({ reversed: { ...v.reversed, [menu.name]: !v.reversed[menu.name] } })}
          onColour={() => put({ colorBy: v.colorBy === menu.name ? null : menu.name })} onHide={() => { put({ axes: axes.filter((a) => a !== menu.name) }); setMenu(null); }}
          onFilter={(f) => setFilter(menu.name, f)} onClose={() => setMenu(null)} />
      )}
    </>
  );
}

/** Zoom in / out / back for a parallel plot (the wheel does the same). */
export function ZoomButtons({ zoom, onZoom }: { zoom: { k: number; x: number; y: number }; onZoom: (z: { k: number; x: number; y: number }) => void }) {
  const t = useT();
  // around the middle of what is on screen (the plot's own width is not known here: a fair guess)
  const mid = (f: number) => onZoom(zoomAt(zoom, f, 400, 220));
  return (
    <span className="sw-zoom" role="group" aria-label={t("swZoom")}>
      <button className="iconbtn sm" onClick={() => mid(1.25)} title={t("swZoomIn")} aria-label={t("swZoomIn")}>+</button>
      <button className="iconbtn sm" onClick={() => mid(0.8)} disabled={zoom.k <= 1} title={t("swZoomOut")} aria-label={t("swZoomOut")}>−</button>
      <button className="btn outline sm" onClick={() => onZoom(NO_ZOOM)} disabled={zoom.k <= 1}>{t("swResetZoom")}</button>
    </span>
  );
}

/** A table's columns for the picker, grouped by their role (a column taken out: Not used). */
function rawOptions(t: TFn, s: Study, tb: StudyTable, names: string[]) {
  const role = rolesOf(s, tb);
  return names.map((n) => ({ id: n, label: n, group: groupLabel(t, role.get(n) ?? "ignore") }));
}
