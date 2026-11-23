import { useState } from "react";
import { useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { DEMOS, currentStep, demoFinish, demoLineUp, demoNext } from "../demoGuide";

/** RV5: a demo's line above the plots (or above a panel on the whole stage) - what it shows, what to do next and the
 *  click that does it; a demo of several steps counts them and offers *Show the result* (every step left at once). */
export default function DemoGuide({ area }: { area?: "sweeps" }) {
  const t = useT();
  const g = useApp((s) => s.demoGuide);
  // FR5: a demo of Sweeps has its line there, while its table of recordings is the one shown
  const up = useApp(demoLineUp) || (!!area && !!g && DEMOS[g.id]?.area === area);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const demo = g && DEMOS[g.id];
  if (!g || !demo || !up) return null;
  const step = currentStep(g);
  const done = g.done && demo.done;
  if (!step && !done) return null;
  const close = () => useApp.setState({ demoGuide: null });
  const run = (f: typeof demoNext) => async () => {
    setBusy(true); setFailed(false);
    try { await f(useApp.getState().demoGuide ?? g); } catch { setFailed(true); } finally { setBusy(false); }
  };
  const n = demo.steps.length, i = g.step ?? 0;
  return (
    <div className="demo-guide" role="status" data-demo={g.id} data-step={done ? "done" : i + 1}>
      {n > 1 && !done && <span className="demo-count" aria-label={t("demoStepOf", { i: i + 1, n })}>{i + 1}/{n}</span>}
      <span className="demo-text" dir="auto">{t(done ? demo.done! : step!.text)}{failed && <> · <b>{t("demoFailed")}</b></>}</span>
      {!done && step?.act && <button className="btn primary sm demo-next" disabled={busy} onClick={run(demoNext)}>{t(step.act)}</button>}
      {!done && n > 1 && i < n - 1 && <button className="linklike demo-finish" disabled={busy} onClick={run(demoFinish)}>{t("demoFinish")}</button>}
      <button className="iconbtn sm" onClick={close} aria-label={t("close")} title={t("close")}><Icon.X width={12} height={12} /></button>
    </div>
  );
}
