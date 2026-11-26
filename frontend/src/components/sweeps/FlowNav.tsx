/* PLAN 2026-11-16 §7a: the one stepper of every study - 1 Data · 2 Columns · 3 Goal · 4 Results · 5 Next runs -
   above a table and above a study file alike (sweeps/flow.ts reads the step from both). Each step says where it
   stands; a step with nothing to show yet (Columns without a table) says what opens it. It replaced the table's
   four steps (StepNav) and the study file's navigator items (Set up, Together) and its Run column. */
import { fmtInt, useT, type TFn, type TKey } from "../../i18n";
import { useApp } from "../../store";
import { flowGo, flowStep, flowSteps, type FlowAt, type FlowStep } from "../../sweeps/flow";
import { goFlow } from "../../sweeps/goFlow";
import { isRecordings, useSweeps, type Study } from "../../sweeps/state";
import { hasGoal, readiness, setupDone } from "../../sweeps/setup";
import { rerunCount } from "../../sweeps/split";
import { useLeftHidden, useNarrow } from "../../sweeps/narrow";
import type { StudyPanelState } from "../../sweeps/studyStore";
import { Icon } from "../../icons";

const baseName = (p: string) => p.replace(/[\\/]+$/, "").split(/[\\/]/).pop() ?? p;
const stem = (n: string) => n.replace(/\.(svstudy\.json|svsweep|[^.]+)$/, "");

/** UX5.3: the study's name - the head of the area's page, as a workspace's title in Recordings */
export function useStudyName(): string {
  const t = useT();
  const common = useSweeps((s) => s.common);
  const study = useSweeps((s) => s.studies[s.active]);
  return common.open ? (common.study?.name || stem(baseName(common.path)) || t("nsTitle")) : study ? stem(study.name) : "";
}

const TITLE: Record<FlowStep, TKey> = { data: "swStepData", columns: "swStepColumns", goal: "swStepGoal", results: "swStepResults", next: "swCenterNext" };
export const flowTitle = (t: TFn, s: FlowStep) => t(TITLE[s]);
export { goFlow };

/** The step shown now. */
export function useFlowStep(): FlowStep {
  const part = useSweeps((s) => s.part);
  const step = useSweeps((s) => s.studies[s.active]?.view.step);
  const center = useSweeps((s) => s.studies[s.active]?.view.center);
  const common = useSweeps((s) => s.common.open);
  const systems = useSweeps((s) => s.common.study?.tables.length ?? 0);
  return flowStep({ part, table: step ? { step, center: center ?? "lines" } : null, common, systems });
}

/** A step that works on a table, none open: a study that has tables names them; else one is needed. */
const noTable = (t: TFn, cs: StudyPanelState["study"] | null): string =>
  cs?.tables.length ? t("flOpenOne", { n: cs.tables.length }) : t("flNeedsTable");

/** One line under each step's name: what it holds now. */
function status(t: TFn, lang: "en" | "he", s: Study | undefined, c: StudyPanelState, step: FlowStep, rec: boolean): string {
  const cs = c.open ? c.study : null;
  switch (step) {
    case "data":
      if (s) return t(rec ? "swStRawRec" : "swStRaw", { rows: s.rows.toLocaleString(), cols: s.columns.length });
      return cs ? t("flDefined", { n: setupDone(cs, !!c.guess).filter(Boolean).length }) : "";
    // FR6: a study with tables, none open yet, is not "needs a table": it says to open one of them
    case "columns": return s ? t("swStRoles", { p: s.summary.params.length, h: s.summary.holds.length, o: s.summary.outputs.length }) : noTable(t, cs);
    case "goal": if (rec && s) return t(s.question.conditions.length === 1 ? "swStLimit1" : "swStLimits", { c: s.question.conditions.length });
      if (!s) return noTable(t, cs);
      // CC19: "1 limit", not "1 limits"
      return s ? t(s.question.conditions.length === 1 ? "swStGoal1" : "swStGoal", { c: s.question.conditions.length, o: (s.question.goals[s.question.active]?.optimize ?? []).length }) : t("flNeedsTable");
    case "results":
      if (s && rec) return t(s.question.conditions.length && s.answer ? "rcStResults" : "swStRecordings", { n: s.answer?.counts.holding ?? 0, of: s.answer?.counts.sets ?? s.rows });
      if (s) return !s.answer ? "…" : s.question.conditions.length ? t("swStResults", { n: s.answer.counts.holding, of: s.answer.counts.sets })
        : t("swStNoGoal", { of: s.answer.counts.sets });
      return cs && cs.tables.length > 1 ? t("flSystems", { n: cs.tables.length }) : t("flNeedsTable");
    case "next": {
      const k = c.loopProgress?.round ?? c.demoProgress?.round ?? cs?.history?.length ?? 0;
      if (cs && !c.demo && readiness(cs).missing.length && !k) return t("flNotReady");
      if (cs && !c.demo && k && !hasGoal(cs)) return t("flNeedsGoal");          // SF1: the loop asks for it here
      const n = s ? rerunCount(s) : 0;
      return [k ? t("flRounds", { k: fmtInt(k, lang) }) : "", n ? t("flRerun", { n }) : ""].filter(Boolean).join(" · ") || t("flPropose");
    }
  }
}

export default function FlowNav() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const cur = useFlowStep();
  const study = useSweeps((s) => s.studies[s.active]);
  const common = useSweeps((s) => s.common);
  const narrow = useNarrow();
  const hidden = useLeftHidden();
  const at: FlowAt = { part: useSweeps.getState().part, table: study ? { step: study.view.step, center: study.view.center } : null, common: common.open,
    systems: common.study?.tables.length ?? 0 };
  // the steps of a table have a side panel to fold (Data's tables list and Next runs' settings are their own)
  const panel = !!study && (cur === "columns" || cur === "goal" || (cur === "results" && useSweeps.getState().part !== "together"));
  const toggle = () => (narrow ? useSweeps.setState({ narrowOpen: hidden }) : useSweeps.getState().setLeftHidden(!hidden));
  const rec = useSweeps(isRecordings);
  const steps = flowSteps(rec);
  const ci = steps.indexOf(cur);
  const name = useStudyName();
  // UX5.3: the area's page head (shell/PanelFrame.tsx's anatomy): its title where a page has its own, then the steps
  return (
    <nav className="sw-steps page-head" aria-label={t("swSteps")}>
      {name && <h2 className="page-title sw-page-title" title={name}><Icon.Table aria-hidden="true" /><span className="sw-ellipsis">{name}</span></h2>}
      {panel && <button className="iconbtn sw-panel-toggle" aria-pressed={!hidden} onClick={toggle}
        title={t(hidden ? "swShowPanel" : "swHidePanel")} aria-label={t(hidden ? "swShowPanel" : "swHidePanel")}>{hidden ? "›" : "‹"}</button>}
      {steps.map((s, i) => {
        const open = s === cur || !!flowGo(at, s);
        return (
          <button key={s} data-step={s === "data" ? "raw" : s === "columns" ? "roles" : s === "goal" ? "goals" : s} data-flow={s}
            className={`sw-step-btn${s === cur ? " on" : ""}${ci > i ? " done" : ""}`} aria-current={s === cur ? "step" : undefined}
            disabled={!open} title={open ? undefined : t(common.study?.tables.length ? "flOpenOneHint" : "flNeedsTableHint")} onClick={() => goFlow(s)}>
            <span className="sw-step-n">{i + 1}</span>
            <span className="sw-step-txt"><b>{flowTitle(t, s)}</b><span>{status(t, lang, study, common, s, rec)}</span></span>
          </button>
        );
      })}
    </nav>
  );
}
