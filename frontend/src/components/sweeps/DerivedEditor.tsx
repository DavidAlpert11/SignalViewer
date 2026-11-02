/* Adding (or changing) a column: a formula per run ("range_m / payload_kg"), or one value per
   parameter set - an operation over its runs, optionally only some condition values ("min of
   range_m over scenario 2 and 3"). The formula completes column names (with their role and kind)
   and functions (with what they do) as it is typed - Tab or Enter takes the one marked, a name with
   spaces comes as col("...") - and shows its value in the first run, or what is wrong. */
import { useEffect, useMemo, useRef, useState } from "react";
import { useT, type TKey } from "../../i18n";
import { sweepApi } from "../../sweeps/api";
import { SET_OPS, type Derived, type SetOp } from "../../sweeps/model";
import { fmtValue } from "../../sweeps/scales";
import { useSweeps, type Study } from "../../sweeps/state";
import { groupLabel } from "../../sweeps/view";

/** the formula's functions (svcore/sweep/derived.py `_FUN`), each with its line of help */
const FUNCS: { name: string; key: TKey }[] = [
  { name: "abs", key: "swFnAbs" }, { name: "sqrt", key: "swFnSqrt" }, { name: "exp", key: "swFnExp" }, { name: "log", key: "swFnLog" },
  { name: "log10", key: "swFnLog10" }, { name: "min", key: "swFnMin" }, { name: "max", key: "swFnMax" }, { name: "clip", key: "swFnClip" },
  { name: "where", key: "swFnWhere" }, { name: "round", key: "swFnRound" }, { name: "floor", key: "swFnFloor" }, { name: "ceil", key: "swFnCeil" },
  { name: "sign", key: "swFnSign" }, { name: "isnan", key: "swFnIsnan" }, { name: "sin", key: "swFnTrig" }, { name: "cos", key: "swFnTrig" },
  { name: "tan", key: "swFnTrig" }, { name: "atan2", key: "swFnAtan2" },
];
const IDENT = /^[A-Za-z_][A-Za-z0-9_]*$/;
const MAX_SUGG = 8;

interface Sugg { insert: string; label: string; detail: string; fn: boolean }

export default function DerivedEditor({ study, edit, onDone }: { study: Study; edit?: { i: number; d: Derived }; onDone?: () => void }) {
  const t = useT();
  const init = edit?.d;
  const [kind, setKind] = useState<"row" | "set">(init?.kind ?? "row");
  const [name, setName] = useState(init?.name ?? "");
  const [expr, setExpr] = useState(init?.kind === "row" ? init.expr : "");
  const [op, setOp] = useState<SetOp>(init?.kind === "set" ? init.op : "min");
  const others = study.question.derived.filter((_, j) => j !== edit?.i);
  const numeric = [...study.columns.filter((c) => c.kind === "number" && c.role !== "ignore").map((c) => c.name),
    ...others.filter((d) => d.kind === "row").map((d) => d.name)];
  const [column, setColumn] = useState(init?.kind === "set" ? init.column : numeric[0] ?? "");
  const [where, setWhere] = useState<Record<string, (string | number)[]>>(init?.kind === "set" ? init.where ?? {} : {});
  const holds = study.columns.filter((c) => c.role === "hold");
  // completion: the word being typed at the caret
  const input = useRef<HTMLInputElement>(null);
  const [caret, setCaret] = useState(0);
  const [at, setAt] = useState(0);
  const [open, setOpen] = useState(false);
  const word = useMemo(() => {
    const before = expr.slice(0, caret);
    const c = /col\(\s*"([^"]*)$/.exec(before);                   // inside col("...): any name
    if (c) return { text: c[1], start: c.index, inCol: true };
    const m = /[A-Za-z_][A-Za-z0-9_]*$/.exec(before);
    return m ? { text: m[0], start: m.index, inCol: false } : null;
  }, [expr, caret]);
  const suggs = useMemo<Sugg[]>(() => {
    if (!word) return [];
    const w = word.text.toLowerCase();
    const role = new Map(study.columns.map((c) => [c.name, c]));
    const cols: Sugg[] = numeric.filter((c) => c.toLowerCase().includes(w) && c !== word.text).map((c) => {
      const col = role.get(c);
      const detail = col ? `${groupLabel(t, col.role)} · ${col.kind === "number" ? t("swKindNumber") : t("swKindText")}` : `ƒ ${t("swNewColumns")}`;
      return { insert: IDENT.test(c) ? c : `col("${c}")`, label: c, detail, fn: false };
    });
    // a column whose name starts with what was typed first
    cols.sort((a, b) => Number(!a.label.toLowerCase().startsWith(w)) - Number(!b.label.toLowerCase().startsWith(w)));
    const fns: Sugg[] = word.inCol ? [] : FUNCS.filter((f) => f.name.startsWith(w) && f.name !== word.text).map((f) => ({ insert: `${f.name}(`, label: `${f.name}()`, detail: t(f.key), fn: true }));
    return [...cols, ...fns].slice(0, MAX_SUGG);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [word, study.columns, numeric.join("\u241f"), t]);
  const take = (s: Sugg) => {
    if (!word) return;
    const start = word.start;
    let end = caret;
    if (word.inCol) { const close = expr.slice(caret).match(/^[^"]*"\s*\)?/); end = caret + (close ? close[0].length : 0); }
    const next = expr.slice(0, start) + s.insert + expr.slice(end);
    const pos = start + s.insert.length;
    setExpr(next); setOpen(false); setAt(0);
    requestAnimationFrame(() => { input.current?.setSelectionRange(pos, pos); setCaret(pos); input.current?.focus(); });
  };
  // the value in the first run, or what is wrong - as it is typed
  const [pv, setPv] = useState<{ ok: boolean; value?: number | null; error?: string } | null>(null);
  useEffect(() => {
    if (kind !== "row" || !expr.trim()) { setPv(null); return; }
    let live = true;
    const h = window.setTimeout(() => sweepApi.formulaPreview(study.tableId, expr, others).then((r) => live && setPv(r)).catch(() => live && setPv(null)), 250);
    return () => { live = false; window.clearTimeout(h); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expr, kind, study.tableId]);
  const nm = name.trim();
  const clash = !!nm && (study.columns.some((c) => c.name === nm) || others.some((d) => d.name === nm));
  const ok = nm && !clash && (kind === "row" ? expr.trim() && pv?.ok !== false : column);
  const save = () => {
    if (!ok) return;
    const d: Derived = kind === "row" ? { name: nm, kind: "row", expr: expr.trim() }
      : { name: nm, kind: "set", op, column, where: Object.keys(where).length ? where : undefined };
    const st = useSweeps.getState();
    if (edit) st.replaceDerived(edit.i, d); else st.addDerived(d);
    onDone?.();
  };
  return (
    <div className="sw-derived-editor">
      <div className="sw-seg" role="radiogroup" aria-label={t("swNewColumns")}>
        <button role="radio" aria-checked={kind === "row"} className={kind === "row" ? "on" : ""} onClick={() => setKind("row")}>{t("swNewPerRun")}</button>
        <button role="radio" aria-checked={kind === "set"} className={kind === "set" ? "on" : ""} onClick={() => setKind("set")}>{t("swNewPerSet")}</button>
      </div>
      <label>{t("swNewName")}<input value={name} onChange={(e) => setName(e.target.value)} placeholder={kind === "row" ? "range_per_kg" : "range_hot_min"} /></label>
      {clash && <p className="sw-warn">{t("swNameTaken", { n: nm })}</p>}
      {kind === "row" ? (
        <>
          <label>{t("swFormula")}
            <span className="sw-complete">
              <input ref={input} value={expr} placeholder="range_m / payload_kg" spellCheck={false} dir="ltr" autoComplete="off"
                role="combobox" aria-expanded={open && suggs.length > 0} aria-autocomplete="list"
                onChange={(e) => { setExpr(e.target.value); setCaret(e.target.selectionStart ?? e.target.value.length); setOpen(true); setAt(0); }}
                onSelect={(e) => setCaret((e.target as HTMLInputElement).selectionStart ?? 0)}
                onBlur={() => window.setTimeout(() => setOpen(false), 120)}
                onKeyDown={(e) => {
                  if (!open || !suggs.length) { if (e.key === "Enter") save(); return; }
                  if (e.key === "ArrowDown") { e.preventDefault(); setAt((at + 1) % suggs.length); }
                  else if (e.key === "ArrowUp") { e.preventDefault(); setAt((at - 1 + suggs.length) % suggs.length); }
                  else if (e.key === "Tab" || e.key === "Enter") { e.preventDefault(); take(suggs[at]); }
                  else if (e.key === "Escape") { e.stopPropagation(); setOpen(false); }
                }} />
              {open && suggs.length > 0 && (
                <ul className="sw-complete-list" role="listbox">
                  {suggs.map((s, i) => (
                    <li key={s.label} role="option" aria-selected={i === at} className={i === at ? "on" : ""}
                      onMouseDown={(e) => { e.preventDefault(); take(s); }}>
                      <span className={s.fn ? "sw-fn" : ""} dir="ltr">{s.label}</span><span className="hint">{s.detail}</span>
                    </li>
                  ))}
                </ul>
              )}
            </span>
          </label>
          {pv && (pv.ok ? <p className="hint sw-formula-ok">{t("swFirstRun", { v: pv.value === null || pv.value === undefined ? "–" : fmtValue(pv.value) })}</p>
            : <p className="sw-warn" role="alert">{pv.error}</p>)}
          {!pv && <p className="hint">{t("swFormulaHint")}</p>}
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
        <button className="btn primary" disabled={!ok} onClick={save}>{edit ? t("swSaveColumn") : t("swAddColumn")}</button>
        <button className="btn" onClick={() => onDone?.()}>{t("cancel")}</button>
      </div>
    </div>
  );
}
