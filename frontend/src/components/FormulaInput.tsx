import { flushSync } from "react-dom";
import { useMemo, useRef } from "react";
import type { RunInfo } from "../api";
import { fileLabel } from "../store";
import { refFor } from "../formulaRefs";
import { parenProblem, VAR_E, VAR_PI, VAR_T } from "../formulaHelp";
import { useT } from "../i18n";
import ExprInput, { type SigOption } from "./ExprInput";
import { useApp } from "../store";

const QUICK = ["+", "−", "×", "÷", "(", ")", "^", "abs(", "sqrt(", "sin(", "deriv(", "integ(", "smooth(", "where("];
const VARS = [VAR_T, VAR_PI, VAR_E];

/** Formula editor: suggestions for signal names, functions (with what they do) and variables
 *  while typing, the arguments of the function the caret is in, and buttons for common operators. */
export default function FormulaInput({ value, onChange, runs, error }: {
  value: string; onChange: (v: string) => void; runs: RunInfo[]; error?: string;
}) {
  const t = useT();
  const ref = useRef<(HTMLInputElement & HTMLTextAreaElement) | null>(null);
  const options: SigOption[] = useMemo(() => runs.flatMap((r) => r.signals.map((s) => ({
    label: s.name, sub: r.format === "derived" ? "ƒ" : fileLabel(runs, r.id), insert: refFor(runs, s.id),
  }))), [runs]);
  const paren = value.trim() ? parenProblem(value) : null;
  const logs = useApp((s) => s.logs);
  const params = useMemo(() => {
    const m = new Map<string, number>();
    Object.values(logs).forEach((l) => l.params.forEach((p) => { if (!m.has(p.name)) m.set(p.name, p.value); }));
    return Array.from(m, ([name, v]) => ({ name, value: v })).sort((a, b) => a.name.localeCompare(b.name));
  }, [logs]);

  const quick = (q: string) => {
    const map: Record<string, string> = { "−": " - ", "×": " * ", "÷": " / ", "+": " + ", "^": "^" };
    const el = ref.current;
    const a = el?.selectionStart ?? value.length, b = el?.selectionEnd ?? value.length;
    const text = map[q] ?? q;
    const pos = a + text.length;
    flushSync(() => onChange(value.slice(0, a) + text + value.slice(b)));     // (then the caret, at once)
    el?.focus();
    el?.setSelectionRange(pos, pos);
  };

  return (
    <div className="fx">
      <ExprInput value={value} onChange={onChange} vars={VARS} signals={options} params={params} multiline inputRef={ref}
        placeholder="2*Speed - RPM/95" ariaLabel={t("formula")} invalid={!!error || !!paren} />
      <div className="fx-quick">
        {QUICK.map((q) => <button key={q} type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => quick(q)}>{q}</button>)}
      </div>
      {error ? <p className="hint err fx-err">{error}</p> : paren ? <p className="hint err fx-err">{t(paren)}</p> : <p className="hint fx-help">{t("fxHelp")}</p>}
    </div>
  );
}
