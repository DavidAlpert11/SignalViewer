/* One parameter set, on the right: its parameters, why it fails (which condition, in which
   combination, by how much), and every run of it - the cells that break a condition marked. */
import { useEffect, useState } from "react";
import { useT } from "../../i18n";
import { sweepApi, type SetDetail as Detail } from "../../sweeps/api";
import type { Condition } from "../../sweeps/model";
import { fmtValue } from "../../sweeps/scales";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import { useApp } from "../../store";
import { openPaths } from "../../files";

const breaks = (c: Condition, v: unknown) => {
  if (typeof v !== "number" || !Number.isFinite(v)) return true;
  switch (c.op) { case ">=": return !(v >= c.value); case "<=": return !(v <= c.value); case ">": return !(v > c.value);
    case "<": return !(v < c.value); case "==": return v !== c.value; default: return v === c.value; }
};

export default function SetDetail({ study, set }: { study: Study; set: number }) {
  const t = useT();
  const { setView } = useSweeps.getState();
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState("");
  const qKey = JSON.stringify(wireQuestion(study));
  useEffect(() => {
    let live = true;
    setErr("");
    sweepApi.set(study.tableId, wireQuestion(study), set).then((r) => { if (live) setD(r); }).catch((e) => { if (live) setErr((e as Error).message); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [study.tableId, set, qKey]);
  const col = (name: string) => study.answer?.sets.find((c) => c.name === name)?.values[set];
  const holds = col("#holds") === 1;
  const share = col("#neighbours"), tol = col("#tolerance");
  const openRecordings = (paths: string[]) => {
    useApp.setState({ area: "recordings" });
    openPaths(paths, undefined, { autoView: true });
  };
  const inRerun = study.view.rerun.includes(set);
  const conds = study.question.conditions;
  return (
    <aside className="side sw-detail" aria-label={t("swSetDetail")}>
      <div className="side-head">
        <h2>{t("swSetDetail")}</h2>
        <span className={holds ? "sw-badge ok" : "sw-badge bad"}>{holds ? t("swHolds") : t("swFails")}</span>
        <button className="iconbtn" aria-label={t("swCloseDetail")} onClick={() => setView({ pinned: null })}>×</button>
      </div>
      {err && <p className="sw-error">{err}</p>}
      {d && (
        <div className="sw-detail-body">
          <dl className="sw-params">{Object.entries(d.params).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v === null ? "–" : String(v)}</dd></div>)}</dl>
          {d.missingCombos > 0 && <p className="sw-warn">{t("swMissingCombos", { n: d.missingCombos })}</p>}
          <div className="sw-row hint">
            {share !== undefined && Number.isFinite(share) && <span title={t("swNeighboursHint")}>{t("swNeighboursHold", { p: Math.round(share * 100) })}</span>}
            {holds && tol !== undefined && Number.isFinite(tol) && <span title={t("swToleranceHint")}>· {t("swToleranceSteps", { n: tol })}</span>}
          </div>
          {d.why.length > 0 && (
            <div className="sw-why">
              <h3>{t("swWhy")}</h3>
              {d.why.map((w, i) => (
                <p key={i}>
                  <b>{conds[w.condition] ? `${conds[w.condition].column} ${conds[w.condition].op} ${conds[w.condition].value}` : w.column}</b>
                  {" · "}{t("swBrokenIn", { n: w.broken, of: w.of })}
                  {w.noResult ? ` · ${t("swNoResult")}` : w.worst !== null ? ` · ${t("swWorstAt", { v: fmtValue(w.worst) })}` : ""}
                  {w.where && Object.keys(w.where).length > 0 && <span className="hint"> {Object.values(w.where).join(" · ")}</span>}
                </p>
              ))}
            </div>
          )}
          <div className="sw-runs-wrap">
            <table className="sw-table sw-runs">
              <thead><tr>{d.recordings.length > 0 && <th />}{d.columns.map((c) => <th key={c} className={d.holds.includes(c) ? "hold" : "num"}>{c}</th>)}</tr></thead>
              <tbody>{d.runs.map((r, i) => (
                <tr key={i}>
                  {d.recordings.length > 0 && <td>{d.recordingPerRun[i] && (
                    <button className="iconbtn" aria-label={t("swOpenRun")} title={`${t("swOpenRun")}: ${d.recordingPerRun[i]}`}
                      onClick={() => openRecordings([d.recordingPerRun[i]!])}>↗</button>)}</td>}
                  {r.map((v, j) => {
                  const c = d.columns[j];
                  const bad = conds.some((cd) => cd.column === c && cd.mode !== "only" && breaks(cd, v));
                  return <td key={j} className={`${typeof v === "number" ? "num" : ""}${bad ? " bad" : ""}`}>{v === null ? "–" : typeof v === "number" ? fmtValue(v) : String(v)}</td>;
                })}</tr>
              ))}</tbody>
            </table>
          </div>
          {d.recordings.length > 0
            ? <button className="btn outline" onClick={() => openRecordings(d.recordings)}>{t("swOpenRecordings", { n: d.recordings.length })}</button>
            : <p className="hint">{t("swNoRecordings")}</p>}
          <button className={`btn ${inRerun ? "outline" : "primary"}`} onClick={() => setView({ rerun: inRerun ? study.view.rerun.filter((x) => x !== set) : [...study.view.rerun, set] })}>
            {inRerun ? t("swRemoveFromRerun") : t("swAddToRerun")}
          </button>
        </div>
      )}
    </aside>
  );
}
