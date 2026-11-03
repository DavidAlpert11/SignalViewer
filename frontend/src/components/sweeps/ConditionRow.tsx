/* A condition: column, comparison, limit, and where it must be met - in every combination, in at
   least k, or in every combination of some values. */
import { useT } from "../../i18n";
import { OPS, condText, type Condition, type Op } from "../../sweeps/model";
import { useSweeps, type Study } from "../../sweeps/state";
import { activeColumns, columnChoices } from "../../sweeps/view";
import ColumnSearch from "./ColumnSearch";

export default function ConditionRow({ study, i, c, outputs, met }: { study: Study; i: number; c: Condition; outputs: string[]; met?: number }) {
  const t = useT();
  const st = useSweeps.getState();
  const params = activeColumns(study, "param");
  const active = new Set(activeColumns(study, "hold"));
  const holds = study.columns.filter((x) => active.has(x.name));
  const up = (p: Partial<Condition>) => st.updateCondition(i, p);
  // the columns other conditions of this goal use come first in the search
  const g = study.question.goals[study.question.active];
  const used = [...new Set([...(g?.conditions ?? []).map((x) => x.column), ...(g?.optimize ?? []).map((o) => o.column)])];
  // a categorical parameter's levels (MF01, chosen in Explore or the problem table): shown, removable
  if (c.in) return (
    <div className="sw-cond">
      <div className="sw-cond-line">
        <span className="mono">{condText(c)}</span>{met !== undefined && <span className="hint">{t("swMetBy", { n: met })}</span>}
        <button className="iconbtn" aria-label={t("swRemove")} onClick={() => st.removeCondition(i)}>×</button>
      </div>
    </div>
  );
  return (
    <div className="sw-cond">
      <div className="sw-cond-line">
        {/* typed: part of the name finds it; an output, or a parameter (a limit on one, S21) */}
        <ColumnSearch label={t("swCondColumn")} value={c.column} used={used} onChange={(column) => up({ column })}
          options={columnChoices(study, ["output", "param"]).filter((o) => o.role !== "param" || params.includes(o.name))
            .filter((o) => o.role === "param" || outputs.includes(o.name))} />
        <select aria-label={t("swCondOp")} value={c.op} onChange={(e) => up({ op: e.target.value as Op })}>
          {OPS.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
        <input type="number" aria-label={t("swCondValue")} defaultValue={c.value} key={`${i}:${c.value}`}
          onBlur={(e) => { const v = Number(e.target.value); if (Number.isFinite(v) && v !== c.value) up({ value: v }); }}
          onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
        <button className="iconbtn" aria-label={t("swRemove")} onClick={() => st.removeCondition(i)}>×</button>
      </div>
      <div className="sw-cond-line">
        <select aria-label={t("swCondWhere")} value={c.mode} onChange={(e) => up({ mode: e.target.value as Condition["mode"] })}>
          <option value="all">{t("swInAll")}</option>
          <option value="atLeast">{t("swAtLeast")}</option>
          <option value="only">{t("swOnlyIn")}</option>
        </select>
        {c.mode === "atLeast" && (
          <input type="number" min={1} aria-label={t("swAtLeastK")} defaultValue={c.k ?? 1} key={`k${i}:${c.k}`}
            onBlur={(e) => up({ k: Math.max(1, Math.round(Number(e.target.value) || 1)) })} />
        )}
        {met !== undefined && <span className="hint">{t("swMetBy", { n: met })}</span>}
      </div>
      {c.mode === "only" && holds.map((h) => (
        <div key={h.name} className="sw-hold-values">
          <span className="hint">{h.name}</span>
          {(h.values ?? []).map((v) => {
            const sel = c.where?.[h.name] ?? [];
            const on = sel.includes(v);
            return <button key={String(v)} className={`sw-pill${on ? " on" : ""}`} aria-pressed={on}
              onClick={() => up({ where: { ...(c.where ?? {}), [h.name]: on ? sel.filter((x) => x !== v) : [...sel, v] } })}>{String(v)}</button>;
          })}
        </div>
      ))}
    </div>
  );
}
