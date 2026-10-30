/* The data's health before trusting an answer: what is missing, what gave no result, and runs that
   look wrong - an output far from its neighbours' in the same combination. A run can be left out
   (then its combination counts as missing, so its set asks to be run again). */
import { useEffect, useState } from "react";
import { useT } from "../../i18n";
import { sweepApi, type Suspect } from "../../sweeps/api";
import { fmtValue } from "../../sweeps/scales";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";

export default function HealthView({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const [sus, setSus] = useState<Suspect[] | null>(null);
  const [err, setErr] = useState("");
  const qk = JSON.stringify({ ...wireQuestion(study), exclude: [] });
  useEffect(() => {
    let live = true;
    sweepApi.suspects(study.tableId, wireQuestion(study)).then((r) => live && setSus(r.suspects)).catch((e) => live && setErr((e as Error).message));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [study.tableId, qk]);
  const sm = study.summary, ex = study.question.exclude;
  const toggle = (row: number, on: boolean) => st.setQuestion({ exclude: on ? [...ex, row] : ex.filter((r) => r !== row) });
  return (
    <div className="sw-health">
      <div className="sw-shape">
        <div className="sw-stat"><div className="sw-stat-value">{sm.sets.toLocaleString()}</div><div className="sw-stat-label">{t("swSets")}</div></div>
        <div className={`sw-stat${sm.missing ? " warn" : ""}`}><div className="sw-stat-value">{sm.missing.toLocaleString()}</div><div className="sw-stat-label">{t("swMissing")}</div></div>
        <div className={`sw-stat${sm.failedRuns ? " warn" : ""}`}><div className="sw-stat-value">{sm.failedRuns.toLocaleString()}</div><div className="sw-stat-label">{t("swFailed")}</div></div>
        <div className={`sw-stat${sm.duplicates ? " warn" : ""}`}><div className="sw-stat-value">{sm.duplicates.toLocaleString()}</div><div className="sw-stat-label">{t("swDuplicatesShort")}</div></div>
        <div className={`sw-stat${sus?.length ? " warn" : ""}`}><div className="sw-stat-value">{sus ? sus.length : "…"}</div><div className="sw-stat-label">{t("swSuspects")}</div></div>
        <div className="sw-stat"><div className="sw-stat-value">{ex.length}</div><div className="sw-stat-label">{t("swLeftOut")}</div></div>
      </div>
      <p className="hint">{t("swSuspectsHint")}</p>
      {err && <p className="sw-error">{err}</p>}
      {sus && sus.length > 0 && (
        <>
          <div className="sw-row">
            <button className="btn outline" onClick={() => st.setQuestion({ exclude: [...new Set([...ex, ...sus.map((s) => s.row)])] })}>{t("swLeaveAllOut")}</button>
            {ex.length > 0 && <button className="btn" onClick={() => st.setQuestion({ exclude: [] })}>{t("swKeepAll")}</button>}
          </div>
          <div className="sw-table-wrap">
            <table className="sw-table">
              <thead><tr><th>{t("swLeaveOut")}</th><th>{t("swCondColumn")}</th><th className="num">{t("swValue")}</th><th className="num">{t("swNeighboursGave")}</th>
                <th>{t("swCombination")}</th><th>{t("swSetCol")}</th><th className="num">{t("swHowOdd")}</th></tr></thead>
              <tbody>{sus.map((s, i) => (
                <tr key={i} onClick={() => st.setView({ pinned: s.set, center: "lines" })}>
                  <td onClick={(e) => e.stopPropagation()}><input type="checkbox" aria-label={t("swLeaveOut")} checked={ex.includes(s.row)} onChange={(e) => toggle(s.row, e.target.checked)} /></td>
                  <td>{s.column}</td><td className="num bad">{fmtValue(s.value ?? NaN)}</td><td className="num">{fmtValue(s.expected ?? NaN)}</td>
                  <td>{Object.values(s.where).join(" · ")}</td><td>{Object.values(s.params).join(" · ")}</td><td className="num">{s.z.toFixed(1)}×</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </>
      )}
      {sus && !sus.length && <p className="hint">{t("swNoSuspects")}</p>}
    </div>
  );
}
