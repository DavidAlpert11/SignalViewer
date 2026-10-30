/* The parameter sets, best first: rank, parameters, the goal, each condition's worst case and
   margin, how many combinations ran. The plot's filters apply; a click opens the set. */
import { useMemo } from "react";
import { useT } from "../../i18n";
import { keptMask } from "../../sweeps/filters";
import { labelOf } from "../../sweeps/scales";
import { useSweeps, type Study } from "../../sweeps/state";
import { colLabel, setColumns } from "../../sweeps/view";

const MAX_ROWS = 300;

export default function SetsTable({ study }: { study: Study }) {
  const t = useT();
  const { setView } = useSweeps.getState();
  const cols = useMemo(() => setColumns(study), [study]);
  const a = study.answer!;
  const n = a.sets[0]?.values.length ?? 0;
  const v = study.view;
  const show = useMemo(() => {
    const names: string[] = ["#rank", ...a.sets.filter((c) => c.group === "param").map((c) => c.name)];
    if (cols.has("#goal")) names.push("#goal");
    for (const c of a.sets) if (c.group === "condition" && c.part !== "passed") names.push(c.name);
    names.push("#covered");
    return names;
  }, [a, cols]);
  const order = useMemo(() => {
    const kept = keptMask(cols, v.filters, n);
    const rank = cols.get("#rank")!.values, holds = cols.get("#holds")!.values, goal = cols.get("#goal")?.values;
    const dir = study.question.goal?.direction === "min" ? 1 : -1;
    const rows: number[] = [];
    for (let i = 0; i < n; i++) if (kept[i]) rows.push(i);
    rows.sort((x, y) => {
      const rx = Number.isFinite(rank[x]) ? rank[x] : Infinity, ry = Number.isFinite(rank[y]) ? rank[y] : Infinity;
      if (rx !== ry) return rx - ry;
      if (holds[x] !== holds[y]) return holds[y] - holds[x];
      if (goal) { const gx = goal[x], gy = goal[y]; if (gx !== gy) return Number.isFinite(gx) ? (Number.isFinite(gy) ? dir * (gx - gy) : -1) : 1; }
      return x - y;
    });
    return rows;
  }, [cols, v.filters, n, study.question.goal]);
  const rows = order.slice(0, MAX_ROWS);
  const holds = cols.get("#holds")!.values;
  return (
    <div className="sw-table-wrap">
      <table className="sw-table">
        <thead><tr>
          <th aria-label={t("swRerun")} />
          {show.map((c) => <th key={c} className={c.startsWith("#c") ? "num cond" : c === "#goal" ? "num goal" : ""}>{colLabel(t, study, c)}</th>)}
          <th>{t("swHoldsCol")}</th>
        </tr></thead>
        <tbody>
          {rows.map((i) => (
            <tr key={i} className={`${v.pinned === i ? "pinned" : ""}${holds[i] === 1 ? " holds" : ""}`} onClick={() => setView({ pinned: i })}>
              <td onClick={(e) => e.stopPropagation()}>
                <input type="checkbox" aria-label={t("swRerunThis")} checked={v.rerun.includes(i)}
                  onChange={(e) => setView({ rerun: e.target.checked ? [...v.rerun, i] : v.rerun.filter((x) => x !== i) })} />
              </td>
              {show.map((c) => {
                const col = cols.get(c)!, val = col.values[i];
                const neg = col.part === "margin" && val < 0;
                return <td key={c} className={`${col.kind === "num" ? "num" : ""}${neg ? " bad" : ""}`}>{c === "#covered" ? `${val} / ${a.counts.combos}` : labelOf(col, val)}</td>;
              })}
              <td className={holds[i] === 1 ? "ok" : "bad"}>{holds[i] === 1 ? "✓" : "✗"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {order.length > MAX_ROWS && <p className="hint sw-more">{t("swMoreRows", { n: (order.length - MAX_ROWS).toLocaleString() })}</p>}
    </div>
  );
}
