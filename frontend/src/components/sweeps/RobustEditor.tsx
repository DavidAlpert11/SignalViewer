/* Robust to (S06): the parameters a good set must not be fragile to - each with how far it may move
   (± a percentage of its value, ± a value, or ± steps of the grid). A set holds robustly when every
   set within that tolerance holds too, and its goal is their worst case; only such sets are ranked.
   For every goal of the study. Chosen by typing, as columns are everywhere in the area. */
import { useT } from "../../i18n";
import type { Tolerance } from "../../sweeps/model";
import { useSweeps, type Study } from "../../sweeps/state";
import { activeParams } from "../../sweeps/view";
import ColumnPicker from "./ColumnPicker";

const DEFAULT_TOL: Tolerance = { mode: "steps", value: 1 };

export default function RobustEditor({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const robust = study.question.robust ?? {};
  // only numbers can move by a tolerance
  const numeric = new Set(study.columns.filter((c) => c.kind === "number").map((c) => c.name));
  const params = activeParams(study).filter((p) => numeric.has(p));
  const chosen = Object.keys(robust).filter((c) => params.includes(c));
  const choose = (ids: string[]) => {
    for (const c of chosen) if (!ids.includes(c)) st.setRobust(c, null);
    for (const c of ids) if (!chosen.includes(c)) st.setRobust(c, DEFAULT_TOL);
  };
  const seen = study.answer?.sets.find((c) => c.name === "#robustSeen")?.values;
  const unmeasured = seen ? Array.from(seen).every((x) => x === 0) : false;
  return (
    <section className="sw-goal-part">
      <h3>{t("swRobustTo")}</h3>
      <span className="hint">{t("swRobustHint")}</span>
      {params.length === 0 ? <span className="hint">{t("swRobustNoParams")}</span> : (
        <ColumnPicker options={params.map((p) => ({ id: p, label: p, group: t("swRoleParam") }))} value={chosen} onChange={choose}
          label={t("swRobustPick", { n: chosen.length, of: params.length })} />
      )}
      {chosen.map((c) => {
        const tol = robust[c];
        return (
          <div key={c} className="sw-cond-line sw-robust-row">
            <span className="sw-robust-name">{c}</span>
            <span>±</span>
            <input type="number" min={0} step="any" aria-label={t("swRobustValue", { c })} defaultValue={tol.value} key={`${c}:${tol.value}`} style={{ width: 72 }}
              onBlur={(e) => { const v = Math.abs(Number(e.target.value)); if (Number.isFinite(v) && v !== tol.value) st.setRobust(c, { ...tol, value: v }); }}
              onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
            <select aria-label={t("swRobustMode", { c })} value={tol.mode} onChange={(e) => st.setRobust(c, { ...tol, mode: e.target.value as Tolerance["mode"] })}>
              <option value="pct">{t("swTolPct")}</option><option value="abs">{t("swTolAbs")}</option><option value="steps">{t("swTolSteps")}</option>
            </select>
            <select aria-label={t("swRobustDist", { c })} value={tol.dist ?? "uniform"} title={t("swRobustDistHint")}
              onChange={(e) => st.setRobust(c, { ...tol, dist: e.target.value as NonNullable<Tolerance["dist"]> })}>
              <option value="uniform">{t("swDist_uniform")}</option><option value="triangular">{t("swDist_triangular")}</option><option value="normal">{t("swDist_normal")}</option>
            </select>
            <button className="iconbtn" aria-label={t("swRemove")} onClick={() => st.setRobust(c, null)}>×</button>
          </div>
        );
      })}
      {chosen.length > 0 && unmeasured && <p className="sw-warn">{t("swRobustUnmeasured")}</p>}
    </section>
  );
}
