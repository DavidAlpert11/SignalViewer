/* What the plot and the table show for a study: the columns of the current mode, their names on
   screen, their scales, and which axes can be added. Pure functions of the study. */
import type { TFn } from "../i18n";
import type { Col, Scale } from "./model";
import type { Study } from "./state";

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
    if (c.name === "#set") continue;
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
