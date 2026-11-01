/* Maps of two parameters, as many as wanted (S05): in each cell the share of sets that hold
   (colour) and the best goal among them (number). The other parameters: every value (the share is
   over all of them) or a slice through the best set (they stay at its values). A line marks where
   holding begins - between a cell where some set holds and a neighbour where none does. A click on
   a cell keeps its sets on the axes of the lines. Optional marks on top (next runs' suggestions). */
import { useEffect, useState } from "react";
import { useApp } from "../../store";
import { useT, type TFn } from "../../i18n";
import { rampCssOf, rampOf, type Cmap } from "../../sweeps/colors";
import StyleMenu from "./StyleMenu";
import { sweepApi, type PairMap } from "../../sweeps/api";
import type { Filter, MapSpec } from "../../sweeps/model";
import { fmtValue } from "../../sweeps/scales";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import { activeParams, mapList, nextMapPair, setColumns, styleOf } from "../../sweeps/view";
import { MARK } from "../../sweeps/next";

/** a suggestion: where it is, why, and the parameter it moves (when one) */
export interface Mark { params: Record<string, number | string | null>; kind: string; param?: string }
type MapAnswer = PairMap & { rest: "all" | "best"; fixed: Record<string, number | string | null> | null;
  goal: boolean; direction: "max" | "min"; bestAt: [number, number] | null };
type MapColor = "share" | "goal";

export default function MapsView({ study, marks }: { study: Study; marks?: Mark[] }) {
  const t = useT();
  const maps = mapList(study);
  if (activeParams(study).length < 2) return <p className="hint">{t("swMapNeedsTwo")}</p>;
  const setMaps = (m: MapSpec[]) => useSweeps.getState().setView({ maps: m });
  const add = () => { const n = nextMapPair(study); if (n) setMaps([...maps, n]); };
  return (
    <div className="sw-maps">
      <div className="sw-row"><span className="sw-edge-key" /> <span className="hint">{t("swMapEdgeKey")}</span>
        <span className="hint">★ {t("swMapBestSet")}</span>
        <span className="sw-add-map" /><StyleMenu study={study} parts={["cmap", "numbers"]} />
        <button className="btn outline" onClick={add}>{t("swAddMap")}</button></div>
      <div className="sw-maps-grid">
        {maps.map((m, i) => (
          <MapPanel key={`${i}:${m.x}:${m.y}:${m.rest}`} study={study} spec={m} marks={marks}
            onChange={(p) => setMaps(maps.map((x, j) => (j === i ? { ...x, ...p } : x)))}
            onRemove={maps.length > 1 ? () => setMaps(maps.filter((_, j) => j !== i)) : undefined} />
        ))}
      </div>
    </div>
  );
}

export function MapPanel({ study, spec, marks, onChange, onRemove }: {
  study: Study; spec: MapSpec; marks?: Mark[]; onChange: (p: Partial<MapSpec>) => void; onRemove?: () => void;
}) {
  const t = useT();
  const params = activeParams(study);
  const { x, y } = spec;
  const rest = spec.rest ?? "all";
  // coloured by the goal when there is one and nothing else to show (no condition: every set holds)
  const goal = study.question.goal?.column;
  const conds = study.question.conditions.length > 0;
  const color: MapColor = goal ? spec.color ?? (conds ? "share" : "goal") : "share";
  const [m, setM] = useState<MapAnswer | null>(null);
  const [err, setErr] = useState("");
  const qk = JSON.stringify(wireQuestion(study));
  useEffect(() => {
    let live = true;
    sweepApi.map(study.tableId, wireQuestion(study), x, y, rest)
      .then((r) => { if (live) { setM(r as MapAnswer); setErr(""); } }).catch((e) => live && setErr((e as Error).message));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [study.tableId, qk, x, y, rest]);
  const head = (
    <div className="sw-row sw-map-head">
      <label>{t("swMapX")} <select value={x} onChange={(e) => onChange({ x: e.target.value, y: e.target.value === y ? x : y })}>{params.map((p) => <option key={p}>{p}</option>)}</select></label>
      <label>{t("swMapY")} <select value={y} onChange={(e) => onChange({ y: e.target.value, x: e.target.value === x ? y : x })}>{params.map((p) => <option key={p}>{p}</option>)}</select></label>
      {params.length > 2 && (
        <label title={t("swMapRestHint")}>{t("swMapRest")} <select value={rest} onChange={(e) => onChange({ rest: e.target.value as MapSpec["rest"] })}>
          <option value="all">{t("swMapRestAll")}</option><option value="best">{t("swMapRestBest")}</option></select></label>
      )}
      {goal && (
        <label>{t("swMapColour")} <select value={color} onChange={(e) => onChange({ color: e.target.value as MapColor })}>
          <option value="share">{t("swMapByShare")}</option><option value="goal">{t("swMapByGoal", { c: goal })}</option></select></label>
      )}
      {onRemove && <button className="iconbtn" aria-label={t("swRemoveMap")} title={t("swRemoveMap")} onClick={onRemove}>×</button>}
    </div>
  );
  if (err) return <div className="sw-map">{head}<p className="sw-error">{err}</p></div>;
  if (!m || m.x !== x || m.y !== y) return <div className="sw-map">{head}<p className="hint">{t("swReading")}</p></div>;
  const at = m.fixed ? Object.entries(m.fixed).map(([k, v]) => `${k} = ${fmt(v)}`).join(", ") : "";
  return (
    <div className="sw-map">
      {head}
      {rest === "best" && <p className="hint sw-map-at">{m.fixed ? t("swMapAtBest", { at }) : t("swMapNoBest")}</p>}
      <MapKey t={t} m={m} color={color} goal={goal} cmap={styleOf(study).cmap} />
      <MapSvg t={t} m={m} color={color} marks={marks} style={styleOf(study)} onCell={(i, j) => keepCell(t, study, m, i, j)} />
    </div>
  );
}

const fmt = (v: unknown) => (typeof v === "number" ? fmtValue(v) : String(v));

/** A click on a cell: its sets kept on the lines' axes (x, y, and in a slice the parameters held). */
function keepCell(t: TFn, study: Study, m: MapAnswer, i: number, j: number) {
  const cols = setColumns(study);
  const want: Record<string, number | string | null> = { ...(m.fixed ?? {}), [m.x]: m.xs[i], [m.y]: m.ys[j] };
  const st = useSweeps.getState();
  const filters = { ...study.view.filters };
  for (const [name, v] of Object.entries(want)) {
    const c = cols.get(name);
    if (!c || v === null) continue;
    let f: Filter;
    if (c.kind === "cat") {
      const code = (c.labels ?? []).indexOf(String(v));
      if (code < 0) continue;
      f = { kind: "values", values: [code] };
    } else {
      const n = Number(v), eps = 1e-6 * Math.max(1, Math.abs(n));      // the plot keeps Float32 values
      f = { kind: "ranges", ranges: [[n - eps, n + eps]] };
    }
    filters[name] = f;
  }
  st.setView({ filters });
  const what = Object.entries(want).map(([k, v]) => `${k} = ${fmt(v)}`).join(", ");
  useApp.getState().toast({ kind: "info", text: t("swMapCellKept", { what }), ms: 8000,
    action: { label: t("swShowLines"), run: () => useSweeps.getState().setView({ center: "lines" }) } });
}

/** The range of the best goal over the cells (for the colour by the goal). */
function goalRange(m: MapAnswer): [number, number] | null {
  let lo = Infinity, hi = -Infinity;
  for (const r of m.best) for (const b of r) if (b !== null) { lo = Math.min(lo, b); hi = Math.max(hi, b); }
  return Number.isFinite(lo) ? [lo, hi] : null;
}

/** What the colour and the numbers of a map mean. */
function MapKey({ t, m, color, goal, cmap }: { t: TFn; m: MapAnswer; color: MapColor; goal?: string; cmap: Cmap }) {
  const r = goalRange(m);
  const byGoal = color === "goal" && r;
  return (
    <p className="hint sw-map-key">
      <span className="sw-legend-ramp" style={{ background: rampCssOf(cmap) }} />{" "}
      {byGoal ? t("swMapKeyGoal", { c: goal ?? "", worse: fmtValue(m.direction === "min" ? r![1] : r![0]), better: fmtValue(m.direction === "min" ? r![0] : r![1]) })
        : t("swMapKeyShare")}
      {m.goal ? ` · ${t("swMapKeyNumber", { c: goal ?? "" })}` : ""}
    </p>
  );
}

function MapSvg({ t, m, color, marks, style, onCell }: { t: TFn; m: MapAnswer; color: MapColor; marks?: Mark[];
  style: ReturnType<typeof styleOf>; onCell: (i: number, j: number) => void }) {
  const nx = m.xs.length, ny = m.ys.length;
  const r = color === "goal" ? goalRange(m) : null;
  const ramp = rampOf(style.cmap);
  // a cell's colour: the share that holds, or its best goal from worse (dark) to better (bright)
  const fillOf = (s: number | null, b: number | null) => {
    if (s === null) return "transparent";
    if (!r) return ramp(s);
    if (b === null) return "var(--line)";                     // nothing holds here: no goal to show
    const f = r[1] > r[0] ? (b - r[0]) / (r[1] - r[0]) : 1;
    return ramp(m.direction === "min" ? 1 - f : f);
  };
  const L = 64, B = 40, T = 8, R = 8, cw = Math.max(26, Math.min(90, 560 / nx)), ch = Math.max(22, Math.min(60, 360 / ny));
  const W = L + nx * cw + R, H = T + ny * ch + B;
  const cx = (i: number) => L + i * cw, cy = (j: number) => T + (ny - 1 - j) * ch;
  // a mark between grid values sits between the cells
  const pos = (vals: (number | string)[], v: number | string | null | undefined) => {
    if (v === null || v === undefined) return -9;
    const i = vals.indexOf(v);
    if (i >= 0) return i;
    if (typeof v !== "number") return -9;
    const nums = vals as number[];
    for (let k = 0; k < nums.length - 1; k++) if (v > nums[k] && v < nums[k + 1]) return k + (v - nums[k]) / (nums[k + 1] - nums[k]);
    return v < nums[0] ? -0.4 : nums.length - 0.6;
  };
  // where holding begins: between a cell where some set holds and a neighbour where none does
  const edges: [number, number, number, number][] = [];
  const some = (i: number, j: number) => { const s = m.share[j]?.[i]; return s === null || s === undefined ? null : s > 0; };
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    const a = some(i, j);
    if (a === null) continue;
    const r = i + 1 < nx ? some(i + 1, j) : null, u = j + 1 < ny ? some(i, j + 1) : null;
    if (r !== null && r !== a) edges.push([cx(i + 1), cy(j), cx(i + 1), cy(j) + ch]);
    if (u !== null && u !== a) edges.push([cx(i), cy(j), cx(i) + cw, cy(j)]);
  }
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: W, maxWidth: "100%" }} role="img" aria-label={t("swMapAria", { x: m.x, y: m.y })}>
      {m.share.map((row, j) => row.map((s, i) => {
        const b = m.best[j][i];
        return (
          <g key={`${i}-${j}`} className={s === null ? "" : "sw-cell"} onClick={s === null ? undefined : () => onCell(i, j)}>
            <rect x={cx(i) + 1} y={cy(j) + 1} width={cw - 2} height={ch - 2} rx={3}
              fill={fillOf(s, b)} className={s === null ? "sw-cell-empty" : ""}>
              <title>{`${m.x} ${m.xs[i]}, ${m.y} ${m.ys[j]}: ${s === null ? "–" : Math.round(s * 100) + "%"}${b !== null ? ` · ${fmtValue(b)}` : ""}${s === null ? "" : ` - ${t("swMapClickCell")}`}`}</title>
            </rect>
            {b !== null && style.numbers && cw >= 40 && <text x={cx(i) + cw / 2} y={cy(j) + ch / 2 + 4} textAnchor="middle" className="sw-cell-text">{fmtValue(b)}</text>}
          </g>
        );
      }))}
      {/* the edge twice - light under dark - so it shows on the dark and the light cells alike */}
      {edges.map(([x1, y1, x2, y2], k) => <line key={`h${k}`} x1={x1} y1={y1} x2={x2} y2={y2} className="sw-edge-halo" />)}
      {edges.map(([x1, y1, x2, y2], k) => <line key={k} x1={x1} y1={y1} x2={x2} y2={y2} className="sw-edge" />)}
      {m.bestAt && <text x={cx(m.bestAt[0]) + cw - 5} y={cy(m.bestAt[1]) + 13} textAnchor="end" className="sw-best-star">★<title>{t("swMapBestSet")}</title></text>}
      {m.xs.map((v, i) => <text key={i} x={cx(i) + cw / 2} y={H - B + 16} textAnchor="middle" className="sw-ax">{String(v)}</text>)}
      {m.ys.map((v, j) => <text key={j} x={L - 6} y={cy(j) + ch / 2 + 4} textAnchor="end" className="sw-ax">{String(v)}</text>)}
      <text x={L + (nx * cw) / 2} y={H - 4} textAnchor="middle" className="sw-ax-title">{m.x}</text>
      <text x={12} y={T + (ny * ch) / 2} textAnchor="middle" className="sw-ax-title" transform={`rotate(-90 12 ${T + (ny * ch) / 2})`}>{m.y}</text>
      {(marks ?? []).map((mk, k) => {
        const i = pos(m.xs, mk.params[m.x]), j = pos(m.ys, mk.params[m.y]);
        if (i < -1 || j < -1) return null;
        // a suggestion that moves a parameter this map does not draw sits on a cell already run: say so
        const off = !!mk.param && mk.param !== m.x && mk.param !== m.y;
        return <text key={k} x={cx(i) + cw / 2 + (off ? 9 : 0)} y={cy(j) + ch / 2 + 5 - (off ? 9 : 0)} textAnchor="middle"
          className={`sw-mark sw-mark-${mk.kind}${off ? " sw-mark-off" : ""}`}>{MARK[mk.kind] ?? "•"}{off && <title>{t("swMarkOther", { p: mk.param! })}</title>}</text>;
      })}
    </svg>
  );
}
