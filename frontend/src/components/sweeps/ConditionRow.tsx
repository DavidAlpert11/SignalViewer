/* A condition: column, comparison, limit, and where it must be met - in every combination, in at
   least k, or in every combination of some values. */
import { useT } from "../../i18n";
import { OPS, type Condition, type Op } from "../../sweeps/model";
import { useSweeps, type Study } from "../../sweeps/state";

export default function ConditionRow({ study, i, c, outputs, met }: { study: Study; i: number; c: Condition; outputs: string[]; met?: number }) {
  const t = useT();
  const st = useSweeps.getState();
  const holds = study.columns.filter((x) => x.role === "hold");
  const up = (p: Partial<Condition>) => st.updateCondition(i, p);
  return (
    <div className="sw-cond">
      <div className="sw-cond-line">
        <select aria-label={t("swCondColumn")} value={c.column} onChange={(e) => up({ column: e.target.value })}>
          {outputs.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
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
