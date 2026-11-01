/* A value that can be typed, not only slid (Q129, MF01): the value as text; a click makes it a
   field - Enter or leaving it commits, Esc restores, the arrows step (Shift: ×10). A typed value
   outside the results' range is kept: the slider beside it pins at its end and this says so. */
import { useState } from "react";
import { useT } from "../../i18n";
import { fmtValue } from "../../sweeps/scales";

export function parseNum(s: string): number | null {
  const v = Number(s.trim().replace(/,/g, "").replace(/−/g, "-"));
  return s.trim() && Number.isFinite(v) ? v : null;
}

/** One step of the arrows: a hundredth of the range, rounded to a 1 / 2 / 5 step. */
export function stepOf(lo: number, hi: number): number {
  const span = Math.abs(hi - lo);
  if (!(span > 0)) return 1;
  const raw = span / 100, p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p;
  return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * p;
}

export default function NumField({ value, lo, hi, onChange, label, className = "", prefix = "", empty }: {
  value: number | undefined; lo: number; hi: number; onChange: (v: number) => void; label: string;
  className?: string; prefix?: string; empty?: string;
}) {
  const t = useT();
  const [text, setText] = useState<string | null>(null);
  const outside = value !== undefined && Number.isFinite(value) && (value < Math.min(lo, hi) || value > Math.max(lo, hi));
  const commit = () => {
    if (text === null) return;
    const v = parseNum(text);
    setText(null);
    if (v !== null && v !== value) onChange(v);
  };
  if (text !== null) {
    return (
      <input className={`sw-num-field mono ${className}`} autoFocus value={text} aria-label={label}
        onChange={(e) => setText(e.target.value)} onBlur={commit} onFocus={(e) => e.target.select()}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); commit(); }
          else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setText(null); }
          else if (e.key === "ArrowUp" || e.key === "ArrowDown") {
            e.preventDefault();
            const base = parseNum(text) ?? value ?? lo;
            const st = stepOf(lo, hi) * (e.shiftKey ? 10 : 1) * (e.key === "ArrowUp" ? 1 : -1);
            const v = +(base + st).toPrecision(12);
            setText(String(v));
            onChange(v);
          }
        }} />
    );
  }
  return (
    <button type="button" className={`sw-num mono ${className}${outside ? " outside" : ""}`} aria-label={label}
      title={outside ? t("swOutsideResults") : t("swTypeValue")}
      onClick={(e) => { e.stopPropagation(); setText(value === undefined ? "" : String(+value.toPrecision(10))); }}>
      {value === undefined ? empty ?? "–" : `${prefix}${fmtValue(value)}`}{outside && <span className="sw-num-out"> ⇥</span>}
    </button>
  );
}
