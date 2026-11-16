/* PLAN 2026-11-16 §7a: running the next sets from the app - in the Next runs step, beside the proposal of the
   next sets (it was the Run column on the right of every part, C8). What the next round will run (or what is still
   missing - Send runs in Data says it), the loop's goal (SF1: asked for here, not before), the loop's
   controls (Next round / Until converged / Stop / Start over; *Only write the files* and *Run them* with the
   launcher - C9: the one place a round is written or run) and its progress. The demo's controls are here too.
   A table opened alone gets its study file here, with *Run from the app*. */
import LoopAnswer from "./LoopAnswer";
import { useState } from "react";
import { fmtInt, useT, type TFn } from "../../i18n";
import { useApp } from "../../store";
import { Icon } from "../../icons";
import { useSweeps } from "../../sweeps/state";
import { firstTable, hasGoal, outputs, readiness, setGoal, type Missing } from "../../sweeps/setup";
import { demoAction, editStudy, isUnsaved, launcherCommand, sendToLauncher, setupFromOpenTable, suggestNext } from "../../sweeps/studyStore";
import { goFlow } from "../../sweeps/goFlow";
import { confirmAsk } from "../Overlays";
import { notify, notifyError } from "../../sweeps/notify";
import { saveStudyDialog } from "./StudyPanel";
import ConvergenceChart from "./ConvergenceChart";
import LoopSection from "./LoopSection";

let confirmedThisSession = false;                // W17: the launcher command is shown once per session
const MISSING: Record<Missing, string> = { params: "rcMissParams", range: "rcMissRange", command: "rcMissCommand" };
export const missingText = (t: TFn, m: Missing[]) => m.map((x) => t(MISSING[x] as never)).join(", ");

/** `goalAbove`: the loop's goal card is shown above the proposal already (Next runs with a table, no goal yet). */
export default function RunPanel({ goalAbove = false }: { goalAbove?: boolean }) {
  const t = useT();
  const common = useSweeps((s) => s.common);
  const table = useSweeps((s) => s.studies[s.active]);
  return (
    <section className="sw-run" aria-label={t("rcTitle")}>
      <h3 className="sw-run-title">{t("rcTitle")}</h3>
      {common.open && common.study ? (common.demo ? <DemoControls /> : <><NextRound />{!goalAbove && <LoopGoal />}<LoopSection /></>)
        : table ? <RunOffer /> : null}
    </section>
  );
}

/** A table opened alone: to run its next sets from the app it needs a study file - made from the table (its
 *  columns' roles and goal), the problem definition then says what is still missing. */
function RunOffer() {
  const t = useT();
  const make = async () => {
    try { if (await setupFromOpenTable()) useSweeps.setState({ part: "run" }); } catch (e) { notifyError(e); }
  };
  return (
    <div className="card rc-offer">
      <p className="card-meta">{t("rcOfferHint")}</p>
      <div className="card-next"><button className="btn outline sm rc-make" onClick={() => { void make(); }}>{t("rcOffer")}</button></div>
    </div>
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
        {(r.missing.length > 0 || (k === 1 && !hasGoal(study))) && <button className="btn outline sm rc-setup" onClick={() => useSweeps.setState({ part: "setup" })}>{t("rcDefine")}</button>}
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

/** SF1: the loop ranks the sets, so it needs a goal - asked for here. With a round's table open (linked to the study,
 *  C11) the goal is that table's Goal step (it reaches the study); otherwise said here: rank by, smallest / largest,
 *  what must hold. Older studies show the goal typed in their Set up. */
export function LoopGoal() {
  const t = useT();
  const study = useSweeps((s) => s.common.study)!;
  const table = useSweeps((s) => s.studies[s.active]);
  const tb = firstTable(study);
  const goal = hasGoal(study);
  const linked = !!table?.studyTable;
  const names = [...new Set([...outputs(study), ...(table?.columns.filter((c) => c.role === "output").map((c) => c.name) ?? [])])];
  const sense = tb?.objective?.sense ?? "min";
  const edit = (expr: string, d: "min" | "max", hold: string[]) => editStudy((x) => setGoal(x, expr, d, hold));
  return (
    <section className={`card rc-goal${goal ? " ok" : " warn"}`} data-goal={goal ? "1" : "0"}>
      <span className="card-title">{t("glTitle")}</span>
      {goal ? <span className="card-meta">{t("glNow", { goal: `${t(sense === "min" ? "suMinimise" : "suMaximise")} ${tb?.objective?.expr ?? ""}` })}</span>
        : <span className="card-meta">{t("glNeed")}</span>}
      {linked ? <>
        <span className="card-meta">{t("glInTable")}</span>
        <div className="card-next"><button className="btn outline sm rc-to-goal" onClick={() => goFlow("goal")}>{t("suOpenGoal")}</button></div>
      </> : <div className="su-body">
        <div className="su-row">
          <span>{t("suRankBy")}</span>
          <input key={tb?.objective?.expr ?? ""} className="su-in su-goal" dir="ltr" list="rc-goal-names" aria-label={t("suRankBy")} defaultValue={tb?.objective?.expr ?? ""}
            onBlur={(e) => { if (e.target.value.trim() !== (tb?.objective?.expr ?? "")) edit(e.target.value.trim(), sense, tb?.constraints ?? []); }}
            onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
          <datalist id="rc-goal-names">{names.map((o) => <option key={o} value={o} />)}</datalist>
          <div className="seg">{(["min", "max"] as const).map((d) => <button key={d} className={sense === d ? "on" : ""} aria-pressed={sense === d}
            onClick={() => edit(tb?.objective?.expr ?? "", d, tb?.constraints ?? [])}>{t(d === "min" ? "suMinimise" : "suMaximise")}</button>)}</div>
        </div>
        <label className="su-wide">{t("suMustHold")}
          <textarea key={(tb?.constraints ?? []).join("\n")} className="su-in su-hold" rows={2} dir="ltr" defaultValue={(tb?.constraints ?? []).join("\n")} aria-label={t("suMustHold")}
            onBlur={(e) => edit(tb?.objective?.expr ?? "", sense, e.target.value.split("\n").map((c) => c.trim()).filter(Boolean))} /></label>
      </div>}
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
          {p.converged ? <span className="dm-ok">{t("dmConverged")}</span> : <LoopAnswer p={p} />}
        </div>
      )}
      {p?.converged && <LoopAnswer p={p} />}
      {p && <ConvergenceChart p={p} />}
    </section>
  );
}
