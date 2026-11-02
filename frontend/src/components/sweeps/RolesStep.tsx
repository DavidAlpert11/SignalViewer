/* Step 2, the columns (2026-11-01: the old "clean columns" step is part of it - a column taken out is
   simply "not used") - what each column is: a SCENARIO (what we don't choose - a parameter set must hold in
   every combination of them), a PARAMETER (what we choose - each combination of them is a
   parameter set), an OUTPUT (a result to set goals on), a run id, a recording, or not used. The
   guess is only a start; the shape of the study follows every change. */
import { useT, type TKey } from "../../i18n";
import type { Role } from "../../sweeps/api";
import { useSweeps, type Study } from "../../sweeps/state";
import { ShapeStats } from "./Shape";
import DerivedEditor from "./DerivedEditor";
import { fmtValue } from "../../sweeps/scales";
import { StepFoot } from "./StepNav";

/** one value in every run, or empty */
const tellsNothing = (c: { constant: boolean; empty: boolean }) => c.constant || c.empty;

const ROLE_ORDER: { r: Role; key: TKey }[] = [
  { r: "param", key: "swRoleParam" }, { r: "output", key: "swRoleOutput" }, { r: "hold", key: "swRoleHold" },
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
      <NothingBox study={study} />
      <div className="sw-hide-box">
        <b>{t("swNewColumns")}</b>
        {q.derived.map((d, i) => (
          <div key={i} className="sw-derived">
            <b>ƒ {d.name}</b>
            <span className="hint">{d.kind === "row" ? d.expr : `${d.op}(${d.column})`}</span>
            <button className="iconbtn" aria-label={t("swRemove")} onClick={() => st.removeDerived(i)}>×</button>
          </div>
        ))}
        <DerivedEditor study={study} />
      </div>
      <StepFoot study={study} />
    </div>
  );
}

/** The columns that tell nothing (one value in every run, or empty): "not used" in one click. */
function NothingBox({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const removed = new Set(study.question.removed);
  const nothing = study.columns.filter(tellsNothing).filter((c) => c.role !== "ignore" && !removed.has(c.name));
  if (!nothing.length) return null;
  return (
    <div className="sw-hide-box">
      <b>{t("swHideNothing")}</b>
      <span className="hint">{t("swCleanNothing", { n: nothing.length })} {nothing.map((c) => c.name).join(", ")}</span>
      <button className="btn outline" onClick={() => nothing.forEach((c) => st.setRole(c.name, "ignore"))}>{t("swNothingUnused", { n: nothing.length })}</button>
    </div>
  );
}

export function RolesCenter({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const removed = new Set(study.question.removed);
  const cols = study.columns;
  // a column taken out in the old "clean" step shows as not used; any other role brings it back
  const roleOf = (c: Study["columns"][number]) => (removed.has(c.name) ? "ignore" : c.role);
  const choose = (name: string, r: Role) => {
    if (removed.has(name)) st.setRemoved([...removed].filter((x) => x !== name));
    st.setRole(name, r);
  };
  return (
    <div className="sw-table-wrap">
      <table className="sw-table sw-roles">
        <thead><tr><th>{t("swColumn")}</th>{ROLE_ORDER.map(({ r, key }) => <th key={r} className={`sw-th-${r}`}>{t(key)}</th>)}<th>{t("swKind")}</th><th>{t("swValuesShort")}</th></tr></thead>
        <tbody>{cols.map((c) => (
          <tr key={c.name} className={roleOf(c) === "ignore" ? "sw-unused" : ""}>
            <td className="sw-col-name">{c.name}{c.role !== c.guessRole && <span className="sw-changed"> · {t("swYourChoice")}</span>}</td>
            {ROLE_ORDER.map(({ r }) => (
              <td key={r} className="sw-radio">
                <input type="radio" name={`role-${c.name}`} checked={roleOf(c) === r} aria-label={`${c.name}: ${r}`} onChange={() => choose(c.name, r)} />
              </td>
            ))}
            <td className="hint">{c.kind === "number" ? t("swKindNumber") : t("swKindText")}</td>
            <td className="hint">{c.values && c.values.length <= 6 ? c.values.join(", ")
              : `${t("swDistinct", { n: c.distinct })}${c.min !== undefined && c.max !== undefined ? ` · ${fmtValue(c.min)} – ${fmtValue(c.max)}` : ""}`}
              {tellsNothing(c) ? <span className="sw-warn-txt"> · {t("swTellsNothing")}</span> : null}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}
