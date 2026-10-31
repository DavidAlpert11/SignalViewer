/* Small pieces several steps share: the shape of the study (runs, sets, combinations, what is
   missing) and adding another table (merge). */
import { useState } from "react";
import { pickPath } from "../../store";
import { useT } from "../../i18n";
import { useSweeps, type Study } from "../../sweeps/state";

export function Stat({ label, value, warn }: { label: string; value: number | string; warn?: boolean }) {
  return (
    <div className={`sw-stat${warn ? " warn" : ""}`}>
      <div className="sw-stat-value">{typeof value === "number" ? value.toLocaleString() : value}</div>
      <div className="sw-stat-label">{label}</div>
    </div>
  );
}

/** The shape for the roles as they are now - it changes as soon as a role does. */
export function ShapeStats({ study }: { study: Study }) {
  const t = useT();
  const sm = study.summary;
  return (
    <div className="sw-shape">
      <Stat label={t("swRuns")} value={sm.rows} />
      <Stat label={t("swSets")} value={sm.sets} />
      <Stat label={t("swCombos")} value={sm.combos} />
      <Stat label={t("swMissing")} value={sm.missing} warn={sm.missing > 0} />
      <Stat label={t("swFailed")} value={sm.failedRuns} warn={sm.failedRuns > 0} />
    </div>
  );
}

/** The tables in this study, and adding another - a second sweep, finer somewhere - as rows of it. */
export function MergeBox({ study }: { study: Study }) {
  const t = useT();
  const [prefer, setPrefer] = useState<"new" | "old" | "both">("new");
  const [note, setNote] = useState("");
  const add = async () => {
    const p = await pickPath({ mode: "open", title: t("swMergeTable"), exts: [".csv", ".tsv", ".txt", ".parquet", ".pq", ".xlsx", ".xls"] });
    if (!p) return;
    try { const r = await useSweeps.getState().merge(p, prefer); setNote(t("swMerged", { added: r.added, replaced: r.replaced })); }
    catch (e) { setNote((e as Error).message); }
  };
  return (
    <div className="sw-hide-box">
      <b>{t("swTables")}</b>
      <div className="sw-tags">{study.sources.map((s, i) => <span key={i} className="sw-tag">{s}</span>)}</div>
      <div className="sw-row">
        <button className="btn outline" onClick={add}>{t("swMergeTable")}</button>
        <select aria-label={t("swWhenBoth")} title={t("swWhenBoth")} value={prefer} onChange={(e) => setPrefer(e.target.value as "new" | "old" | "both")}>
          <option value="new">{t("swPreferNew")}</option><option value="old">{t("swPreferOld")}</option><option value="both">{t("swPreferBoth")}</option>
        </select>
      </div>
      {note && <span className="hint">{note}</span>}
    </div>
  );
}
