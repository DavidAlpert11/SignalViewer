/* C8: the Run column (plan §4.3 / §4.6 A, mock-up sweeps.html) - the right column of a study, beside every part
   of it: the next round (what it will run, or what is still missing - Set up says it), the loop's controls (Next
   round / Until converged / Stop / Start over; for a study of your own also *Only write the files* and *Run them*
   with the launcher - C9: the one place a round is written or run), its progress
   and convergence. Collapsible; the choice is remembered. The demo's controls are here too (its explanation, the
   space and the rounds stay in its page). */
import { useState } from "react";
import { fmtInt, useT, type TFn } from "../../i18n";
import { useApp } from "../../store";
import { Icon } from "../../icons";
import { getPrefValue, setPref } from "../../prefs";
import { useSweeps } from "../../sweeps/state";
import { readiness, type Missing } from "../../sweeps/setup";
import { demoAction, isUnsaved, launcherCommand, sendToLauncher, suggestNext } from "../../sweeps/studyStore";
import { confirmAsk } from "../Overlays";
import { notify, notifyError } from "../../sweeps/notify";
import { saveStudyDialog } from "./StudyPanel";
import ConvergenceChart from "./ConvergenceChart";
import LoopSection from "./LoopSection";

const PREF = "sv3.swRunHidden";
let confirmedThisSession = false;                // W17: the launcher command is shown once per session
const MISSING: Record<Missing, string> = { params: "rcMissParams", range: "rcMissRange", output: "rcMissOutput", goal: "rcMissGoal", command: "rcMissCommand" };
export const missingText = (t: TFn, m: Missing[]) => m.map((x) => t(MISSING[x] as never)).join(", ");

export default function RunColumn() {
  const t = useT();
  const common = useSweeps((s) => s.common);
  const [hidden, setHidden] = useState(() => getPrefValue<boolean>(PREF) === true);
  if (!common.open || !common.study) return null;
  const fold = (h: boolean) => { setPref(PREF, h); setHidden(h); };
  if (hidden) {
    return (
      <aside className="sw-run folded" aria-label={t("rcTitle")}>
        <button className="iconbtn rc-toggle" aria-expanded="false" onClick={() => fold(false)} title={t("rcShow")} aria-label={t("rcShow")}>‹</button>
      </aside>
    );
  }
  return (
    <aside className="side sw-run" aria-label={t("rcTitle")}>
      <div className="panel-head rc-head">
        <span className="eyebrow">{t("rcTitle")}</span>
        <button className="iconbtn sm rc-toggle ph-actions" aria-expanded="true" onClick={() => fold(true)} title={t("rcHide")} aria-label={t("rcHide")}>›</button>
      </div>
      <div className="rc-body">
        {common.demo ? <DemoControls /> : <><NextRound /><LoopSection /></>}
      </div>
    </aside>
  );
}

/** What the next round will run - round 1's start grid, or what is missing for it (a click opens Set up). */
function NextRound() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const study = useSweeps((s) => s.common.study)!;
  const p = useSweeps((s) => s.common.loopProgress);
  const path = useSweeps((s) => s.common.path);
  const status = useSweeps((s) => s.common.status);
  const [busy, setBusy] = useState(false);
  const r = readiness(study);
  const k = (p?.round ?? study.history?.length ?? 0) + 1;
  const write = async () => {
    if (!path || isUnsaved()) { if (!(await saveStudyDialog(t))) { notify(t("cpSaveFirst"), "error"); return; } }
    setBusy(true);
    try {
      const n = await suggestNext();
      notify(n.exhausted ? t("cpExhausted") : t("cpNextDone", { k: n.round, c: n.counts.candidates, r: n.counts.runs, f: n.files.join(", ") }), n.exhausted ? "error" : "info");
    } catch (e) { notifyError(e); } finally { setBusy(false); }
  };
  // W17 (C9: was *Send to launcher* above the ranking): the written round run with the study's command - once
  // per session the exact command is shown first
  const hasCmd = !!study.launcher?.submit?.length;
  const written = !!study.history?.some((h) => h.proposals.some((x) => x.state === "pending"));
  const runThem = async () => {
    if (!path || isUnsaved()) { if (!(await saveStudyDialog(t))) return; }
    try {
      const cmd = await launcherCommand();
      if (!confirmedThisSession) {
        if (!(await confirmAsk(t("cpSendTitle"), t("cpSendText", { cwd: cmd.cwd, n: cmd.submitted, cmd: cmd.command.join(" ") }), t("cpSendOk")))) return;
        confirmedThisSession = true;
      }
      await sendToLauncher();
    } catch (e) { notifyError(e); }
  };
  return (
    <section className={`card rc-next${r.missing.length ? " warn" : " ok"}`} data-missing={r.missing.join(" ")} data-round={k}>
      <span className="card-title">{r.missing.length ? t("rcMissingTitle", { k }) : t("rcReady", { k })}</span>
      {k === 1 && r.runs > 0 && <span className="card-meta">{t("rcRound1", { sets: fmtInt(r.sets, lang), combos: fmtInt(r.combos, lang), runs: fmtInt(r.runs, lang) })}</span>}
      {r.missing.length > 0 && <span className="card-meta">{t("rcMissing", { list: missingText(t, r.missing) })}</span>}
      <div className="card-next">
        {r.missing.length > 0 && <button className="btn outline sm rc-setup" onClick={() => useSweeps.setState({ part: "setup" })}>{t("suTitle")}</button>}
        {/* W15: the next runs written to the round's folder, for a launcher of your own - nothing runs */}
        <button className="btn outline sm rc-write" disabled={busy || !study.tables.length} onClick={() => { void write(); }}
          title={t("rcWriteHint")}>{t("rcWrite")}</button>
        <button className="btn outline sm rc-send" disabled={!hasCmd || !written} onClick={() => { void runThem(); }}
          title={hasCmd ? t("rcRunThemHint") : t("cpNoLauncher")}>{t("rcRunThem")}</button>
      </div>
      {status && (
        <span className="card-meta cp-run-states" role="status" data-finished={status.finished ? "1" : "0"}>
          {t("cpRunsCount", { k: status.round, done: status.counts.done, sub: status.counts.submitted, failed: status.counts.failed, missing: status.counts.missing })}</span>
      )}
    </section>
  );
}

/** The demo's loop: Next round / Until converged / Stop / Start over, its live strip and the convergence chart. */
function DemoControls() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const p = useSweeps((s) => s.common.demoProgress);
  const running = !!p?.running;
  return (
    <section className="lp" aria-label={t("lpTitle")}>
      <div className="rc-buttons">
        <button className="btn primary sm dm-next" disabled={running || !p || p.exhausted} onClick={() => { void demoAction("next"); }}>{t("dmNext")}</button>
        <button className="btn outline sm dm-run" disabled={running || !p || p.exhausted || p.converged} onClick={() => { void demoAction("run"); }}>{t("dmRun")}</button>
        {running ? <button className="btn outline sm" onClick={() => { void demoAction("stop"); }}>{t("dmStop")}</button>
          : <button className="btn ghost sm dm-reset" disabled={!p?.round} onClick={() => { void demoAction("reset"); }}><Icon.Reset /> {t("dmReset")}</button>}
      </div>
      {p && (
        <div className={`dm-strip${running ? " busy" : ""}`} role="status" data-done={p.runs.done} data-round={p.round}>
          <b>{t("dmRound", { k: p.round })}</b>
          <span>{t("dmRuns", { d: fmtInt(p.runs.done, lang), r: fmtInt(p.runs.running, lang), f: fmtInt(p.runs.failed, lang) })}</span>
          <span className="dm-workers" aria-hidden="true">{Array.from({ length: 8 }, (_, i) => <i key={i} className={i < Math.min(8, p.runs.running) ? "on" : ""} />)}</span>
          {p.converged && <span className="dm-ok">{t("dmConverged")}</span>}
        </div>
      )}
      {p && <ConvergenceChart p={p} />}
    </section>
  );
}
