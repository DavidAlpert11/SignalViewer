/* C6 / SF1: *Send runs* (owner, 2026-11-16) - only what varies, the scenarios and how to run, then *Send round 1*.
   No outputs and no goal here: round 1's results come back as a table in Data and the usual flow follows (Columns,
   Goal, Results); the loop asks for its goal in Next runs. Each field is the study file's own block
   (sweeps/setup.ts), edited through editStudy: one Undo with the tables. A field is written when it is left (Enter
   or blur), not on every key. Older studies keep the outputs and goal typed here before (shown in Next runs). */
import { useState, type ReactNode } from "react";
import { fmtInt, useT } from "../../i18n";
import { useApp } from "../../store";
import { useSweeps } from "../../sweeps/state";
import { goFlow } from "../../sweeps/goFlow";
import { editStudy, isUnsaved, loopAction, useStudyPanel } from "../../sweeps/studyStore";
import { studyApi } from "../../sweeps/studyApi";
import { notify, notifyError } from "../../sweeps/notify";
import { applyParamsText, applyScenariosText, joinCommand, params, paramsText, parseValues, readiness, removeParam, removeScenario,
  runWhere, scenarios, scenariosText, setParam, setRun, setScenario, setupDone, type ParamRow, type Scale } from "../../sweeps/setup";
import { missingText } from "./RunPanel";
import { saveStudyDialog } from "./StudyPanel";

/** A text field written when it is left; it shows the stored value again after an undo (key = the value). */
function Field({ value, onDone, label, ph, className, num }: { value: string; onDone: (v: string) => void; label: string; ph?: string; className?: string; num?: boolean }) {
  return <input key={value} className={`su-in${num ? " num" : ""}${className ? " " + className : ""}`} defaultValue={value} aria-label={label} placeholder={ph}
    dir={num ? "ltr" : undefined} onBlur={(e) => { if (e.target.value !== value) onDone(e.target.value); }}
    onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />;
}
/** The inputs as "name: values" lines (owner, 2026-11-16), written when left - one Undo, like the fields. */
function TextBlock({ value, onDone, label, hint, className }: { value: string; onDone: (v: string) => void; label: string; hint: string; className: string }) {
  return <label className="su-wide">{hint}
    <textarea key={value} className={`su-in su-text ${className}`} dir="ltr" rows={Math.max(3, value.split("\n").length + 1)} defaultValue={value}
      aria-label={label} spellCheck={false} onBlur={(e) => { if (e.target.value !== value) onDone(e.target.value); }} /></label>;
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
  const [asText, setAsText] = useState<Record<number, boolean>>({});
  const textToggle = (no: number) => <button className="btn ghost su-as-text" aria-pressed={!!asText[no]}
    onClick={() => setAsText((x) => ({ ...x, [no]: !x[no] }))}>{t(asText[no] ? "suAsTable" : "suAsText")}</button>;
  const tables = useSweeps((x) => x.studies.length);
  const demo = useStudyPanel((x) => x.demo);                // the demo runs from its own controls (Next runs)
  if (!study) return null;
  const ps = params(study), sc = scenarios(study), r = readiness(study);
  const fromTable = !!guess && !sc.length;              // I have results: the scenarios are the table's columns
  const edit = (f: Parameters<typeof editStudy>[0]) => editStudy(f);
  const rowEdit = (p: ParamRow, patch: Partial<ParamRow>) => edit((x) => setParam(x, p.name, { ...p, ...patch }));
  const scaleOf = (p: ParamRow, v: Scale): Partial<ParamRow> => (v === "values"
    ? { scale: v, values: [p.min, p.max].filter((x): x is number => x !== null) } : { scale: v, min: p.min ?? p.values[0] ?? null, max: p.max ?? p.values[p.values.length - 1] ?? null });
  const done = setupDone(study, fromTable);
  return (
    <div className="su" data-part="setup" data-missing={r.missing.join(" ")}>
      <div className="su-head">
        <span className="eyebrow">{t("suTitle")} · {t("suPartOf", { n: done.filter(Boolean).length })}</span>
        <Field value={study.name ?? ""} label={t("suName")} ph={t("suNamePh")} className="su-name" onDone={(v) => edit((x) => ({ ...x, name: v }))} />
        {tables > 0 && <button className="btn outline su-to-results" onClick={() => goFlow("results")}>{t("suContinue")}</button>}
      </div>

      <Section no={1} title={t("suVaries")} count={String(ps.length)} done={done[0]}>
        {asText[1] ? <TextBlock value={paramsText(study)} label={t("suVaries")} hint={t("suParamsTextHint")} className="su-params-text"
          onDone={(v) => edit((x) => applyParamsText(x, v))} /> : <>
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
        </>}
        <div className="su-foot">
          {!asText[1] && <button className="btn ghost su-add-param" onClick={() => setAdding(1)}>{t("suAddParam")}</button>}
          {textToggle(1)}
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
        </> : asText[2] ? <>
          <TextBlock value={scenariosText(study)} label={t("suScenarios")} hint={t("suScenTextHint")} className="su-scen-text"
            onDone={(v) => edit((y) => applyScenariosText(y, v))} />
          <div className="su-foot">{textToggle(2)}</div>
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
          <div className="su-foot"><button className="btn ghost su-add-scenario" onClick={() => setAdding(2)}>{t("suAddScenario")}</button>{textToggle(2)}</div>
        </>}
      </Section>

      {!demo && <Section no={3} title={t("suHowRun")} done={done[2]}><RunHow /></Section>}
      {!demo && <SendRound />}
    </div>
  );
}

/** How to run (the study's launcher): this PC, a wrapper or a farm, the command, the workers - Send runs' part 3. */
function RunHow() {
  const t = useT();
  const study = useStudyPanel((x) => x.study);
  if (!study) return null;
  const where = runWhere(study);
  const path = useStudyPanel.getState().path;
  const edit = (f: Parameters<typeof editStudy>[0]) => editStudy(f);
  const copyWrapper = async () => {
    if (!path) { notify(t("suWrapperSaveFirst"), "error"); return; }
    try { notify(t((await studyApi.copyWrapper(path)).existed ? "suWrapperThere" : "suWrapperCopied")); } catch (e) { notifyError(e); }
  };
  return (
    <div className="su-body su-how">
      <div className="seg su-where">{(["pc", "wrapper", "farm"] as const).map((w) => <button key={w} data-where={w} className={where === w ? "on" : ""} aria-pressed={where === w}
        onClick={() => edit((x) => setRun(x, { where: w }))}>{t(w === "pc" ? "suThisPc" : w === "wrapper" ? "suWrapper" : "suFarm")}</button>)}</div>
      <label className="su-wide">{t(where === "pc" ? "suCommand" : where === "wrapper" ? "suCommandWrapper" : "suCommandFarm")}
        <Field num value={joinCommand(study.launcher?.submit ?? [])} label={t("suCommand")} className="su-command"
          ph={where === "pc" ? "python sim.py {{params_file}}" : "python sweep_wrapper.py --list {{params_files}}"}
          onDone={(v) => edit((x) => setRun(x, { command: v }))} /></label>
      {where === "pc" && <label className="su-row">{t("suWorkers")}
        <Field num value={String(study.launcher?.local_workers ?? 2)} label={t("suWorkers")} className="su-workers"
          onDone={(v) => edit((x) => setRun(x, { where: "pc", workers: Math.max(1, Math.round(n(v) ?? 2)) }))} /></label>}
      <p className="card-meta">{t(where === "pc" ? "suRunHint" : where === "wrapper" ? "suWrapperHint" : "suFarmHint")}</p>
      {where === "wrapper" && <div className="card-next"><button className="btn outline sm su-wrapper-copy" onClick={() => { void copyWrapper(); }}>{t("suWrapperCopy")}</button></div>}
    </div>
  );
}

/** Round 1 sent from here (the loop's first round: the start grid); its progress while it runs. A study with
 *  results already (I have results, rounds run) proposes its next rounds in Next runs. */
function SendRound() {
  const t = useT();
  const lang = useApp((x) => x.lang);
  const study = useStudyPanel((x) => x.study)!;
  const guess = useStudyPanel((x) => x.guess);
  const path = useStudyPanel((x) => x.path);
  const p = useStudyPanel((x) => x.loopProgress);
  const r = readiness(study);
  const running = !!p?.running;
  if ((study.history?.length || guess) && !running) return (
    <section className="card su-send" data-state="next">
      <p className="card-meta">{t("suSendNext")}</p>
      <div className="card-next"><button className="btn outline sm su-to-next" onClick={() => goFlow("next")}>{t("suToNext")}</button></div>
    </section>
  );
  const send = async () => {
    if (isUnsaved() || !path) { if (!(await saveStudyDialog(t))) return; }
    try { await loopAction("next"); } catch (e) { notifyError(e); }
  };
  return (
    <section className={`card su-send${r.missing.length ? " warn" : " ok"}`} data-missing={r.missing.join(" ")} data-state={running ? "running" : "ready"}>
      <span className="card-title">{r.missing.length ? t("suSendNotYet", { list: missingText(t, r.missing) }) : t("rcRound1", { sets: fmtInt(r.sets, lang), combos: fmtInt(r.combos, lang), runs: fmtInt(r.runs, lang) })}</span>
      <p className="card-meta">{t("suSendHint")}</p>
      {running && p && (
        <div className="dm-strip busy" role="status">
          <b>{t("dmRound", { k: p.round })}</b>
          <span>{t("dmRuns", { d: fmtInt(p.runs.done, lang), r: fmtInt(p.runs.running, lang), f: fmtInt(p.runs.failed, lang) })}</span>
        </div>
      )}
      {p?.error && !running && <p className="sw-error" role="alert">{p.error}</p>}
      <div className="card-next"><button className="btn primary su-send-btn" disabled={running || r.missing.length > 0} onClick={() => { void send(); }}>{t("suSend")}</button></div>
    </section>
  );
}
