/* The Run area (M23 §4): quiet until the study has a run step (MF06 - a template, a parser, the
   runs in parallel - and MF11, the live monitor). Until then it says how the loop closes today:
   the next runs exported as a list, run in one's own tool, the results table opened or merged back. */
import { useT } from "../../i18n";
import { useSweeps, type Study } from "../../sweeps/state";
import DoeSheet from "./DoeSheet";
import RunStepPanel from "./RunStepPanel";
import OptimiserPanel from "./OptimiserPanel";

export function RunSide() {
  const t = useT();
  return (
    <div className="sw-side-step">
      <p className="hint">{t("swRunQuiet")}</p>
    </div>
  );
}

export function RunCenter({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  return (
    <div className="sw-run-quiet">
      {study.answer && <DoeSheet study={study} />}
      {study.answer && <RunStepPanel study={study} />}
      {study.answer && <OptimiserPanel study={study} />}
      <h3>{t("swRunNoStep")}</h3>
      <p>{t("swRunToday")}</p>
      <ol>
        <li>{t("swRunToday1")} <button className="linklike" disabled={!study.answer} onClick={() => st.setView({ step: "results", center: "next" })}>{t("swCenterNext")}</button></li>
        <li>{t("swRunToday2")}</li>
        <li>{t("swRunToday3")}</li>
      </ol>
    </div>
  );
}
