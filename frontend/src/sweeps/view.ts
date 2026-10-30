/* What the plot and the table show for a study: the columns of the current mode, their names on
   screen, their scales, and which axes can be added. Pure functions of the study. */
import type { TFn } from "../i18n";
import type { Col, Scale } from "./model";
import { wireQuestion, type Study } from "./state";

/** The columns the plot draws: one entry per parameter set, or per run. */
export function modeColumns(s: Study): { cols: Map<string, Col>; n: number } {
  const a = s.answer;
  if (!a) return { cols: new Map(), n: 0 };
  const list = s.view.mode === "runs" && a.runs ? a.runs.columns : a.sets;
  return { cols: new Map(list.map((c) => [c.name, c])), n: list[0]?.values.length ?? 0 };
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
