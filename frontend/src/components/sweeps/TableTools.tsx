/* S2 (PLAN_2026-11-17 §2b): the table's own tools, in the Columns step's side panel. Each one is a step of
   the study (saved with it, one Undo each, the file on disk never changes): drop every *Not used* column
   (and bring them back), keep only the runs where a condition holds, a column's display name and unit,
   and values fixed by hand. Export (the Data step's table menu) writes the table as edited. */
import { useState } from "react";
import { useT } from "../../i18n";
import { Icon } from "../../icons";
import type { CellFix } from "../../sweeps/model";
import { useSweeps, type Study } from "../../sweeps/state";

export default function TableTools({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const q = study.question;
  const removed = new Set(q.removed);
  const unused = study.columns.filter((c) => c.role === "ignore" && !removed.has(c.name)).map((c) => c.name);
  const names = study.columns.filter((c) => !removed.has(c.name)).map((c) => c.name);
  const [filter, setFilter] = useState(q.rowFilter ?? "");
  const [col, setCol] = useState(names[0] ?? "");
  const [label, setLabel] = useState(q.labels?.[col] ?? "");
  const [unit, setUnit] = useState(q.units?.[col] ?? "");
  const [cell, setCell] = useState<{ row: string; column: string; value: string }>({ row: "", column: names[0] ?? "", value: "" });
  const pick = (c: string) => { setCol(c); setLabel(q.labels?.[c] ?? ""); setUnit(q.units?.[c] ?? ""); };
  const without = (m: Record<string, string> | undefined, k: string, v: string) => {
    const r = { ...(m ?? {}) };
    if (v.trim()) r[k] = v.trim(); else delete r[k];
    return r;
  };
  const named = Object.keys({ ...(q.labels ?? {}), ...(q.units ?? {}) });
  const cells = q.cells ?? [];
  const n = (q.rowFilter ? 1 : 0) + named.length + cells.length + q.removed.length;
  const kind = study.columns.find((c) => c.name === cell.column)?.kind;
  const addCell = () => {
    const row = Number(cell.row);
    if (!Number.isInteger(row) || row < 0 || !cell.column) return;
    const value: CellFix["value"] = cell.value.trim() === "" ? null : kind === "number" ? Number(cell.value) : cell.value;
    if (typeof value === "number" && !Number.isFinite(value)) return;
    st.editTable({ cells: [...cells.filter((c) => !(c.row === row && c.column === cell.column)), { row, column: cell.column, value }] });
    setCell({ ...cell, row: "", value: "" });
  };
  return (
    <details className="sw-fold sw-table-tools">
      <summary><b>{t("swTableTools")}</b> <span className="hint">{n || ""}</span></summary>
      <p className="hint">{t("swTableToolsHint")}</p>
      <div className="sw-row">
        <button className="btn outline" disabled={!unused.length} onClick={() => st.setRemoved([...q.removed, ...unused])}>{t("swDropUnused", { n: unused.length })}</button>
        {q.removed.length > 0 && <button className="btn" onClick={() => st.setRemoved([])}>{t("swBringBack", { n: q.removed.length })}</button>}
      </div>
      <label>{t("swKeepWhere")}
        <input value={filter} dir="ltr" spellCheck={false} placeholder="crashed == 0" onChange={(e) => setFilter(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") st.editTable({ rowFilter: filter.trim() || undefined }); }}
          onBlur={() => { if ((q.rowFilter ?? "") !== filter.trim()) st.editTable({ rowFilter: filter.trim() || undefined }); }} />
      </label>
      <div className="sw-tt-group">
        <span className="hint">{t("swNameUnit")}</span>
        <div className="sw-row">
          <select aria-label={t("swColumn")} value={col} onChange={(e) => pick(e.target.value)}>{names.map((c) => <option key={c} value={c}>{c}</option>)}</select>
          <input aria-label={t("swShownName")} placeholder={t("swShownName")} value={label} onChange={(e) => setLabel(e.target.value)} />
          <input aria-label={t("swUnit")} placeholder={t("swUnit")} value={unit} size={5} onChange={(e) => setUnit(e.target.value)} />
          <button className="btn" disabled={!col} onClick={() => st.editTable({ labels: without(q.labels, col, label), units: without(q.units, col, unit) })}>{t("swApply")}</button>
        </div>
        {named.map((c) => (
          <div key={c} className="sw-derived"><span className="sw-ellipsis">{c} → <b>{q.labels?.[c] || c}{q.units?.[c] ? ` [${q.units[c]}]` : ""}</b></span>
            <button className="iconbtn sm" aria-label={t("swUndoName", { n: c })} title={t("swUndoName", { n: c })}
              onClick={() => st.editTable({ labels: without(q.labels, c, ""), units: without(q.units, c, "") })}><Icon.X width={12} height={12} /></button></div>
        ))}
      </div>
      <div className="sw-tt-group">
        <span className="hint">{t("swFixValue")}</span>
        <div className="sw-row">
          <input aria-label={t("swRunRow")} placeholder={t("swRunRow")} inputMode="numeric" size={5} value={cell.row} onChange={(e) => setCell({ ...cell, row: e.target.value })} />
          <select aria-label={t("swColumn")} value={cell.column} onChange={(e) => setCell({ ...cell, column: e.target.value })}>{names.map((c) => <option key={c} value={c}>{c}</option>)}</select>
          <input aria-label={t("swValue")} placeholder={t("swValue")} size={7} value={cell.value} onChange={(e) => setCell({ ...cell, value: e.target.value })}
            onKeyDown={(e) => { if (e.key === "Enter") addCell(); }} />
          <button className="btn" onClick={addCell}>{t("swApply")}</button>
        </div>
        {cells.map((c) => (
          <div key={`${c.row}/${c.column}`} className="sw-derived"><span className="sw-ellipsis">#{c.row} · {c.column} = <b>{c.value === null ? "–" : String(c.value)}</b></span>
            <button className="iconbtn sm" aria-label={t("swUndoFix", { n: c.row })} title={t("swUndoFix", { n: c.row })}
              onClick={() => st.editTable({ cells: cells.filter((x) => x !== c) })}><Icon.X width={12} height={12} /></button></div>
        ))}
      </div>
    </details>
  );
}
