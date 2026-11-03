/* Split by (owner's spec 2026-11-02): a condition studied value by value - "the best set for a
   payload of 0.5 against the best for 1.5", with the same goal. Above the results' tabs: All
   together | each value; a value recomputes everything for it (a set must hold in every combination
   of the other conditions with that value). Below it, the best set per value side by side; a click
   on a row shows that value. */
import { useEffect, useState } from "react";
import { useT } from "../../i18n";
import { fmtValue } from "../../sweeps/scales";
import { splitRows, splitValues, type SplitRow } from "../../sweeps/split";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import { notify } from "../../sweeps/notify";

export default function SplitBar({ study }: { study: Study }) {
  const t = useT();
  const col = study.question.split!;
  const values = splitValues(study);
  const cur = study.view.splitValue ?? null;
  const st = useSweeps.getState();
  const [rows, setRows] = useState<SplitRow[] | null>(null);
  const [open, setOpen] = useState(false);
  const key = JSON.stringify([study.tableId, wireQuestion({ ...study, view: { ...study.view, splitValue: null } }), values]);
  useEffect(() => {
    if (!open) return;
    let live = true;
    setRows(null);
    splitRows(study).then((r) => live && setRows(r)).catch(() => live && setRows([]));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, open]);
  const pill = (v: string | number | null, label: string) => (
    <button key={String(v)} className={`sw-pill${cur === v ? " on" : ""}`} aria-pressed={cur === v} onClick={() => st.setSplitValue(v)}>{label}</button>
  );
  return (
    <div className="sw-split">
      <div className="sw-row sw-split-bar" role="group" aria-label={t("swSplitBy", { c: col })}>
        <b className="sw-ellipsis" title={col}>{col}:</b>
        {pill(null, t("swAllTogether"))}
        {values.map((v) => pill(v, String(v)))}
        <button className="linklike" aria-expanded={open} onClick={() => setOpen(!open)}>{t(open ? "swSplitHideCompare" : "swSplitCompare")}</button>
      </div>
      {open && (
        <div className="sw-table-wrap sw-split-table">
          {!rows ? <p className="hint">{t("swReading")}</p> : (
            <table className="sw-table">
              <thead><tr><th>{col}</th><th>{t("swSplitHolding")}</th><th>{t("swSplitBest")}</th><th>{t("swSplitBestSet")}</th></tr></thead>
              <tbody>{rows.map((r) => (
                <tr key={String(r.value)} className={cur === r.value ? "pinned" : ""} onClick={() => st.setSplitValue(r.value)}>
                  <td>{r.value === null ? t("swAllTogether") : String(r.value)}</td>
                  <td className="num">{r.holding.toLocaleString()} / {r.sets.toLocaleString()}</td>
                  <td className="num">{r.best === null || !Number.isFinite(r.best) ? "–" : fmtValue(r.best)}</td>
                  <td className="mono sw-ellipsis" title={r.set}>{r.set || "–"}</td>
                </tr>
              ))}</tbody>
            </table>
          )}
          {rows && rows.length > 1 && (
            <button className="btn outline sm sw-split-groups" title={t("swSplitGroupsHint")} onClick={() => {
              const st2 = useSweeps.getState();
              for (const r of rows.slice(1)) st2.addIdsGroup(`${col} = ${r.value}`, r.holds);
              notify(t("swSplitGroupsMade", { n: rows.length - 1 }));
            }}>{t("swSplitGroups")}</button>
          )}
        </div>
      )}
    </div>
  );
}
