/* What the plot and the table show for a study: the columns of the current mode, their names on
   screen, their scales, and which axes can be added. Pure functions of the study. */
import type { TFn, TKey } from "../i18n";
import type { Col, MapSpec, Role, Scale } from "./model";
import { wireQuestion, type Study } from "./state";
import { keptMask } from "./filters";

/** The columns the plot draws: one entry per parameter set, or per run. */
export function modeColumns(s: Study): { cols: Map<string, Col>; n: number } {
  const a = s.answer;
  if (!a) return { cols: new Map(), n: 0 };
  const list = s.view.mode === "runs" && a.runs ? a.runs.columns : a.sets;
  return { cols: new Map(list.map((c) => [c.name, c])), n: list[0]?.values.length ?? 0 };
}

/** The table's columns of a role that the question uses: a column taken out in *Clean columns* is
 *  not one (the server sees it as not used). */
export const activeColumns = (s: Study, role: "param" | "hold" | "output") => {
  const removed = new Set(s.question.removed);
  return s.columns.filter((c) => c.role === role && !removed.has(c.name)).map((c) => c.name);
};
export const activeParams = (s: Study) => activeColumns(s, "param");

/** Two parameters of a map, checked: the chosen ones while they are parameters of the question,
 *  else the first ones that are. */
function pairOf(params: string[], wx?: string | null, wy?: string | null): { x: string | undefined; y: string | undefined } {
  const x = wx && params.includes(wx) ? wx : params[0];
  const y = wy && params.includes(wy) && wy !== x ? wy : params.find((p) => p !== x);
  return { x, y };
}

/** The maps on screen, checked (S05): the study's list, or one map of mapX / mapY (older studies).
 *  Empty with fewer than two parameters. One answer for the maps, next runs' marks and the report. */
export function mapList(s: Study): MapSpec[] {
  const params = activeParams(s);
  if (params.length < 2) return [];
  const want = s.view.maps?.length ? s.view.maps : [{ x: s.view.mapX ?? "", y: s.view.mapY ?? "", rest: "all" as const }];
  return want.map((m) => { const p = pairOf(params, m.x, m.y); return { x: p.x!, y: p.y!, rest: m.rest ?? "all" }; });
}

/** The first map's two parameters (and the parameters there are). */
export function mapAxes(s: Study): { x: string | undefined; y: string | undefined; params: string[] } {
  const params = activeParams(s);
  return { ...pairOf(params, s.view.maps?.[0]?.x ?? s.view.mapX, s.view.maps?.[0]?.y ?? s.view.mapY), params };
}

/** A pair of parameters not on any map yet, for "+ map" (or the first pair again). */
export function nextMapPair(s: Study): MapSpec | null {
  const params = activeParams(s), used = new Set(mapList(s).map((m) => `${m.x}|${m.y}`));
  for (let i = 0; i < params.length; i++)
    for (let j = 0; j < params.length; j++)
      if (i !== j && !used.has(`${params[i]}|${params[j]}`) && !used.has(`${params[j]}|${params[i]}`)) return { x: params[i], y: params[j], rest: "all" };
  return params.length >= 2 ? { x: params[0], y: params[1], rest: "all" } : null;
}

/** The sets' columns (the table, the detail). */
export const setColumns = (s: Study) => new Map((s.answer?.sets ?? []).map((c) => [c.name, c]));

export function colLabel(t: TFn, s: Study, name: string): string {
  const c = s.answer?.sets.find((x) => x.name === name);
  if (name === "#goal") {
    const g = s.question.goal;
    return g ? t(g.direction === "max" ? "swGoalLabelMax" : "swGoalLabelMin", { c: g.column }) : t("swGoal");
  }
  if (name === "#holds") return t("swHoldsCol");
  if (name === "#rank") return t("swRankCol");
  if (name === "#covered") return t("swCoveredCol");
  if (name === "#complete") return t("swCompleteCol");
  if (name === "#set") return t("swSetCol");
  if (name === "#pareto") return t("swParetoCol");
  if (name === "#score") return t("swScoreCol");
  if (name === "#neighbours") return t("swNeighboursCol");
  if (name === "#tolerance") return t("swToleranceCol");
  if (name === "#partial") return t("swPartialCol");
  if (c?.group === "condition" && c.label) return `${c.label} · ${t(c.part === "worst" ? "swWorst" : c.part === "margin" ? "swMargin" : "swPassed")}`;
  if (c?.group === "output" && c.agg && s.view.mode === "sets") return `${name} · ${c.agg}`;
  return name;
}

export function scaleOf(s: Study, name: string, col?: Col): Scale {
  const tc = s.columns.find((c) => c.name === name);
  if (s.view.scales[name]) return s.view.scales[name];
  // an output per set is a mean / worst case: no longer the few values of the table column
  if (tc && s.view.mode === "sets" && tc.role === "output" && (tc.scale === "category" || tc.scale === "ordinal")) return "linear";
  if (tc) return tc.scale;
  if (col?.kind === "cat") return "category";
  if (name === "#holds" || name === "#complete" || name === "#pareto" || name === "#partial") return "category";
  return "linear";
}

/** Columns that can be an axis (and a colour) in the current mode; what tells nothing is left out
 *  when the view says so. */
export function axisChoices(s: Study): string[] {
  const { cols } = modeColumns(s);
  const out: string[] = [];
  for (const c of cols.values()) {
    if (c.name === "#set" || c.name === "#row") continue;
    const meta = s.answer?.sets.find((x) => x.name === c.name);
    if (s.view.hideConstant && meta?.constant) continue;
    if (s.view.hideFlat && meta?.flat) continue;
    out.push(c.name);
  }
  return out;
}

/** The shown axes that exist in the current mode. */
export function shownAxes(s: Study): string[] {
  const { cols } = modeColumns(s);
  const ok = new Set(axisChoices(s));
  return s.view.axes.filter((a) => cols.has(a) && ok.has(a));
}

/** What a set number means: the parameter sets of these roles, kept values, new columns and left-out runs. */
export function scopeKey(s: Study): string {
  const q = wireQuestion(s);
  return JSON.stringify([q.roles, q.holdValues, q.derived, q.exclude]);
}

/** 1 for each parameter set the keep / exclude steps leave on screen; null when there are none. */
export function scopeMask(s: Study): Uint8Array | null {
  const sc = s.view.scope;
  const n = s.answer?.sets[0]?.values.length ?? 0;
  if (!sc.steps.length || sc.key !== scopeKey(s) || !n) return null;
  const m = new Uint8Array(n).fill(1);
  for (const st of sc.steps) {
    const on = new Set(st.sets);
    for (let i = 0; i < n; i++) if (m[i] && (st.kind === "keep" ? !on.has(i) : on.has(i))) m[i] = 0;
  }
  return m;
}

/** The current mode's columns with only what the keep / exclude steps leave (axes rescale to it, as
 *  in HiPlot); `index` maps a row back to its row in the full columns. */
export function scopedColumns(s: Study): { cols: Map<string, Col>; n: number; index: Int32Array | null } {
  const { cols, n } = modeColumns(s);
  const m = scopeMask(s);
  if (!m) return { cols, n, index: null };
  const setOf = s.view.mode === "runs" ? cols.get("#set")?.values : null;
  const idx: number[] = [];
  for (let i = 0; i < n; i++) if (m[setOf ? setOf[i] : i]) idx.push(i);
  const index = Int32Array.from(idx);
  const out = new Map<string, Col>();
  for (const [k, c] of cols) { const v = new Float32Array(index.length); for (let j = 0; j < index.length; j++) v[j] = c.values[index[j]]; out.set(k, { ...c, values: v }); }
  return { cols: out, n: index.length, index };
}

/** Which columns to show, at once: every one, or a group by role. */
export type ColumnPreset = "all" | "params-outputs" | "params-goal" | "params" | "scenarios" | "outputs";
export const PRESETS: ColumnPreset[] = ["all", "params-outputs", "params-goal", "params", "scenarios", "outputs"];

/** The columns of a group, in table order, among `available` (what the current view can show). */
export function presetColumns(s: Study, preset: ColumnPreset, available: string[]): string[] {
  const role = (r: "param" | "hold" | "output") => activeColumns(s, r);
  const derived = s.question.derived.map((d) => d.name);
  const goalCols = ["#goal", ...(s.answer?.sets.filter((c) => c.group === "condition" && c.part === "worst").map((c) => c.name) ?? [])];
  const want = preset === "all" ? [...role("hold"), ...role("param"), ...role("output"), ...derived, "#goal"]
    : preset === "params-outputs" ? [...role("param"), ...role("output"), ...derived]
    : preset === "params-goal" ? [...role("param"), ...goalCols]
    : preset === "params" ? role("param")
    : preset === "scenarios" ? role("hold")
    : [...role("output"), ...derived];
  const ok = new Set(available);
  return want.filter((c, i) => ok.has(c) && want.indexOf(c) === i);
}

/** A column's group in the column picker: its role, a new column, or part of the answer. */
export function groupLabel(t: TFn, group: Col["group"] | Role): string {
  return group === "param" ? t("swRoleParam") : group === "hold" ? t("swRoleHold") : group === "output" ? t("swRoleOutput")
    : group === "derived" ? t("swNewColumns") : group === "id" ? t("swRoleId") : group === "recording" ? t("swRoleRecording")
    : group === "ignore" ? t("swRoleIgnore") : t("swGroupAnswer");
}

/** The column picker's choices for the plot of the results: what can be an axis now, by group. */
export function axisOptions(t: TFn, s: Study): { id: string; label: string; group: string }[] {
  const { cols } = modeColumns(s);
  const role = new Map(s.columns.map((c) => [c.name, c.role]));
  return axisChoices(s).map((name) => {
    const g = cols.get(name)?.group;
    // in the runs mode a table column comes back as "run": its role says more
    const group = g && g !== "run" ? g : role.get(name) ?? "derived";
    return { id: name, label: colLabel(t, s, name), group: groupLabel(t, group) };
  });
}

/** The groups as one-click choices of the picker (Show columns: all, parameters, outputs...). */
export function presetChoices(t: TFn, s: Study, available: string[], keys: Record<ColumnPreset, TKey>, skip: ColumnPreset[] = []) {
  return PRESETS.filter((p) => !skip.includes(p)).map((p) => ({ label: t(keys[p]), ids: presetColumns(s, p, available) })).filter((p) => p.ids.length);
}

/* ------------------------------------------------------------------ the table of sets
   One answer for the table on screen, its export and the report's table: which sets, in which
   order, with which columns. */

/** always in the table, kept in view when it scrolls (SetsTable draws them itself) */
export const TABLE_FIXED = ["#rank", "#holds"];
const NOT_IN_TABLE = new Set(["#set", "#row", ...TABLE_FIXED]);

/** The columns a table starts with: the parameters, the goal, each condition's worst case and
 *  margin, the scores there are, and how many combinations ran. */
export function defaultTableColumns(s: Study): string[] {
  const sets = s.answer?.sets ?? [];
  const have = new Set(sets.map((c) => c.name));
  return [...sets.filter((c) => c.group === "param").map((c) => c.name), ...(have.has("#goal") ? ["#goal"] : []),
    ...sets.filter((c) => c.group === "condition" && c.part !== "passed").map((c) => c.name),
    ...["#score", "#pareto", "#neighbours", "#tolerance", "#covered"].filter((x) => have.has(x))];
}

/** The table's columns now: the chosen ones that this answer has, else the default. */
export function tableColumns(s: Study): string[] {
  const have = new Set((s.answer?.sets ?? []).map((c) => c.name));
  const chosen = s.view.tableColumns?.filter((c) => have.has(c) && !NOT_IN_TABLE.has(c));
  return chosen?.length ? chosen : defaultTableColumns(s);
}

/** Every column the table can show, for the picker. */
export function tableOptions(t: TFn, s: Study): { id: string; label: string; group: string }[] {
  return (s.answer?.sets ?? []).filter((c) => !NOT_IN_TABLE.has(c.name))
    .map((c) => ({ id: c.name, label: colLabel(t, s, c.name), group: groupLabel(t, c.group) }));
}

/** The sets the table shows, in its order: kept by the plot's filters, the keep / exclude steps and
 *  "only those that hold"; sorted by the chosen column, else best first (rank, holds, the goal). */
export function tableRows(s: Study): number[] {
  const a = s.answer;
  const cols = setColumns(s);
  const n = a?.sets[0]?.values.length ?? 0;
  if (!a || !n) return [];
  const kept = keptMask(cols, s.view.filters, n);
  const scope = scopeMask(s);
  const holds = cols.get("#holds")!.values;
  const rows: number[] = [];
  for (let i = 0; i < n; i++) if (kept[i] && (!scope || scope[i]) && (!s.view.onlyHolding || holds[i] === 1)) rows.push(i);
  const sort = s.view.tableSort, sc = sort ? cols.get(sort.column) : undefined;
  if (sort && sc) {
    const v = sc.values, lab = sc.kind === "cat" ? sc.labels ?? [] : null, dir = sort.desc ? -1 : 1;
    rows.sort((x, y) => {
      const fx = Number.isFinite(v[x]), fy = Number.isFinite(v[y]);
      if (fx !== fy) return fx ? -1 : 1;                                    // no value: last, either way
      if (!fx) return x - y;
      const d = lab ? String(lab[v[x]] ?? "").localeCompare(String(lab[v[y]] ?? ""), undefined, { numeric: true }) : v[x] - v[y];
      return d ? dir * d : x - y;
    });
    return rows;
  }
  const rank = cols.get("#rank")!.values, goal = cols.get("#goal")?.values;
  const g = s.question.goal?.direction === "min" ? 1 : -1;
  return rows.sort((x, y) => {
    const rx = Number.isFinite(rank[x]) ? rank[x] : Infinity, ry = Number.isFinite(rank[y]) ? rank[y] : Infinity;
    if (rx !== ry) return rx - ry;
    if (holds[x] !== holds[y]) return holds[y] - holds[x];
    if (goal) { const gx = goal[x], gy = goal[y]; if (gx !== gy) return Number.isFinite(gx) ? (Number.isFinite(gy) ? g * (gx - gy) : -1) : 1; }
    return x - y;
  });
}
