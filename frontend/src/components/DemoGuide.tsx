import { useState } from "react";
import { useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { DEMO_STEPS, demoLineUp } from "../demoGuide";

/** RV5: a demo's line above the plots - what it shows, what to do next, and the click that does it. */
export default function DemoGuide() {
  const t = useT();
  const g = useApp((s) => s.demoGuide);
  const up = useApp(demoLineUp);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const step = g && DEMO_STEPS[g.id];
  if (!g || !step || !up) return null;
  const close = () => useApp.setState({ demoGuide: null });
  const go = async () => {
    setBusy(true); setFailed(false);
    try {
      await step.go?.(g.runs);
      // FR2: once its button was pressed the line says what happened (a step with a "done" text) or goes -
      // it never keeps offering what was just done
      useApp.setState({ demoGuide: step.done ? { ...g, done: true } : null });
    } catch { setFailed(true); }
    finally { setBusy(false); }
  };
  const done = g.done && step.done;
  return (
    <div className="demo-guide" role="status" data-demo={g.id}>
      <span className="demo-text" dir="auto">{t(done ? step.done! : step.text)}{failed && <> · <b>{t("demoFailed")}</b></>}</span>
      {!done && step.act && <button className="btn primary sm" disabled={busy} onClick={go}>{t(step.act)}</button>}
      <button className="iconbtn sm" onClick={close} aria-label={t("close")} title={t("close")}><Icon.X width={12} height={12} /></button>
    </div>
  );
}
