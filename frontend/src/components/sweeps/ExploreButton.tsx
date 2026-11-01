/* "Explore this goal →" (S23): the way into Explore from where the goal is edited (the Goals step)
   and from the answer (the Results' side). It starts a fresh draft of the active goal; the Explore
   tab of the results goes back to a draft already there. Its own file: GoalsStep and ResultsSide
   both show it, and ExploreView imports GoalsStep. */
import { useT } from "../../i18n";
import { draftOf } from "../../sweeps/explore";
import { useSweeps, type Study } from "../../sweeps/state";

export default function ExploreButton({ study }: { study: Study }) {
  const t = useT();
  const q = study.question;
  const open = () => useSweeps.getState().setView({ step: "results", center: "explore",
    explore: { draft: draftOf(q.goals[q.active]), from: q.active } });
  return (
    <div className="sw-explore-cta">
      <button className="btn primary" onClick={open}>{t("swExploreThis")} →</button>
      <span className="hint">{t("swExploreThisHint")}</span>
    </div>
  );
}
