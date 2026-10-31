/* Step 3 - what each column is: a SCENARIO (what we don't choose - a parameter set must hold in
   every combination of them), a PARAMETER (what we choose - each combination of them is a
   parameter set), an OUTPUT (a result to set goals on), a run id, a recording, or not used. The
   guess is only a start; the shape of the study follows every change. */
import { useT, type TKey } from "../../i18n";
import type { Role } from "../../sweeps/api";
import { useSweeps, type Study } from "../../sweeps/state";
import { ShapeStats } from "./Shape";
import { StepFoot } from "./StepNav";

const ROLE_ORDER: { r: Role; key: TKey }[] = [
  { r: "hold", key: "swRoleHold" }, { r: "param", key: "swRoleParam" }, { r: "output", key: "swRoleOutput" },
  { r: "id", key: "swRoleId" }, { r: "recording", key: "swRoleRecording" }, { r: "ignore", key: "swRoleIgnore" },
];

export function RolesSide({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const q = study.question;
  const holds = study.columns.filter((c) => c.role === "hold" && !q.removed.includes(c.name));
  const changed = study.columns.some((c) => c.role !== c.guessRole);
  return (
    <div className="sw-side-step">
      <p className="sw-step-intro">{t("swRolesIntro")}</p>
      <ShapeStats study={study} />
      {study.summary.duplicates > 0 && <p className="sw-warn">{t("swDuplicates", { n: study.summary.duplicates })}</p>}
      {holds.length > 0 && (
        <div className="sw-hide-box">
          <b>{t("swRolesValues")}</b>
          <span className="hint">{t("swRolesValuesHint")}</span>
          {holds.map((c) => {
            const all = c.values ?? [];
            const kept = q.holdValues[c.name]?.length ? q.holdValues[c.name] : all;
            return (
              <div key={c.name} className="sw-hold">
                <div className="sw-hold-name">{c.name}</div>
                {all.length ? (
                  <div className="sw-hold-values">{all.map((v) => {
                    const on = kept.includes(v);
                    return <button key={String(v)} className={`sw-pill${on ? " on" : ""}`} aria-pressed={on}
                      onClick={() => { const next = on ? kept.filter((x) => x !== v) : [...kept, v]; if (next.length) st.setHoldValues(c.name, next.length === all.length ? [] : next); }}>{String(v)}</button>;
                  })}</div>
                ) : <span className="hint">{t("swDistinct", { n: c.distinct })}</span>}
              </div>
            );
          })}
        </div>
      )}
      {changed && <button className="linklike" onClick={st.resetRoles}>{t("swBackToGuessRoles")}</button>}
      <StepFoot study={study} />
    </div>
  );
}

export function RolesCenter({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const removed = new Set(study.question.removed);
  const cols = study.columns.filter((c) => !removed.has(c.name));
  return (
    <div className="sw-table-wrap">
      <table className="sw-table sw-roles">
        <thead><tr><th>{t("swColumn")}</th>{ROLE_ORDER.map(({ r, key }) => <th key={r} className={`sw-th-${r}`}>{t(key)}</th>)}<th>{t("swValuesShort")}</th></tr></thead>
        <tbody>{cols.map((c) => (
          <tr key={c.name}>
            <td className="sw-col-name">{c.name}{c.role !== c.guessRole && <span className="sw-changed"> · {t("swYourChoice")}</span>}</td>
            {ROLE_ORDER.map(({ r }) => (
              <td key={r} className="sw-radio">
                <input type="radio" name={`role-${c.name}`} checked={c.role === r} aria-label={`${c.name}: ${r}`} onChange={() => st.setRole(c.name, r)} />
              </td>
            ))}
            <td className="hint">{c.values && c.values.length <= 6 ? c.values.join(", ") : t("swDistinct", { n: c.distinct })}</td>
          </tr>
        ))}</tbody>
      </table>
      {removed.size > 0 && <p className="hint">{t("swRolesRemoved", { n: removed.size })}</p>}
    </div>
  );
}
