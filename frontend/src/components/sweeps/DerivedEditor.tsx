/* Adding a column: a formula per run ("range_m / payload_kg"), or one value per parameter set -
   an operation over its runs, optionally only some must-hold-across values ("min of range_m over
   scenario 2 and 3"). */
import { useState } from "react";
import { useT } from "../../i18n";
import { SET_OPS, type SetOp } from "../../sweeps/model";
import { useSweeps, type Study } from "../../sweeps/state";

export default function DerivedEditor({ study }: { study: Study }) {
  const t = useT();
  const [kind, setKind] = useState<"row" | "set" | null>(null);
  const [name, setName] = useState("");
  const [expr, setExpr] = useState("");
  const [op, setOp] = useState<SetOp>("min");
  const numeric = [...study.columns.filter((c) => c.kind === "number" && c.role !== "ignore").map((c) => c.name),
    ...study.question.derived.filter((d) => d.kind === "row").map((d) => d.name)];
  const [column, setColumn] = useState("");
  const [where, setWhere] = useState<Record<string, (string | number)[]>>({});
  const holds = study.columns.filter((c) => c.role === "hold");
  if (!kind) return (
    <div className="sw-row">
      <button className="btn outline" onClick={() => setKind("row")}>{t("swNewPerRun")}</button>
      <button className="btn outline" onClick={() => { setKind("set"); setColumn(numeric[0] ?? ""); }}>{t("swNewPerSet")}</button>
    </div>
  );
  const ok = name.trim() && (kind === "row" ? expr.trim() : column);
  const add = () => {
    if (!ok) return;
    const nm = name.trim();
    useSweeps.getState().addDerived(kind === "row" ? { name: nm, kind: "row", expr: expr.trim() }
      : { name: nm, kind: "set", op, column, where: Object.keys(where).length ? where : undefined });
    setKind(null); setName(""); setExpr(""); setWhere({});
  };
  return (
    <div className="sw-derived-editor">
      <label>{t("swNewName")}<input value={name} onChange={(e) => setName(e.target.value)} placeholder={kind === "row" ? "range_per_kg" : "range_hot_min"} /></label>
      {kind === "row" ? (
        <>
          <label>{t("swFormula")}<input value={expr} onChange={(e) => setExpr(e.target.value)} placeholder="range_m / payload_kg" spellCheck={false} dir="ltr" /></label>
          <p className="hint">{t("swFormulaHint")}</p>
        </>
      ) : (
        <>
          <div className="sw-row">
            <select aria-label={t("swOperation")} value={op} onChange={(e) => setOp(e.target.value as SetOp)}>{SET_OPS.map((o) => <option key={o} value={o}>{o}</option>)}</select>
            <select aria-label={t("swOfColumn")} value={column} onChange={(e) => setColumn(e.target.value)}>{numeric.map((c) => <option key={c} value={c}>{c}</option>)}</select>
          </div>
          <p className="hint">{t("swOverOnly")}</p>
          {holds.map((h) => (
            <div key={h.name} className="sw-hold-values">
              <span className="hint">{h.name}</span>
              {(h.values ?? []).map((v) => {
                const sel = where[h.name] ?? [];
                const on = sel.includes(v);
                return <button key={String(v)} className={`sw-pill${on ? " on" : ""}`} aria-pressed={on}
                  onClick={() => { const next = on ? sel.filter((x) => x !== v) : [...sel, v]; const w = { ...where }; if (next.length) w[h.name] = next; else delete w[h.name]; setWhere(w); }}>{String(v)}</button>;
              })}
            </div>
          ))}
        </>
      )}
      <div className="sw-row">
        <button className="btn primary" disabled={!ok} onClick={add}>{t("swAddColumn")}</button>
        <button className="btn" onClick={() => setKind(null)}>{t("cancel")}</button>
      </div>
    </div>
  );
}
