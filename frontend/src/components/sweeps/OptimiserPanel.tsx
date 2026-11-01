/* MF07: an optimiser in the loop - each generation of sets is run with the run step, the next one
   chosen from the results; the goal (or two or three objectives) and its conditions are what it
   optimises. Chosen by the problem (several objectives: NSGA-II; few runs: model-assisted; else
   differential evolution), or by hand. Watched with the run monitor; when it ends, the sets it ran
   are a group "Optimiser n" and the results are merged into the study. */
import { useState } from "react";
import { useT, type TKey } from "../../i18n";
import { sweepApi, type DoeSpec } from "../../sweeps/api";
import { idOfParams } from "../../sweeps/groups";
import { notify, notifyError } from "../../sweeps/notify";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import { rowsOf, type Row } from "./DoeSheet";
import NumField from "./NumField";
import { defaultStep, Monitor } from "./RunStepPanel";

const METHODS = ["auto", "nsga2", "de", "surrogate"] as const;
const KEY: Record<(typeof METHODS)[number], TKey> = { auto: "swOptAuto", nsga2: "swOptNsga2", de: "swOptDe", surrogate: "swOptSurrogate" };
const jobOf = new Map<string, string>();

export default function OptimiserPanel({ study }: { study: Study }) {
  const t = useT();
  const q = study.question;
  const [rows, setRows] = useState<Row[]>(() => rowsOf(study));
  const [method, setMethod] = useState<(typeof METHODS)[number]>("auto");
  const varied = rows.filter((r) => r.on).length;
  const [budget, setBudget] = useState(Math.max(40, 20 * varied));
  const [combos, setCombos] = useState(true);
  const [job, setJob] = useState<string | null>(() => jobOf.get(study.tableId) ?? null);
  const [info, setInfo] = useState("");
  const objs = q.objectives.length >= 2 ? q.objectives.map((o) => `${o.direction === "max" ? "↑" : "↓"} ${o.column}`) : q.goal ? [`${q.goal.direction === "max" ? "↑" : "↓"} ${q.goal.column}`] : [];
  const conds = q.conditions.filter((c) => !c.in && c.op !== "==" && c.op !== "!=").length;
  const specs = (): DoeSpec[] => rows.map((r) => (r.on ? r.spec : { name: r.spec.name, kind: "fixed", value: r.fixed }));
  const start = async () => {
    try {
      const r = await sweepApi.optimiseStart(study.tableId, wireQuestion(study), specs(), method, budget, combos, study.view.runStep ?? defaultStep(study));
      jobOf.set(study.tableId, r.id);
      setJob(r.id);
      setInfo(t("swOptStarted", { m: t(KEY[(r.method as (typeof METHODS)[number])] ?? "swOptAuto"), p: r.pop }));
    } catch (e) { notifyError(e); }
  };
  const groupOf = (done: Record<string, string | number | null>[]) => {
    const order = study.answer!.sets.filter((c) => c.group === "param").map((c) => c.name);
    const ids = [...new Set(done.map((r) => idOfParams(Object.fromEntries(order.map((k) => [k, r[k] ?? null])), order)))];
    if (!ids.length) return;
    const st = useSweeps.getState();
    const s = st.studies[st.active];
    const gs = s.view.groups ?? [];
    let color = 0;
    while (gs.some((g) => g.color === color)) color++;
    const n = gs.filter((g) => g.source === "rerun" && g.name.startsWith(t("swOptGroup", { n: "" }).trim())).length + 1;
    st.setView({ groups: [...gs, { id: `g${Date.now().toString(36)}o`, name: t("swOptGroup", { n }), color, source: "rerun", frozen: true, ids }] });
    notify(t("swOptGroupSaved", { n: ids.length }));
  };
  return (
    <section className="sw-optimiser" aria-label={t("swOptTitle")}>
      <h3>{t("swOptTitle")}</h3>
      <p className="hint">{objs.length ? t("swOptWhat", { o: objs.join(", "), c: conds }) : t("swOptNoGoal")}</p>
      <div className="sw-row sw-doe-controls">
        <span className="hint">{t("swOptVaried", { n: varied, of: rows.length })}</span>
        <details><summary>{t("swOptParams")}</summary>
          {rows.map((r, i) => <label key={r.spec.name} className="acheck"><input type="checkbox" checked={r.on}
            onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, on: e.target.checked } : x)))} />{r.spec.name}</label>)}
          <p className="hint">{t("swOptParamsHint")}</p>
        </details>
        <label>{t("swDoeMethod")} <select aria-label={t("swOptMethod")} value={method} onChange={(e) => setMethod(e.target.value as (typeof METHODS)[number])}>
          {METHODS.map((m) => <option key={m} value={m}>{t(KEY[m])}</option>)}</select></label>
        <label>{t("swOptBudget")} <NumField value={budget} lo={4} hi={2000} label={t("swOptBudget")} onChange={(x) => setBudget(Math.max(4, Math.min(5000, Math.round(x))))} /></label>
        <label className="acheck"><input type="checkbox" checked={combos} onChange={(e) => setCombos(e.target.checked)} />{t("swDoeCombos", { n: study.answer!.counts.combos })}</label>
        <button className="btn primary" disabled={!objs.length || !varied || !study.view.runStep} onClick={start}
          title={!study.view.runStep ? t("swOptNeedsStep") : undefined}>{t("swOptStart")}</button>
      </div>
      {!study.view.runStep && <p className="hint">{t("swOptNeedsStep")}</p>}
      {info && <p className="hint">{info}</p>}
      {job && <Monitor study={study} job={job} onDone={groupOf} />}
    </section>
  );
}
