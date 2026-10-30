/* Two studies of the same parameter sets - before and after a change - asked the same question:
   which sets now hold, which no longer do, and how the goal moved. */
import { useEffect, useState } from "react";
import { useT } from "../../i18n";
import { sweepApi, type CompareResult } from "../../sweeps/api";
import { fmtValue } from "../../sweeps/scales";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";

export default function CompareView({ study }: { study: Study }) {
  const t = useT();
  const studies = useSweeps((s) => s.studies);
  const others = studies.filter((s) => s.tableId !== study.tableId);
  const [other, setOther] = useState(others[0]?.tableId ?? "");
  const [r, setR] = useState<CompareResult | null>(null);
  const [err, setErr] = useState("");
  const [onlyChanged, setOnlyChanged] = useState(true);
  const qk = JSON.stringify(wireQuestion(study));
  useEffect(() => {
    const b = studies.find((s) => s.tableId === other);
    if (!b) return;
    let live = true;
    setErr("");
    // the same question asked of both: this study's question, with the other table's own roles
    const q = wireQuestion(study);
    const qb = { ...q, roles: wireQuestion(b).roles, exclude: [] };
    sweepApi.compare({ id: study.tableId, question: q }, { id: b.tableId, question: qb }).then((x) => live && setR(x)).catch((e) => live && setErr((e as Error).message));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qk, other]);
  const rows = (r?.rows ?? []).filter((x) => !onlyChanged || x.holdsA !== x.holdsB || (x.delta ?? 0) !== 0);
  return (
    <div className="sw-compare">
      <div className="sw-row">
        <label>{t("swCompareWith")} <select value={other} onChange={(e) => setOther(e.target.value)}>{others.map((s) => <option key={s.tableId} value={s.tableId}>{s.name}</option>)}</select></label>
        <label className="acheck"><input type="checkbox" checked={onlyChanged} onChange={(e) => setOnlyChanged(e.target.checked)} />{t("swOnlyChanged")}</label>
      </div>
      {err && <p className="sw-error">{err}</p>}
      {r && (
        <>
          <div className="sw-shape">
            <div className="sw-stat"><div className="sw-stat-value">{r.matched}</div><div className="sw-stat-label">{t("swMatched")}</div></div>
            <div className="sw-stat"><div className="sw-stat-value sw-ok">{r.nowHold}</div><div className="sw-stat-label">{t("swNowHold")}</div></div>
            <div className={`sw-stat${r.noLongerHold ? " warn" : ""}`}><div className="sw-stat-value">{r.noLongerHold}</div><div className="sw-stat-label">{t("swNoLongerHold")}</div></div>
            <div className="sw-stat"><div className="sw-stat-value">{r.onlyA + r.onlyB}</div><div className="sw-stat-label">{t("swInOneOnly")}</div></div>
          </div>
          <div className="sw-table-wrap">
            <table className="sw-table">
              <thead><tr>{Object.keys(r.rows[0]?.params ?? {}).map((c) => <th key={c}>{c}</th>)}<th>{study.name}</th><th>{others.find((s) => s.tableId === other)?.name}</th>
                {study.question.goal && <><th className="num">{t("swGoal")} A</th><th className="num">{t("swGoal")} B</th><th className="num">Δ</th></>}</tr></thead>
              <tbody>{rows.slice(0, 500).map((x, i) => (
                <tr key={i}>{Object.values(x.params).map((v, j) => <td key={j}>{v === null ? "–" : String(v)}</td>)}
                  <td className={x.holdsA ? "ok" : "bad"}>{x.holdsA ? "✓" : "✗"}</td><td className={x.holdsB ? "ok" : "bad"}>{x.holdsB ? "✓" : "✗"}</td>
                  {study.question.goal && <><td className="num">{fmtValue(x.goalA ?? NaN)}</td><td className="num">{fmtValue(x.goalB ?? NaN)}</td>
                    <td className={`num${(x.delta ?? 0) * (study.question.goal!.direction === "max" ? 1 : -1) < 0 ? " bad" : ""}`}>{fmtValue(x.delta ?? NaN)}</td></>}</tr>
              ))}</tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
