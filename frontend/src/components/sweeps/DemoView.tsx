/* W18: the smart-sweep demo - Next round / Run until converged / Reset, the live strip (the local workers
   fill and empty), the shared-parameter space (tried values by round, feasible or not, the best, the full
   grid's optimum as a ring), the convergence chart and the one-sentence result, computed from the numbers.
   The demo runs in its own work folder (svcore/demo.py); the backend runs the rounds, this view polls. */
import { fmtInt, fmtNum, useT, type TFn } from "../../i18n";
import { useApp } from "../../store";
import { Icon } from "../../icons";
import { closePanel, demoAction, openStudyFile, useStudyPanel } from "../../sweeps/studyStore";
import { studyApi } from "../../sweeps/studyApi";
import { pickPath } from "../../store";
import type { DemoProgress } from "../../sweeps/studyTypes";
import ConvergenceChart from "./ConvergenceChart";
import SpaceView from "./SpaceView";

/** The result in one sentence - the same numbers as `study demo` prints (svcore/demo.py sentence()). */
export function demoSentence(t: TFn, p: DemoProgress, lang: "en" | "he"): string {
  const pts = p.points.filter((x) => x.gap_pct !== null);
  if (!pts.length) return "";
  const hit = pts.find((x) => (x.gap_pct as number) <= p.tolerance_pct);
  const at = hit ?? pts[pts.length - 1];
  const per = Math.round(p.full_grid.runs / Math.max(1, p.full_grid.values));
  return hit
    ? t("dmSentenceHit", { tol: fmtNum(p.tolerance_pct, lang), runs: fmtInt(at.runs, lang), values: fmtInt(p.full_grid.values, lang), per,
      full: fmtInt(p.full_grid.runs, lang), x: fmtInt(Math.round(p.full_grid.runs / at.runs), lang) })
    : t("dmSentenceGap", { gap: fmtNum(at.gap_pct, lang, 3), runs: fmtInt(at.runs, lang), full: fmtInt(p.full_grid.runs, lang) });
}

export default function DemoView() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const p = useStudyPanel((s) => s.demoProgress);
  const study = useStudyPanel((s) => s.study);
  const error = useStudyPanel((s) => s.error);
  const running = !!p?.running;
  const startRuns = study?.demo ? Math.pow(study.demo.start_grid ?? 4, (study.shared ?? []).length)
    * study.tables.reduce((a, x) => a + Object.values(study.demo?.scenarios?.[x.id] ?? {}).reduce((m, v) => m * v.length, 1), 0) : 0;
  return (
    <div className="cp-panel dm-panel" data-testid="demo-panel">
      <div className="cp-head">
        <h2>{t("dmTitle")}</h2>
        <span className="cp-state">{p ? t("dmRound", { k: p.round }) : ""}</span>
        <span className="spacer" />
        <button className="btn primary dm-next" disabled={running || !p || p.exhausted} onClick={() => demoAction("next")}>{t("dmNext")}</button>
        <button className="btn outline dm-run" disabled={running || !p || p.exhausted || p.converged} onClick={() => demoAction("run")}>{t("dmRun")}</button>
        {running ? <button className="btn outline" onClick={() => demoAction("stop")}>{t("dmStop")}</button>
          : <button className="btn outline dm-reset" disabled={!p?.round} onClick={() => demoAction("reset")}><Icon.Reset /> {t("dmReset")}</button>}
        <button className="iconbtn" onClick={closePanel} aria-label={t("cpClose")} title={t("cpClose")}><Icon.X /></button>
      </div>
      {error && <p className="sw-error" role="alert">{error}</p>}
      {p && (
        <div className="dm-body" data-shot="demo" data-settled={running ? "0" : "1"}>
          <div className={`dm-strip${running ? " busy" : ""}`} role="status" data-done={p.runs.done} data-round={p.round}>
            <b>{t("dmRound", { k: p.round })}</b>
            <span>{t("dmRuns", { d: fmtInt(p.runs.done, lang), r: fmtInt(p.runs.running, lang), f: fmtInt(p.runs.failed, lang) })}</span>
            <span className="dm-workers" aria-hidden="true">{Array.from({ length: 8 }, (_, i) => <i key={i} className={i < Math.min(8, p.runs.running) ? "on" : ""} />)}</span>
            {p.converged && <span className="dm-ok">{t("dmConverged")}</span>}
          </div>
          {!p.points.length && !running && <p className="empty-note">{t("dmNothing", { n: fmtInt(startRuns, lang) })}</p>}
          <p className="dm-sentence">{demoSentence(t, p, lang)}</p>
          {p.points.length > 0 && (
            <table className="sw-table lp-rounds dm-rounds">
              <thead><tr><th>{t("dmRoundOf")}</th><th>{t("lpRunsDone")}</th><th>{t("lpBest")}</th><th>{t("dmGap")}</th></tr></thead>
              <tbody>{p.points.map((x) => <tr key={x.round} className={x.gap_pct !== null && x.gap_pct <= p.tolerance_pct ? "lp-better" : ""}>
                <td>{x.round}</td><td>{fmtInt(x.runs, lang)}</td><td>{x.best === null ? "–" : fmtNum(x.best, lang, 5)}</td>
                <td>{x.gap_pct === null ? "–" : `${fmtNum(x.gap_pct, lang, 3)} %`}</td></tr>)}</tbody>
            </table>
          )}
          <div className="dm-views">
            <SpaceView axes={p.axes} points={p.tried.map((x) => ({ values: x.values, feasible: x.feasible, round: x.round }))}
              best={p.best?.values} optimum={p.optimum.values} rounds={p.round} />
            <ConvergenceChart p={p} />
          </div>
          <HowItWorks />
        </div>
      )}
    </div>
  );
}

/** The demo explained on the screen, with the real files: the question, the program's input and output, the
 *  loop, and how to make it yours (a copy in a folder, opened as an ordinary study). */
function HowItWorks() {
  const t = useT();
  const study = useStudyPanel((s) => s.study);
  const path = useStudyPanel((s) => s.path);
  const p = useStudyPanel((s) => s.demoProgress);
  const tb = study?.tables[0];
  const ex: Record<string, string> = { run_id: "8c068b1aed", table: tb?.id ?? "A", round: "2", study_dir: "…/smart_sweep_demo",
    sleep_ms: String(study?.demo?.sleep_ms ?? 30), noise: String(study?.demo?.noise ?? 0), seed: String(study?.demo?.seed ?? 1),
    wind: "5", mass: "3.5", filter_hz: "30", ...Object.fromEntries(Object.entries(p?.best?.values ?? { Kp: 2.75, Ki: 0.7, Kd: 1.05 }).map(([k, v]) => [k, String(v)])) };
  const input = (tb?.params_template ?? "").replace(/\{\{\s*([\w]+)\s*\}\}/g, (_m, k: string) => ex[k] ?? k).trim();
  const copy = async () => {
    const folder = await pickPath({ mode: "folder", title: t("dmCopyTitle") });
    if (!folder) return;
    try {
      const r = await studyApi.copyDemo(path, folder);
      await openStudyFile(r.path, false);
      useApp.getState().toast({ kind: "info", text: t("dmCopied"), ms: 9000 });
    } catch (e) { useApp.getState().toast({ kind: "error", text: (e as Error).message }); }
  };
  return (
    <section className="dm-how" aria-label={t("dmHowTitle")}>
      <h3>{t("dmHowTitle")}</h3>
      <ol>
        <li><b>{t("dmHow1")}</b> {t("dmHow1Text")}</li>
        <li><b>{t("dmHow2")}</b> {t("dmHow2Text")}
          <pre dir="ltr" className="dm-io">{input}</pre>{t("dmHow2Out")}
          <pre dir="ltr" className="dm-io">{`Kp,Ki,Kd,wind,overshoot,settling_time,motor_sat,energy,phase_margin,run_id\n${ex.Kp},${ex.Ki},${ex.Kd},5,3.1,1.29,0.31,9.4,62.0,8c068b1aed`}</pre></li>
        <li><b>{t("dmHow3")}</b> {t("dmHow3Text")}</li>
        <li><b>{t("dmHow4")}</b> {t("dmHow4Text")}
          <div><button className="btn outline dm-copy" onClick={copy}><Icon.Copy /> {t("dmCopy")}</button></div></li>
      </ol>
    </section>
  );
}
