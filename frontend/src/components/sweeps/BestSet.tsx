/* The best set (S10) - in the answer's panel, and at the foot of the Goals step while a goal is
   edited (S22): the set ranked first, its parameters and its goal. */
import { useT } from "../../i18n";
import { labelOf } from "../../sweeps/scales";
import { useSweeps, type Study } from "../../sweeps/state";
import { colLabel, setColumns } from "../../sweeps/view";

export default function BestSet({ study }: { study: Study }) {
  const t = useT();
  const cols = setColumns(study);
  const rank = cols.get("#rank")?.values;
  if (!rank || !study.question.goal) return null;
  let best = -1;
  for (let i = 0; i < rank.length; i++) if (Number.isFinite(rank[i]) && (best < 0 || rank[i] < rank[best])) best = i;
  if (best < 0) return <div className="sw-hide-box sw-best"><b>★ {t("swBestSetTitle")}</b><span className="hint">{t("swNoBestSet")}</span></div>;
  const show = (name: string) => { const c = cols.get(name); return c ? labelOf(c, c.values[best]) : "–"; };
  const params = study.answer!.sets.filter((c) => c.group === "param").map((c) => c.name);
  const extra = ["#robustGoal", "#score"].filter((n) => cols.has(n));
  return (
    <div className="sw-hide-box sw-best">
      <b>★ {t("swBestSetTitle")}</b>
      <div className="sw-best-goal"><span>{colLabel(t, study, "#goal")}</span><b>{show("#goal")}</b></div>
      {extra.map((n) => <div key={n} className="sw-best-goal"><span>{colLabel(t, study, n)}</span><b>{show(n)}</b></div>)}
      <div className="sw-best-params">{params.map((p) => <span key={p}>{p} = <b>{show(p)}</b></span>)}</div>
      <button className="btn outline" onClick={() => useSweeps.getState().setView({ pinned: best, step: "results" })}>{t("swOpenBestSet")}</button>
    </div>
  );
}
