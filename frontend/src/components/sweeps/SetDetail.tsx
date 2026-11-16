/* One parameter set, on the right: its parameters, why it fails (which condition, in which
   combination, by how much), and every run of it - the cells that break a condition marked. */
import { useEffect, useState } from "react";
import { addedToNext } from "../../sweeps/notify";
import { inRerun as inRerunNow } from "../../sweeps/split";
import { useT } from "../../i18n";
import { sweepApi, type SetDetail as Detail } from "../../sweeps/api";
import type { Condition, RecordingsPlace } from "../../sweeps/model";
import { fmtValue } from "../../sweeps/scales";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import { pickPath } from "../../store";
import { openRecordings } from "../../folderSummary";

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
  const [recErr, setRecErr] = useState("");
  const rec = study.question.recordings?.folder ? study.question.recordings : undefined;
  const qKey = JSON.stringify(wireQuestion(study));
  const recKey = JSON.stringify(rec ?? null);
  useEffect(() => {
    let live = true;
    setErr(""); setRecErr("");
    const q = wireQuestion(study);
    // the recordings' folder is looked in only now; a wrong folder or pattern is said, the rest still shows
    sweepApi.set(study.tableId, q, set, rec)
      .catch((e) => { if (!rec) throw e; if (live) setRecErr((e as Error).message); return sweepApi.set(study.tableId, q, set); })
      .then((r) => { if (live) setD(r); }).catch((e) => { if (live) setErr((e as Error).message); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [study.tableId, set, qKey, recKey]);
  const col = (name: string) => study.answer?.sets.find((c) => c.name === name)?.values[set];
  const holds = col("#holds") === 1;
  const share = col("#neighbours"), tol = col("#tolerance");
  const inRerun = inRerunNow(study, set);
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
            : !rec && <p className="hint">{t("swNoRecordings")}</p>}
          {rec && d.notFound && d.notFound.length > 0 && <p className="sw-warn">{t("swRecNotFound", { folder: `\u2066${rec.folder}\u2069`, names: `\u2066${d.notFound.join(", ")}\u2069` })}</p>}
          {recErr && <p className="sw-error">{recErr}</p>}
          {(rec || d.recordings.length === 0) && <RecordingsFinder place={rec} />}
          <button className={`btn ${inRerun ? "outline" : "primary"}`} onClick={() => { useSweeps.getState().toggleRerun(set); if (!inRerun) addedToNext(t); }}>
            {inRerun ? t("swRemoveFromRerun") : t("swAddToRerun")}
          </button>
        </div>
      )}
    </aside>
  );
}

/** M3: where the runs' recordings are when the table has no recording column - a folder and a file name made from
 *  the row, saved in the study (one Undo); each run's file is looked for only when a set is shown. */
function RecordingsFinder({ place }: { place?: RecordingsPlace }) {
  const t = useT();
  const [pattern, setPattern] = useState(place?.pattern ?? "");
  useEffect(() => setPattern(place?.pattern ?? ""), [place?.pattern]);
  const save = (p: RecordingsPlace | undefined) => useSweeps.getState().setQuestion({ recordings: p });
  const choose = async () => {
    const folder = await pickPath({ mode: "folder", title: t("swRecFind") });
    if (folder) save({ folder, pattern });
  };
  return (
    <details className="sw-rec-find" open={!place}>
      <summary>{t("swRecFind")}</summary>
      <div className="sw-row">
        <span>{t("swRecFolder")}</span>
        <bdi className="sw-ellipsis hint" dir="ltr" title={place?.folder}>{place?.folder ?? "–"}</bdi>
        <button className="btn sm" onClick={() => { void choose(); }}>{t("swRecChoose")}</button>
      </div>
      <label className="sw-row">
        <span>{t("swRecPattern")}</span>
        <input className="input" dir="ltr" value={pattern} placeholder="flight_{run_id}.bin" aria-label={t("swRecPattern")}
          onChange={(e) => setPattern(e.target.value)}
          onBlur={() => { if (place && pattern !== place.pattern) save({ ...place, pattern }); }}
          onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
      </label>
      <p className="hint">{t("swRecPatternHint")}</p>
      {place && <button className="btn sm outline" onClick={() => save(undefined)}>{t("swRecForget")}</button>}
    </details>
  );
}
