/* C6: the study's Set up (plan §4.3, mock-up sweeps-start.html) - what varies, the scenarios, the outputs and
   the goal, how to run. Each field is the study file's own block (sweeps/setup.ts), edited through editStudy:
   one Undo with the tables. A field is written when it is left (Enter or blur), not on every key. */
import { useState, type ReactNode } from "react";
import { useT } from "../../i18n";
import { useSweeps } from "../../sweeps/state";
import { editStudy, useStudyPanel } from "../../sweeps/studyStore";
import { firstTable, joinCommand, outputs, params, parseValues, readiness, removeParam, removeScenario, runWhere, scenarios, setGoal,
  setOutputs, setParam, setRun, setScenario, type ParamRow, type Scale } from "../../sweeps/setup";

/** A text field written when it is left; it shows the stored value again after an undo (key = the value). */
function Field({ value, onDone, label, ph, className, num }: { value: string; onDone: (v: string) => void; label: string; ph?: string; className?: string; num?: boolean }) {
  return <input key={value} className={`su-in${num ? " num" : ""}${className ? " " + className : ""}`} defaultValue={value} aria-label={label} placeholder={ph}
    dir={num ? "ltr" : undefined} onBlur={(e) => { if (e.target.value !== value) onDone(e.target.value); }}
    onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />;
}
const n = (v: string): number | null => (v.trim() === "" || !Number.isFinite(+v) ? null : +v);
const s = (v: number | null) => (v === null ? "" : String(v));

function Section({ no, title, count, children, done }: { no: number; title: string; count?: string; children: ReactNode; done: boolean }) {
  return (
    <section className="card su-sec" data-section={no} data-done={done ? "1" : "0"}>
      <div className="panel-head"><h2>{no} {title}</h2>{count && <span className="ph-count ph-actions">{count}</span>}</div>
      {children}
    </section>
  );
}

export default function SetupView() {
  const t = useT();
  const study = useStudyPanel((x) => x.study);
  const guess = useStudyPanel((x) => x.guess);
  const [adding, setAdding] = useState(0);
  const tables = useSweeps((x) => x.studies.length);
  if (!study) return null;
  const ps = params(study), sc = scenarios(study), outs = outputs(study), tb = firstTable(study), r = readiness(study);
  const where = runWhere(study);
  const fromTable = !!guess && !sc.length;              // I have results: the scenarios are the table's columns
  const edit = (f: Parameters<typeof editStudy>[0]) => editStudy(f);
  const rowEdit = (p: ParamRow, patch: Partial<ParamRow>) => edit((x) => setParam(x, p.name, { ...p, ...patch }));
  const scaleOf = (p: ParamRow, v: Scale): Partial<ParamRow> => (v === "values"
    ? { scale: v, values: [p.min, p.max].filter((x): x is number => x !== null) } : { scale: v, min: p.min ?? p.values[0] ?? null, max: p.max ?? p.values[p.values.length - 1] ?? null });
  const done = [ps.length > 0 && !r.missing.includes("range"), sc.length > 0 || fromTable, !r.missing.includes("output") && !r.missing.includes("goal"), !r.missing.includes("command")];
  return (
    <div className="su" data-part="setup" data-missing={r.missing.join(" ")}>
      <div className="su-head">
        <span className="eyebrow">{t("suTitle")} · {t("suPartOf", { n: done.filter(Boolean).length })}</span>
        <Field value={study.name ?? ""} label={t("suName")} ph={t("suNamePh")} className="su-name" onDone={(v) => edit((x) => ({ ...x, name: v }))} />
        {tables > 0 && <button className="btn outline su-to-results" onClick={() => useSweeps.setState({ part: "table" })}>{t("suContinue")}</button>}
      </div>

      <Section no={1} title={t("suVaries")} count={String(ps.length)} done={done[0]}>
        <table className="data su-params">
          <thead><tr><th>{t("suParam")}</th><th>{t("suMin")}</th><th>{t("suMax")}</th><th>{t("suStep")}</th><th>{t("suScale")}</th><th>{t("suCount")}</th><th /></tr></thead>
          <tbody>
            {ps.map((p) => (
              <tr key={p.name} data-param={p.name}>
                <td><Field value={p.name} label={t("suParam")} onDone={(v) => rowEdit(p, { name: v })} /></td>
                {p.scale === "values"
                  ? <td colSpan={3}><Field num value={p.values.join(", ")} label={t("suValues")} onDone={(v) => rowEdit(p, { values: parseValues(v).filter((x): x is number => typeof x === "number") })} /></td>
                  : <>
                    <td><Field num value={s(p.min)} label={t("suMin")} onDone={(v) => rowEdit(p, { min: n(v) })} /></td>
                    <td><Field num value={s(p.max)} label={t("suMax")} onDone={(v) => rowEdit(p, { max: n(v) })} /></td>
                    <td><Field num value={s(p.step)} label={t("suStep")} onDone={(v) => rowEdit(p, { step: n(v) })} /></td>
                  </>}
                <td><select value={p.scale} aria-label={t("suScale")} onChange={(e) => rowEdit(p, scaleOf(p, e.target.value as Scale))}>
                  <option value="linear">{t("suLinear")}</option><option value="log">{t("suLog")}</option><option value="values">{t("suValuesScale")}</option></select></td>
                <td><Field num value={String(p.count)} label={t("suCount")} onDone={(v) => rowEdit(p, { count: Math.max(1, Math.round(n(v) ?? p.count)) })} /></td>
                <td><button className="iconbtn" aria-label={t("suRemove", { name: p.name })} title={t("suRemove", { name: p.name })} onClick={() => edit((x) => removeParam(x, p.name))}>×</button></td>
              </tr>
            ))}
            {adding === 1 && <tr><td colSpan={7}><Field value="" label={t("suParam")} ph={t("suParam")} className="su-new-param"
              onDone={(v) => { setAdding(0); if (v.trim()) edit((x) => setParam(x, "", { name: v, min: null, max: null, step: null, scale: "linear", values: [], count: 4 })); }} /></td></tr>}
          </tbody>
        </table>
        <div className="su-foot">
          <button className="btn ghost su-add-param" onClick={() => setAdding(1)}>{t("suAddParam")}</button>
          <label className="su-wide">{t("suConstraints")}
            <Field value={(study.search?.constraints ?? []).join("; ")} label={t("suConstraints")} ph={t("suConstraintsPh")}
              onDone={(v) => edit((x) => ({ ...x, search: { params: x.search?.params ?? {}, ...x.search, constraints: v.split(";").map((c) => c.trim()).filter(Boolean) } }))} /></label>
        </div>
      </Section>

      <Section no={2} title={t("suScenarios")} count={fromTable ? String(guess!.scenarios.length) : sc.length > 1 ? `${sc.map((x) => x.values.length).join(" × ")} = ${r.combos}` : String(r.combos)} done={done[1]}>
        {fromTable ? <>
          <table className="data su-scen">
            <tbody>{guess!.scenarios.map((x) => <tr key={x.name} data-scenario={x.name}><td>{x.name}</td><td className="num">{x.values ? x.values.join(", ") : x.distinct}</td></tr>)}</tbody>
          </table>
          <p className="card-meta su-note">{t("suFromTable")}</p>
        </> : <>
          <table className="data su-scen">
            <tbody>
              {sc.map((x) => (
                <tr key={x.name} data-scenario={x.name}>
                  <td><Field value={x.name} label={t("suParam")} onDone={(v) => edit((y) => setScenario(y, x.name, { name: v, values: x.values }))} /></td>
                  <td><Field num value={x.values.join(", ")} label={t("suScenarioValues")} onDone={(v) => edit((y) => setScenario(y, x.name, { name: x.name, values: parseValues(v) }))} /></td>
                  <td><button className="iconbtn" aria-label={t("suRemove", { name: x.name })} onClick={() => edit((y) => removeScenario(y, x.name))}>×</button></td>
                </tr>
              ))}
              {adding === 2 && <tr><td colSpan={3}><Field value="" label={t("suParam")} ph={t("suParam")} className="su-new-scenario"
                onDone={(v) => { setAdding(0); if (v.trim()) edit((y) => setScenario(y, "", { name: v, values: [] })); }} /></td></tr>}
            </tbody>
          </table>
          <div className="su-foot"><button className="btn ghost su-add-scenario" onClick={() => setAdding(2)}>{t("suAddScenario")}</button></div>
        </>}
      </Section>

      <Section no={3} title={t("suOutputs")} count={String(outs.length)} done={done[2]}>
        {guess ? <div className="su-body">
          <p className="card-meta">{t("suGoalInTable")} <b className="num">{tb?.objective?.expr ? `${tb.objective.sense} ${tb.objective.expr}` : "-"}</b></p>
          <div className="card-next"><button className="btn outline su-open-goal" onClick={() => { useSweeps.setState({ part: "table" }); useSweeps.getState().setView({ step: "goals" }); }}>{t("suOpenGoal")}</button></div>
        </div> : <div className="su-body">
          <label className="su-wide">{t("suOutputsList")}
            <Field value={outs.join(", ")} label={t("suOutputsList")} className="su-outputs" onDone={(v) => edit((x) => setOutputs(x, v.split(",").map((o) => o.trim()).filter(Boolean)))} /></label>
          <div className="su-row">
            <span>{t("suRankBy")}</span>
            <select className="su-goal" aria-label={t("suRankBy")} value={tb?.objective?.expr ?? ""}
              onChange={(e) => edit((x) => setGoal(x, e.target.value, tb?.objective?.sense ?? "min", tb?.constraints ?? []))}>
              <option value="">-</option>{outs.map((o) => <option key={o} value={o}>{o}</option>)}</select>
            <div className="seg">{(["min", "max"] as const).map((d) => <button key={d} className={(tb?.objective?.sense ?? "min") === d ? "on" : ""} aria-pressed={(tb?.objective?.sense ?? "min") === d}
              onClick={() => edit((x) => setGoal(x, tb?.objective?.expr ?? "", d, tb?.constraints ?? []))}>{t(d === "min" ? "suMinimise" : "suMaximise")}</button>)}</div>
          </div>
          <label className="su-wide">{t("suMustHold")}
            <textarea key={(tb?.constraints ?? []).join("\n")} className="su-in su-hold" rows={2} dir="ltr" defaultValue={(tb?.constraints ?? []).join("\n")} aria-label={t("suMustHold")}
              onBlur={(e) => edit((x) => setGoal(x, tb?.objective?.expr ?? "", tb?.objective?.sense ?? "min", e.target.value.split("\n").map((c) => c.trim()).filter(Boolean)))} /></label>
        </div>}
      </Section>

      <Section no={4} title={t("suHowRun")} done={done[3]}>
        <div className="su-body">
          <div className="seg su-where">{(["pc", "farm"] as const).map((w) => <button key={w} className={where === w ? "on" : ""} aria-pressed={where === w}
            onClick={() => edit((x) => setRun(x, { where: w }))}>{t(w === "pc" ? "suThisPc" : "suFarm")}</button>)}</div>
          <label className="su-wide">{t(where === "pc" ? "suCommand" : "suCommandFarm")}
            <Field num value={joinCommand(study.launcher?.submit ?? [])} label={t("suCommand")} className="su-command" ph="python sim.py {{params_file}}"
              onDone={(v) => edit((x) => setRun(x, { command: v }))} /></label>
          {where === "pc" && <label className="su-row">{t("suWorkers")}
            <Field num value={String(study.launcher?.local_workers ?? 2)} label={t("suWorkers")} className="su-workers"
              onDone={(v) => edit((x) => setRun(x, { where: "pc", workers: Math.max(1, Math.round(n(v) ?? 2)) }))} /></label>}
          <p className="card-meta">{t(where === "pc" ? "suRunHint" : "suFarmHint")}</p>
        </div>
      </Section>
    </div>
  );
}
