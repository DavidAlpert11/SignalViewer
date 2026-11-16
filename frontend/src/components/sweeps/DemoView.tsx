/* W18: the smart-sweep demo - the shared-parameter space (tried values by round, feasible or not, the best, the full
   grid's optimum as a ring), the rounds and the one-sentence result, computed from the numbers. How it works is the
   study's About page (`HowItWorks`, C9). Its Next round / Run
   until converged / Reset, the live strip and the convergence chart are in the Run column (C8).
   The demo runs in its own work folder (svcore/demo.py); the backend runs the rounds, this view polls. */
import { fmtInt, fmtNum, useT, type TFn } from "../../i18n";
import { useApp } from "../../store";
import { Icon } from "../../icons";
import { openStudyFile, useStudyPanel } from "../../sweeps/studyStore";
import { useSweeps } from "../../sweeps/state";
import { studyApi } from "../../sweeps/studyApi";
import { pickPath } from "../../store";
import type { DemoProgress } from "../../sweeps/studyTypes";
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
      </div>
      {error && <p className="sw-error" role="alert">{error}</p>}
      {p && (
        <div className="dm-body" data-shot="demo" data-settled={running ? "0" : "1"}>
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
          </div>
        </div>
      )}
    </div>
  );
}

/** The demo explained on the screen, with the real files: the question, the program's input and output, the
 *  loop, and how to make it yours (a copy in a folder, opened as an ordinary study). C9: the study's *About*
 *  page (the navigator's item), no longer below the rounds. */
export function HowItWorks() {
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
        <li><b>{t("dmHow3")}</b> {t("dmHow3Text")}
          <pre dir="ltr" className="dm-io">{(study?.launcher?.submit ?? []).join(" ")}</pre></li>
        <li><b>{t("dmHowInputs")}</b> {t("dmHowInputsText")}{" "}
          <button className="linklike dm-inputs" onClick={() => useSweeps.setState({ part: "setup" })}>{t("dmHowInputsLink")}</button></li>
        <li><b>{t("dmHowYourself")}</b> {t("dmHowYourselfText")}
          <pre dir="ltr" className="dm-io dm-cmd">{`cd "${path.replace(/[\\/][^\\/]*$/, "")}"\npython sweep_wrapper.py --spec grid.txt --set table=A --out my_sweep.csv`}</pre></li>
        <li><b>{t("dmHow4")}</b> {t("dmHow4Text")}
          <div><button className="btn outline dm-copy" onClick={copy}><Icon.Copy /> {t("dmCopy")}</button></div></li>
      </ol>
    </section>
  );
}
