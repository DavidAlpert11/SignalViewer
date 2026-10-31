/* Step 2 - clean the columns: take out those that tell nothing (one value in every run, empty), or
   any not wanted; add columns made from others (a formula per run, a value per parameter set).
   Taking a column out only leaves it out of the analysis; the table is not changed. */
import { useT } from "../../i18n";
import { fmtValue } from "../../sweeps/scales";
import { useSweeps, type Study } from "../../sweeps/state";
import DerivedEditor from "./DerivedEditor";
import { StepFoot } from "./StepNav";

const tellsNothing = (c: { constant: boolean; empty: boolean }) => c.constant || c.empty;

export function CleanSide({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const q = study.question;
  const nothing = study.columns.filter(tellsNothing).map((c) => c.name);
  const outNow = nothing.filter((c) => q.removed.includes(c)).length;
  return (
    <div className="sw-side-step">
      <p className="sw-step-intro">{t("swCleanIntro")}</p>
      <div className="sw-hide-box">
        <b>{t("swHideNothing")}</b>
        <span className="hint">{t("swCleanNothing", { n: nothing.length })}</span>
        <div className="sw-row">
          <button className="btn primary" disabled={!nothing.length || outNow === nothing.length}
            onClick={() => st.setRemoved([...new Set([...q.removed, ...nothing])])}>{t("swCleanRemoveAll", { n: nothing.length })}</button>
          {q.removed.length > 0 && <button className="btn" onClick={() => st.setRemoved([])}>{t("swCleanKeepAll")}</button>}
        </div>
      </div>
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

export function CleanCenter({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const removed = new Set(study.question.removed);
  const toggle = (c: string, out: boolean) => st.setRemoved(out ? [...removed, c] : [...removed].filter((x) => x !== c));
  return (
    <div className="sw-table-wrap">
      <table className="sw-table sw-clean">
        <thead><tr><th>{t("swCleanKeep")}</th><th>{t("swColumn")}</th><th>{t("swKind")}</th><th className="num">{t("swDistinctN")}</th>
          <th className="num">{t("swMin")}</th><th className="num">{t("swMax")}</th><th className="num">{t("swMissingN")}</th><th>{t("swNote")}</th></tr></thead>
        <tbody>{study.columns.map((c) => {
          const out = removed.has(c.name);
          return (
            <tr key={c.name} className={out ? "sw-out" : ""}>
              <td><input type="checkbox" checked={!out} aria-label={t("swCleanKeepCol", { c: c.name })} onChange={(e) => toggle(c.name, !e.target.checked)} /></td>
              <td className="sw-col-name">{c.name}</td>
              <td>{c.kind === "number" ? t("swKindNumber") : t("swKindText")}</td>
              <td className="num">{c.distinct.toLocaleString()}</td>
              <td className="num">{c.min !== undefined ? fmtValue(c.min) : "–"}</td>
              <td className="num">{c.max !== undefined ? fmtValue(c.max) : "–"}</td>
              <td className="num">{c.missing ? c.missing.toLocaleString() : ""}</td>
              <td className={tellsNothing(c) ? "sw-warn-txt" : "hint"}>{c.constant ? t("swConstant") : c.empty ? t("swEmpty") : c.values && c.values.length <= 8 ? c.values.join(", ") : ""}</td>
            </tr>
          );
        })}</tbody>
      </table>
    </div>
  );
}
