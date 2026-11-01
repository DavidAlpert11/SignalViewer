/* Step 1 - the results as they came: the table, page by page (sortable), or all of it as a parallel
   plot to play with (and export alone). Nothing is decided yet. Another table - a second sweep - is
   added (merged) here. */
import { useEffect, useMemo, useState } from "react";
import { pickPath } from "../../store";
import { useT, type TFn } from "../../i18n";
import { sweepApi } from "../../sweeps/api";
import { decodeCol } from "../../sweeps/decode";
import type { Col, Filter, Scale } from "../../sweeps/model";
import { keptMask } from "../../sweeps/filters";
import { fmtValue } from "../../sweeps/scales";
import { useSweeps, type Study } from "../../sweeps/state";
import { groupLabel, presetChoices } from "../../sweeps/view";
import { PRESET_KEY } from "./PlotToolbar";
import AxisMenu from "./AxisMenu";
import ColumnPicker from "./ColumnPicker";
import ParallelPlot from "./ParallelPlot";
import { MergeBox } from "./Shape";
import { StepFoot } from "./StepNav";
import { notify, notifyError } from "../../sweeps/notify";

export function RawSide({ study }: { study: Study }) {
  const t = useT();
  return (
    <div className="sw-side-step">
      <p className="sw-step-intro">{t("swRawIntro")}</p>
      <dl className="sw-facts">
        <div><dt>{t("swRuns")}</dt><dd>{study.rows.toLocaleString()}</dd></div>
        <div><dt>{t("swColumnsN")}</dt><dd>{study.columns.length}</dd></div>
        <div><dt>{t("swReadInShort")}</dt><dd>{study.seconds.toFixed(2)} s</dd></div>
      </dl>
      <MergeBox study={study} />
      <StepFoot study={study} />
    </div>
  );
}

export function RawCenter({ study }: { study: Study }) {
  const t = useT();
  const [tab, setTab] = useState<"table" | "plot">("table");
  return (
    <>
      <div className="sw-center-tabs" role="tablist">
        <button role="tab" aria-selected={tab === "table"} className={tab === "table" ? "on" : ""} onClick={() => setTab("table")}>{t("swRawTable")}</button>
        <button role="tab" aria-selected={tab === "plot"} className={tab === "plot" ? "on" : ""} onClick={() => setTab("plot")}>{t("swRawPlot")}</button>
      </div>
      {tab === "table" ? <RawTable study={study} /> : <RawPlot study={study} />}
    </>
  );
}

const PAGE = 100;

function RawTable({ study }: { study: Study }) {
  const t = useT();
  const [picked, setPicked] = useState<string[] | null>(null);          // null: every column
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState<{ c: string; desc: boolean } | null>(null);
  const [data, setData] = useState<{ total: number; columns: string[]; rows: (string | number | null)[][] } | null>(null);
  useEffect(() => {
    let live = true;
    sweepApi.rows(study.tableId, page * PAGE, PAGE, sort?.c, sort?.desc).then((r) => live && setData(r)).catch(() => {});
    return () => { live = false; };
  }, [study.tableId, study.rows, page, sort]);
  const role = new Map(study.columns.map((c) => [c.name, study.question.removed.includes(c.name) ? "ignore" : c.role]));
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
        <ColumnPicker options={rawOptions(t, study, data.columns)} value={shownNames} onChange={setPicked}
          presets={presetChoices(t, study, data.columns, PRESET_KEY, ["params-goal"])} />
      </div>
      <div className="sw-table-wrap">
        <table className="sw-table">
          <thead><tr>{show.map((j) => data.columns[j]).map((c) => (
            <th key={c} className={`sw-th-${role.get(c) ?? "output"}`} onClick={() => setSort(sort?.c === c ? { c, desc: !sort.desc } : { c, desc: false })}>
              {c}{sort?.c === c ? (sort.desc ? " ▼" : " ▲") : ""}</th>
          ))}</tr></thead>
          <tbody>{data.rows.map((r, i) => (
            <tr key={i}>{show.map((j) => [r[j], j] as const).map(([v, j]) => <td key={j} className={`${typeof v === "number" ? "num" : ""}${role.get(data.columns[j]) === "ignore" ? " sw-dim" : ""}`}>
              {v === null ? "–" : typeof v === "number" ? fmtValue(v) : String(v)}</td>)}</tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}

/** Every run as a line - the raw results, before roles or goals - with its own filters and colour;
 *  "Export the plot" writes it alone as an interactive page. */
export function RawPlot({ study }: { study: Study }) {
  const t = useT();
  const [cols, setCols] = useState<Map<string, Col> | null>(null);
  const [n, setN] = useState(0);
  const [axes, setAxes] = useState<string[]>([]);
  const [filters, setFilters] = useState<Record<string, Filter>>({});
  const [colorBy, setColorBy] = useState<string | null>(null);
  const [scales, setScales] = useState<Record<string, Scale>>({});
  const [reversed, setReversed] = useState<Record<string, boolean>>({});
  const [menu, setMenu] = useState<{ name: string; at: DOMRect } | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let live = true;
    sweepApi.raw(study.tableId).then((r) => {
      if (!live) return;
      const m = new Map(r.columns.map((w) => { const c = decodeCol(w, "run"); return [c.name, c] as [string, Col]; }));
      setCols(m); setN(r.n);
      const removed = new Set(study.question.removed);
      const useful = study.columns.filter((c) => !c.constant && !c.empty && c.role !== "id" && !removed.has(c.name)).map((c) => c.name);
      setAxes(useful.slice(0, 12));
    }).catch((e) => live && setErr((e as Error).message));
    return () => { live = false; };
  }, [study.tableId, study.rows, study.columns, study.question.removed]);
  const shown = useMemo(() => { if (!cols) return 0; const m = keptMask(cols, filters, n); let k = 0; for (let i = 0; i < n; i++) k += m[i]; return k; }, [cols, filters, n]);
  if (!cols) return <p className="hint">{err || t("swReading")}</p>;
  const scaleOf = (a: string) => scales[a] ?? study.columns.find((c) => c.name === a)?.scale ?? "linear";
  const exportPlot = async () => {
    const p = await pickPath({ mode: "save", title: t("swExportPlot"), exts: [".html"], defaultName: study.name.replace(/\.[^.]+$/, "") + "_plot.html" });
    if (!p) return;
    try {
      const r = await sweepApi.report(study.tableId, { roles: {}, combine: "and", holdValues: {}, goal: null, conditions: [], derived: [], outputAgg: {}, objectives: [], exclude: [] },
        { format: "plot", raw: true, path: p, axes, title: study.name, labels: { "#shown": t("swShown", { n: "{n}", of: "{of}" }), "#clear": t("swRepClear"), "#hint": t("swRepHtmlHint"), "#colour": t("swColourByThis") } });
      notify(t("swSaved", { path: r.path }));
      useSweeps.getState().journal("export", { path: r.path });
    } catch (e) { notifyError(e); }
  };
  return (
    <>
      <div className="sw-plotbar">
        <ColumnPicker options={rawOptions(t, study, [...cols.keys()])} value={axes} onChange={setAxes}
          presets={presetChoices(t, study, [...cols.keys()], PRESET_KEY, ["params-goal"])} />
        <span className="hint">{colorBy ? `${t("swColourBy")}: ${colorBy}` : t("swRawColourHint")}</span>
        <span className="hint sw-count">{t("swShown", { n: shown.toLocaleString(), of: n.toLocaleString() })}</span>
        {Object.keys(filters).length > 0 && <button className="btn outline" onClick={() => setFilters({})}>{t("swClearFilters", { n: Object.keys(filters).length })}</button>}
        <button className="btn outline" onClick={exportPlot} title={t("swExportPlotHint")}>{t("swExportPlot")}</button>
      </div>
      <ParallelPlot sliderLabel={(a, b, n) => t("swAxesOnScreen", { a, b, n })} cols={cols} n={n} axes={axes} scaleOf={scaleOf} reversed={reversed} colorBy={colorBy} filters={filters} highlight={null}
        labelOf={(a) => a} onPick={() => {}} onFilter={(a, f) => { const x = { ...filters }; if (f) x[a] = f; else delete x[a]; setFilters(x); }}
        onAxisMenu={(name, at) => setMenu({ name, at })}
        onMoveAxis={(name, to) => { const a = axes.filter((x) => x !== name); a.splice(to, 0, name); setAxes(a); }} height={460} />
      {menu && cols.get(menu.name) && (
        <AxisMenu col={cols.get(menu.name)!} label={menu.name} at={menu.at} scale={scaleOf(menu.name)} reversed={!!reversed[menu.name]}
          filter={filters[menu.name]} colouring={colorBy === menu.name}
          onScale={(s) => setScales({ ...scales, [menu.name]: s })} onReverse={() => setReversed({ ...reversed, [menu.name]: !reversed[menu.name] })}
          onColour={() => setColorBy(colorBy === menu.name ? null : menu.name)} onHide={() => { setAxes(axes.filter((a) => a !== menu.name)); setMenu(null); }}
          onFilter={(f) => { const x = { ...filters }; if (f) x[menu.name] = f; else delete x[menu.name]; setFilters(x); }} onClose={() => setMenu(null)} />
      )}
    </>
  );
}

/** The raw table's columns for the picker, grouped by their role (a column taken out: Not used). */
function rawOptions(t: TFn, s: Study, names: string[]) {
  const removed = new Set(s.question.removed);
  const role = new Map(s.columns.map((c) => [c.name, removed.has(c.name) ? "ignore" as const : c.role]));
  return names.map((n) => ({ id: n, label: n, group: groupLabel(t, role.get(n) ?? "ignore") }));
}
