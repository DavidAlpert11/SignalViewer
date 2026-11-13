/* Owner (2026-11-13): Signal Viewer as the manager of the runs - for any study with a launcher command:
   propose the next runs, start them (your program on this PC, or your launcher), wait for their results to
   appear in the results folder, read them, rank, propose again - until it converges. This section shows what
   runs (the exact command, where the results are read from), the buttons, the live strip, the convergence
   chart and the rounds; the backend runs the loop (svcore/loop.py), this polls it. */
import { fmtInt, fmtNum, useT } from "../../i18n";
import { useApp } from "../../store";
import { Icon } from "../../icons";
import { isUnsaved, loopAction, useStudyPanel } from "../../sweeps/studyStore";
import ConvergenceChart from "./ConvergenceChart";
import { saveStudyDialog } from "./StudyPanel";

export default function LoopSection() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const p = useStudyPanel((s) => s.loopProgress);
  const study = useStudyPanel((s) => s.study);
  const path = useStudyPanel((s) => s.path);
  const cmd = study?.launcher?.submit ?? [];
  const running = !!p?.running;
  const act = async (a: "next" | "run" | "stop" | "reset") => {
    if ((a === "next" || a === "run") && (isUnsaved() || !path)) { if (!(await saveStudyDialog(t))) return; }
    try { await loopAction(a); } catch { /* saved first above */ }
  };
  const state = p?.state ?? "";
  return (
    <section className="lp" aria-label={t("lpTitle")} data-state={state} data-round={p?.round ?? 0} data-points={p?.points.length ?? 0}>
      <div className="lp-head">
        <h3>{t("lpTitle")}</h3>
        {state && <span className={`lp-state ${state}`}>{t(`lpState_${state}` as never)}</span>}
        <span className="spacer" />
        <button className="btn primary lp-next" disabled={running || !cmd.length} onClick={() => act("next")}>{t("dmNext")}</button>
        <button className="btn outline lp-run" disabled={running || !cmd.length} onClick={() => act("run")}><Icon.Reload /> {t("dmRun")}</button>
        {running ? <button className="btn outline lp-stop" onClick={() => act("stop")}>{t("dmStop")}</button>
          : <button className="btn outline lp-reset" disabled={!p?.points.length} onClick={() => act("reset")} title={t("lpResetHint")}>{t("dmReset")}</button>}
      </div>
      {!cmd.length ? <p className="hint">{t("lpNoCommand")}</p> : (
        <dl className="lp-what">
          <dt>{t("lpRuns")}</dt><dd><code dir="ltr">{cmd.join(" ")}</code>
            <span className="hint"> · {study?.launcher?.local_workers ? t("lpLocal", { n: study.launcher.local_workers }) : t("lpFarm")}</span></dd>
          <dt>{t("lpReads")}</dt><dd><code dir="ltr">{study?.launcher?.results?.glob ?? "results/{{table}}/{{run_id}}*"}</code></dd>
        </dl>
      )}
      {p && (p.round > 0 || running) && (
        <div className={`dm-strip${running ? " busy" : ""}`} role="status">
          <b>{t("dmRound", { k: p.round })}</b>
          <span>{t("dmRuns", { d: fmtInt(p.runs.done, lang), r: fmtInt(p.runs.running, lang), f: fmtInt(p.runs.failed, lang) })}</span>
          <span className="dm-workers" aria-hidden="true">{Array.from({ length: 8 }, (_, i) => <i key={i} className={i < Math.min(8, p.runs.running) ? "on" : ""} />)}</span>
          {p.best && <span>{t("lpBest")}: <b>{fmtNum(p.best.score, lang, 5)}</b> <bdi className="hint">{Object.entries(p.best.values).map(([k, v]) => `${k} = ${v}`).join(", ")}</bdi></span>}
        </div>
      )}
      {p && p.points.length > 0 && (
        <div className="lp-views">
          <ConvergenceChart p={p} />
          <table className="sw-table lp-rounds">
            <thead><tr><th>{t("dmRoundOf")}</th><th>{t("lpRunsDone")}</th><th>{t("lpBest")}</th><th>{t("lpChange")}</th></tr></thead>
            <tbody>{p.points.map((x, i) => {
              const prev = i ? p.points[i - 1].best : null;
              const d = prev !== null && x.best !== null ? x.best - prev : null;
              return <tr key={x.round}><td>{x.round}</td><td>{fmtInt(x.runs, lang)}</td><td>{x.best === null ? "–" : fmtNum(x.best, lang, 5)}</td>
                <td className={d !== null && d < 0 ? "lp-better" : ""}>{d === null ? "" : d === 0 ? t("lpSame") : fmtNum(d, lang, 3)}</td></tr>;
            })}</tbody>
          </table>
        </div>
      )}
    </section>
  );
}
