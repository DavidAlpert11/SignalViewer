/* The parameter sets, best first: rank and holds (kept in view), then the chosen columns -
   parameters, the goal, each condition's worst case and margin... The plot's filters and the keep
   / exclude steps apply; *only those that hold* narrows it further. A click on a header sorts by
   it (again: the other way, a third time: best first); a click on a row opens the set. What the
   table shows is what Export writes: the sets, a row each, or all their runs. In Explore (S23) it is
   given the draft's study (explore.ts draftStudy): the sets left, in the draft's order. */
import { useMemo, useState } from "react";
import { pickPath, useApp } from "../../store";
import { addedToNext } from "../../sweeps/notify";
import { useT } from "../../i18n";
import { sweepApi } from "../../sweeps/api";
import { labelOf } from "../../sweeps/scales";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import { notify, notifyError } from "../../sweeps/notify";
import { colLabel, setColumns, showKey, tableColumns, tableOptions, tableRows, TABLE_FIXED } from "../../sweeps/view";
import { openMenu } from "../Overlays";
import ColumnPicker from "./ColumnPicker";
import { exportPlot } from "./ReportStep";
import { say } from "../../sweeps/notify";
import { category } from "../../sweeps/colors";
import { failedConditions, groupMask, setIds, statuses } from "../../sweeps/groups";

const PAGE = 100;

/** `draft`: the study is Explore's draft - the table is what is left, nothing to narrow it by hand */
export default function SetsTable({ study, draft = false }: { study: Study; draft?: boolean }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const { setView } = useSweeps.getState();
  const cols = useMemo(() => setColumns(study), [study]);
  const a = study.answer!;
  const v = study.view;
  const show = useMemo(() => tableColumns(study), [study]);
  const order = useMemo(() => tableRows(study), [study]);
  const [pageWanted, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(order.length / PAGE));
  const page = Math.min(pageWanted, pages - 1);              // fewer rows now (a filter): the last page
  const rows = order.slice(page * PAGE, (page + 1) * PAGE);
  const holds = cols.get("#holds")!.values;
  const holding = useMemo(() => { let k = 0; for (let i = 0; i < holds.length; i++) k += holds[i] === 1 ? 1 : 0; return k; }, [holds]);
  const sort = v.tableSort && cols.has(v.tableSort.column) ? v.tableSort : null;
  const sortBy = (c: string) => setView({ tableSort: sort?.column !== c ? { column: c, desc: false } : !sort.desc ? { column: c, desc: true } : null });
  const arrow = (c: string) => (sort?.column === c ? (sort.desc ? " ▼" : " ▲") : "");
  const base = study.name.replace(/\.[^.]+$/, "");
  // MF00: each set's status (stripe), its groups (chips), why it fails (the holds cell's tooltip)
  const ids = useMemo(() => setIds(a), [a]);
  const status = useMemo(() => statuses(a, [], ids), [a, ids]);
  const groups = useMemo(() => v.groups ?? [], [v.groups]);
  const masks = useMemo(() => groups.map((g) => groupMask(g, a, ids)), [groups, a, ids]);
  const why = (i: number) => {
    if (status[i] === "holds") return t("swStatusHolds");
    if (status[i] === "error") return t("swStatusError");
    if (status[i] === "virtual") return t("swStatusVirtual");
    const f = failedConditions(a, i);
    return t("swStatusFails", { what: f.map((x) => (x.of > 0 ? t("swFailsKofN", { label: x.label, k: x.failed, n: x.of }) : x.label)).join("; ") });
  };
  const failing = (i: number) => new Set(failedConditions(a, i).map((x) => x.condition));

  const exportSets = async () => {
    const p = await pickPath({ mode: "save", title: t("swExportSets"), exts: [".csv"], defaultName: `${base}_sets.csv` });
    if (!p) return;
    const names = [...TABLE_FIXED, ...show];
    const labels = Object.fromEntries(names.map((c) => [c, colLabel(t, study, c)]));
    try {
      const r = await sweepApi.exportSets(study.tableId, wireQuestion(study), order, names, labels, p);
      notify(t("swExportedSets", { n: r.rows, path: r.path }));
      useSweeps.getState().journal("export", { path: r.path, n: r.rows });
    } catch (e) { notifyError(e); }
  };
  const exportRuns = async () => {
    const p = await pickPath({ mode: "save", title: t("swExportSetRuns"), exts: [".csv"], defaultName: `${base}_runs.csv` });
    if (!p) return;
    try {
      const r = await sweepApi.exportRows(study.tableId, wireQuestion(study), { sets: order }, p);
      notify(t("swExported", { n: r.rows, path: r.path }));
      useSweeps.getState().journal("export", { path: r.path, n: r.rows });
    } catch (e) { notifyError(e); }
  };
  const exportMenu = (e: React.MouseEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    openMenu({ clientX: r.left, clientY: r.bottom + 4, preventDefault() {}, stopPropagation() {} } as React.MouseEvent, [
      { label: t("swExportSetsN", { n: order.length.toLocaleString() }), run: exportSets },
      { label: t("swExportSetRunsN", { n: (order.length * a.counts.combos).toLocaleString() }), run: exportRuns },
      { label: t("swExportSetsPlotN", { n: order.length.toLocaleString() }), run: () => say(exportPlot(t, study, lang, order)) },
    ]);
  };

  return (
    <div className="sw-sets">
      <div className="sw-sets-bar">
        {!draft && <label className="sw-show" title={t("swShowHint")}>{t("swShow")}
          <select value={showKey(v)} onChange={(e) => setView({ show: e.target.value })} aria-label={t("swShow")}>
            <option value="all">{t("swShowAllSets", { n: a.counts.sets.toLocaleString() })}</option>
            <option value="holds">{t("swShowHolds", { n: holding.toLocaleString() })}</option>
            <option value="fail">{t("swShowFail", { n: (a.counts.sets - holding).toLocaleString() })}</option>
            {(v.groups ?? []).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select></label>}
        <ColumnPicker options={tableOptions(t, study)} value={show} onChange={(ids) => setView({ tableColumns: ids })}
          label={t("swColumnsOf", { n: show.length, of: tableOptions(t, study).length })} />
        {sort && <button className="linklike" onClick={() => setView({ tableSort: null })}>{t("swBestFirst")}</button>}
        <span className="hint sw-count">{t("swSetsInTable", { n: order.length.toLocaleString() })}</span>
        {pages > 1 && <span className="sw-pages">
          <button className="iconbtn" disabled={page === 0} onClick={() => setPage(page - 1)} aria-label={t("swPrevPage")}>‹</button>
          <span className="hint">{t("swPageOf", { a: page + 1, n: pages })}</span>
          <button className="iconbtn" disabled={page >= pages - 1} onClick={() => setPage(page + 1)} aria-label={t("swNextPage")}>›</button>
        </span>}
        <button className="btn outline" disabled={!order.length} onClick={exportMenu} title={t("swExportTableHint")}>{t("swExportTable")} ▾</button>
      </div>
      <div className="sw-table-wrap">
        <table className="sw-table sw-sets-table">
          {/* the re-run box, the rank and holds / fails stay in view while the table scrolls sideways */}
          <thead><tr>
            <th className="st st-0" aria-label={t("swRerun")} />
            <th className="st st-1 num sortable" onClick={() => sortBy("#rank")}>{colLabel(t, study, "#rank")}{arrow("#rank")}</th>
            <th className="st st-2 sortable" onClick={() => sortBy("#holds")}>{t("swHoldsCol")}{arrow("#holds")}</th>
            {groups.length > 0 && <th>{t("swGroupsCol")}</th>}
            {show.map((c) => <th key={c} className={`sortable ${c.startsWith("#c") ? "num cond" : c === "#goal" ? "num goal" : cols.get(c)?.kind === "num" ? "num" : ""}`}
              onClick={() => sortBy(c)}>{colLabel(t, study, c)}{arrow(c)}</th>)}
          </tr></thead>
          <tbody>
            {rows.map((i) => (
              <tr key={i} className={`${v.pinned === i ? "pinned" : ""}${holds[i] === 1 ? " holds" : ""} status-${status[i]}`} data-status={status[i]} onClick={() => setView({ pinned: i })}>
                <td className="st st-0" onClick={(e) => e.stopPropagation()}>
                  <input type="checkbox" aria-label={t("swRerunThis")} checked={v.rerun.includes(i)}
                    onChange={(e) => { setView({ rerun: e.target.checked ? [...v.rerun, i] : v.rerun.filter((x) => x !== i) }); if (e.target.checked) addedToNext(t); }} />
                </td>
                <td className="st st-1 num">{labelOf(cols.get("#rank")!, cols.get("#rank")!.values[i])}</td>
                <td className={`st st-2 ${holds[i] === 1 ? "ok" : "bad"}`} title={why(i)}>{status[i] === "virtual" ? "≈" : holds[i] === 1 ? "✓" : "✗"}</td>
                {groups.length > 0 && <td className="sw-chips">{groups.map((g, k) => masks[k][i]
                  ? <span key={g.id} className="sw-chip" style={{ background: category(g.color) }} title={g.name}>{g.name}</span> : null)}</td>}
                {show.map((c) => {
                  const col = cols.get(c)!, val = col.values[i];
                  // the condition this set fails: its cells marked (worst, margin, passed)
                  const neg = (col.part === "margin" && val < 0) || (col.condition != null && status[i] === "fails" && failing(i).has(col.condition));
                  const text = c === "#covered" ? `${val} / ${a.counts.combos}` : c === "#pareto" ? (val === 1 ? "◆" : "") : c === "#neighbours" ? (Number.isFinite(val) ? `${Math.round(val * 100)}%` : "–") : labelOf(col, val);
                  return <td key={c} className={`${col.kind === "num" ? "num" : ""}${neg ? " bad" : ""}`}>{text}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {!order.length && <p className="empty-note">{draft ? t("swExploreNone") : v.onlyHolding ? t("swNoneHoldShown") : t("swNoSetsShown")}</p>}
      </div>
    </div>
  );
}
