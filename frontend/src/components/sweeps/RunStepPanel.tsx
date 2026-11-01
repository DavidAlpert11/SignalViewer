/* MF06 + MF11: the run step and the live monitor. The step: the command with placeholders ({param},
   {scenario}, {out}, {run}, {workdir}), where the results are (a JSON / CSV file at {out}, or the
   printed `name = value` lines), how many at once, a time limit, the results file. Before anything
   runs, the first run's command is shown as it will start. Then the runs of a group (a design, the
   virtual sets, the marked ones...) - each in every scenario - run as a job: counts by status, each
   output's history with the best so far, the Pareto front growing (two objectives), the last
   failures with their messages, Stop. The results file is a table: merged into the study when the
   runs end (or by hand), the group then holds its sets. */
import { useEffect, useMemo, useRef, useState } from "react";
import { pickPath } from "../../store";
import { useT } from "../../i18n";
import { sweepApi, type RunLive, type RunStep } from "../../sweeps/api";
import { FAILS, HOLDS } from "../../sweeps/colors";
import { maskOfKey, paramsOfId, setIds } from "../../sweeps/groups";
import { fmtValue } from "../../sweeps/scales";
import { notify, notifyError } from "../../sweeps/notify";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import { activeColumns } from "../../sweeps/view";
import NumField from "./NumField";

/** the run job of each table (kept while the app runs: leaving the area does not lose it) */
const jobOf = new Map<string, string>();

const defaultStep = (study: Study): RunStep => ({
  template: "python sim.py " + activeColumns(study, "param").concat(activeColumns(study, "hold")).map((c) => `--${c} {${c}}`).join(" ") + " --out {out}",
  workdir: study.path.replace(/[\\/][^\\/]*$/, ""), parser: "json", outputs: activeColumns(study, "output"),
  parallel: 2, timeout: 0, results: study.path.replace(/\.[^.\\/]+$/, "") + "_runs.csv",
});

export default function RunStepPanel({ study }: { study: Study }) {
  const t = useT();
  const a = study.answer!;
  const v = study.view;
  const step = v.runStep ?? defaultStep(study);
  const set = (p: Partial<RunStep>) => useSweeps.getState().setView({ runStep: { ...step, ...p } });
  const [source, setSource] = useState<string>(() => (v.groups ?? []).find((g) => g.source === "doe" || g.source === "virtual")?.id ?? "marked");
  const [combos, setCombos] = useState(true);
  const [preview, setPreview] = useState<{ args: string[]; runs: number; workdirExists: boolean } | null>(null);
  const [err, setErr] = useState("");
  // the sets of the chosen group, as values (ids of sets not run yet too)
  const sets = useMemo(() => {
    const g = (v.groups ?? []).find((x) => x.id === source);
    if (g?.frozen) return (g.ids ?? []).map((id) => paramsOfId(id, a));
    const ids = setIds(a);
    const m = maskOfKey(a, v.groups ?? [], source, v.rerun);
    return m ? ids.filter((_, i) => m[i]).map((id) => paramsOfId(id, a)) : [];
  }, [source, v.groups, v.rerun, a]);
  const stepKey = JSON.stringify([step, sets.length, combos, source]);
  useEffect(() => {
    let live = true;
    setErr("");
    if (!sets.length) { setPreview(null); return; }
    sweepApi.runPreview(study.tableId, wireQuestion(study), sets.slice(0, 1), combos, step)
      .then((r) => live && setPreview({ ...r, runs: r.runs * sets.length })).catch((e) => live && (setPreview(null), setErr((e as Error).message)));
    return () => { live = false; };
  }, [stepKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const [job, setJob] = useState<string | null>(() => jobOf.get(study.tableId) ?? null);
  const start = async () => {
    try {
      const r = await sweepApi.runStart(study.tableId, wireQuestion(study), sets, combos, step);
      jobOf.set(study.tableId, r.id);
      setJob(r.id);
      useSweeps.getState().journal("export", { path: step.results, n: preview?.runs ?? 0 });
    } catch (e) { notifyError(e); }
  };
  const pickDir = async () => { const p = await pickPath({ mode: "folder", title: t("swRunWorkdir") }); if (p) set({ workdir: p }); };
  const pickRes = async () => { const p = await pickPath({ mode: "save", title: t("swRunResults"), exts: [".csv"], defaultName: "runs.csv" }); if (p) set({ results: p }); };
  const groupsToRun = (v.groups ?? []);
  return (
    <section className="sw-runstep" aria-label={t("swRunStepTitle")}>
      <h3>{t("swRunStepTitle")}</h3>
      <label className="sw-field">{t("swRunTemplate")}
        <input className="mono" value={step.template} spellCheck={false} onChange={(e) => set({ template: e.target.value })} aria-label={t("swRunTemplate")} />
      </label>
      <p className="hint">{t("swRunTemplateHint")}</p>
      <div className="sw-row sw-runstep-grid">
        <label>{t("swRunWorkdir")} <span className="mono sw-path">{step.workdir}</span> <button className="btn outline" onClick={pickDir}>…</button></label>
        <label>{t("swRunParser")} <select aria-label={t("swRunParser")} value={step.parser} onChange={(e) => set({ parser: e.target.value as RunStep["parser"] })}>
          <option value="json">{t("swRunParserJson")}</option><option value="csv">{t("swRunParserCsv")}</option><option value="stdout">{t("swRunParserStdout")}</option></select></label>
        <label>{t("swRunParallel")} <NumField value={step.parallel} lo={1} hi={16} label={t("swRunParallel")} onChange={(x) => set({ parallel: Math.max(1, Math.min(64, Math.round(x))) })} /></label>
        <label>{t("swRunTimeout")} <NumField value={step.timeout} lo={0} hi={3600} label={t("swRunTimeout")} onChange={(x) => set({ timeout: Math.max(0, x) })} /></label>
        <label>{t("swRunResults")} <span className="mono sw-path">{step.results}</span> <button className="btn outline" onClick={pickRes}>…</button></label>
      </div>
      <div className="sw-row">
        <label>{t("swRunWhich")} <select aria-label={t("swRunWhich")} value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="marked">{t("swGrpMarked")}</option>
          <option value="holds">{t("swGrpHolds")}</option>
          <option value="all">{t("swGrpAll")}</option>
          {groupsToRun.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
        </select></label>
        <label className="acheck"><input type="checkbox" checked={combos} onChange={(e) => setCombos(e.target.checked)} />{t("swDoeCombos", { n: a.counts.combos })}</label>
      </div>
      {err && <p className="sw-error">{err}</p>}
      {preview && <div className="sw-run-preview">
        <span className="hint">{t("swRunFirst", { n: preview.runs })}</span>
        <code className="mono">{preview.args.map((x) => (/\s/.test(x) ? `"${x}"` : x)).join(" ")}</code>
        {!preview.workdirExists && <p className="sw-error">{t("swRunNoDir")}</p>}
      </div>}
      {!sets.length && <p className="hint">{t("swRunNoSets")}</p>}
      <button className="btn primary" disabled={!preview || !preview.workdirExists || !sets.length || !!(job && jobOf.get(study.tableId) === job && running.has(job))} onClick={start}>
        {t("swRunStart", { n: preview?.runs ?? 0 })}</button>
      {job && <Monitor study={study} job={job} />}
    </section>
  );
}

const running = new Set<string>();

function Monitor({ study, job }: { study: Study; job: string }) {
  const t = useT();
  const [st, setSt] = useState<RunLive | null>(null);
  const rows = useRef<Record<string, string | number | null>[]>([]);
  const [, tick] = useState(0);
  const [merged, setMerged] = useState(false);
  const [auto, setAuto] = useState(true);
  useEffect(() => {
    let live = true, timer = 0;
    rows.current = [];
    running.add(job);
    const poll = async () => {
      try {
        const r = await sweepApi.runLive(job, rows.current.length);
        if (!live) return;
        rows.current = rows.current.concat(r.live.rows);
        setSt(r); tick((x) => x + 1);
        if (r.job.state === "running") timer = window.setTimeout(poll, 700);
        else running.delete(job);
      } catch (e) { if (live) { running.delete(job); notifyError(e); } }
    };
    void poll();
    return () => { live = false; window.clearTimeout(timer); };
  }, [job]);
  const done = !!st && st.job.state !== "running";
  const merge = async () => {
    if (!st) return;
    try { const r = await useSweeps.getState().merge(st.live.path, "new"); setMerged(true); notify(t("swMerged", { added: r.added, replaced: r.replaced })); }
    catch (e) { notifyError(e); }
  };
  useEffect(() => { if (done && auto && !merged && st && (st.live.counts.ok > 0)) void merge(); }, [done]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!st) return <p className="hint">{t("swReading")}</p>;
  const c = st.live.counts;
  const outputs = study.view.runStep?.outputs?.length ? study.view.runStep.outputs : activeColumns(study, "output");
  const objs = study.question.objectives.length >= 2 ? study.question.objectives.slice(0, 2) : null;
  return (
    <div className="sw-monitor" aria-live="polite">
      <div className="sw-row sw-monitor-head">
        <progress max={1} value={st.job.progress} />
        <span className="sw-count-chip ok">{t("swRunOk", { n: c.ok })}</span>
        <span className="sw-count-chip bad">{t("swRunErr", { n: c.error })}</span>
        <span className="sw-count-chip warn">{t("swRunTimeoutN", { n: c.timeout })}</span>
        <span className="sw-count-chip">{t("swRunCached", { n: c.cached })}</span>
        <span className="hint">{t("swRunOf", { n: st.live.total, s: Math.round(st.job.elapsed) })}</span>
        {!done ? <button className="btn outline" onClick={() => sweepApi.runStop(job)}>{t("swRunStop")}</button>
          : <span className="hint">{t(st.job.state === "cancelled" ? "swRunStopped" : st.job.state === "error" ? "swRunFailed" : "swRunDone")}{st.job.error ? `: ${st.job.error}` : ""}</span>}
      </div>
      <div className="sw-monitor-grid">
        {outputs.slice(0, 4).map((o) => <History key={o} rows={rows.current} col={o}
          dir={study.question.goal?.column === o ? study.question.goal.direction : study.question.objectives.find((x) => x.column === o)?.direction} />)}
        {objs && <ParetoLive rows={rows.current} a={objs[0]} b={objs[1]} />}
      </div>
      {st.live.failures.length > 0 && <details className="sw-run-failures" open={c.ok === 0}>
        <summary>{t("swRunFailures", { n: st.live.failures.length })}</summary>
        <ul>{st.live.failures.slice().reverse().map((f) => <li key={f.run}><b>#{f.run + 1} {f.status}</b> <span className="mono">{JSON.stringify(f.inputs)}</span><br /><span className="hint">{f.message}</span></li>)}</ul>
      </details>}
      {done && <div className="sw-row">
        <span className="hint mono">{st.live.path}</span>
        {merged ? <span className="hint">{t("swRunMergedNote")}</span> : <button className="btn primary" disabled={!c.ok} onClick={merge}>{t("swRunMerge")}</button>}
      </div>}
      {!done && <label className="acheck"><input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />{t("swRunAutoMerge")}</label>}
    </div>
  );
}

function History({ rows, col, dir }: { rows: Record<string, string | number | null>[]; col: string; dir?: "max" | "min" }) {
  const pts = rows.map((r, i) => ({ i, v: typeof r[col] === "number" ? (r[col] as number) : NaN, ok: r.run_status === "ok" })).filter((p) => p.ok && Number.isFinite(p.v));
  const W = 260, H = 150, L = 40, B = 18, T = 8, R = 6;
  if (!pts.length) return <figure className="sw-model-fig"><figcaption className="hint mono">{col}: –</figcaption></figure>;
  let lo = Math.min(...pts.map((p) => p.v)), hi = Math.max(...pts.map((p) => p.v));
  if (lo === hi) { lo -= 1; hi += 1; }
  const n = Math.max(1, rows.length - 1);
  const X = (i: number) => L + (i / n) * (W - L - R), Y = (v: number) => H - B - ((v - lo) / (hi - lo)) * (H - B - T);
  let best = NaN;
  const line = dir ? pts.map((p) => { best = !Number.isFinite(best) || (dir === "max" ? p.v > best : p.v < best) ? p.v : best; return `${X(p.i)},${Y(best)}`; }).join(" ") : "";
  return (
    <figure className="sw-model-fig">
      <svg viewBox={`0 0 ${W} ${H}`} className="sw-chart" role="img" aria-label={col}>
        <line x1={L} y1={H - B} x2={W - R} y2={H - B} className="sw-ax-line" /><line x1={L} y1={T} x2={L} y2={H - B} className="sw-ax-line" />
        <text x={L - 3} y={T + 8} textAnchor="end" className="sw-ax">{fmtValue(hi)}</text><text x={L - 3} y={H - B} textAnchor="end" className="sw-ax">{fmtValue(lo)}</text>
        {pts.map((p) => <circle key={p.i} cx={X(p.i)} cy={Y(p.v)} r={1.8} fill={FAILS} />)}
        {line && <polyline points={line} fill="none" stroke={HOLDS} strokeWidth={2} />}
      </svg>
      <figcaption className="hint mono">{col}</figcaption>
    </figure>
  );
}

function ParetoLive({ rows, a, b }: { rows: Record<string, string | number | null>[]; a: { column: string; direction: "max" | "min" }; b: { column: string; direction: "max" | "min" } }) {
  const pts = rows.filter((r) => r.run_status === "ok" && typeof r[a.column] === "number" && typeof r[b.column] === "number")
    .map((r) => [r[a.column] as number, r[b.column] as number] as [number, number]);
  if (pts.length < 2) return null;
  const g = (p: [number, number]): [number, number] => [a.direction === "max" ? -p[0] : p[0], b.direction === "max" ? -p[1] : p[1]];
  const front = pts.filter((p) => !pts.some((q) => { const [x, y] = g(q), [u, w] = g(p); return x <= u && y <= w && (x < u || y < w); }));
  const W = 260, H = 150, L = 40, B = 18, T = 8, R = 6;
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const X = (v: number) => L + (x1 > x0 ? (v - x0) / (x1 - x0) : 0.5) * (W - L - R), Y = (v: number) => H - B - (y1 > y0 ? (v - y0) / (y1 - y0) : 0.5) * (H - B - T);
  return (
    <figure className="sw-model-fig">
      <svg viewBox={`0 0 ${W} ${H}`} className="sw-chart" role="img" aria-label="Pareto">
        <line x1={L} y1={H - B} x2={W - R} y2={H - B} className="sw-ax-line" /><line x1={L} y1={T} x2={L} y2={H - B} className="sw-ax-line" />
        {pts.map((p, i) => <circle key={i} cx={X(p[0])} cy={Y(p[1])} r={1.8} fill={FAILS} />)}
        {front.map((p, i) => <circle key={`f${i}`} cx={X(p[0])} cy={Y(p[1])} r={3.5} fill="none" stroke={HOLDS} strokeWidth={1.5} />)}
      </svg>
      <figcaption className="hint mono">{a.column} × {b.column} · Pareto {front.length}</figcaption>
    </figure>
  );
}

