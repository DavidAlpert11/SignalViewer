/* Choosing one column by typing part of its name (owner's spec 2026-11-02): "roll err" finds
   roll_error_deg - every word typed must be in the name, "_" and spaces alike. Each result shows its
   role and range ("output · 1.09–7.24"); the arrows walk them, Enter takes one, the columns already
   in use come first. One control wherever a column is chosen (Must meet, Robust to). */
import { useMemo, useRef, useState } from "react";
import { useT } from "../../i18n";
import { fmtValue } from "../../sweeps/scales";
import { groupLabel, type ColumnChoice } from "../../sweeps/view";

const norm = (s: string) => s.toLowerCase().replace(/[_\s]+/g, " ");
/** every word of the query in the name (in any order) */
const matches = (name: string, q: string) => { const n = norm(name); return norm(q).split(" ").filter(Boolean).every((w) => n.includes(w)); };

export default function ColumnSearch({ value, options, used, onChange, label, max = 12 }: {
  value: string; options: ColumnChoice[]; used?: string[]; onChange: (name: string) => void; label: string; max?: number;
}) {
  const t = useT();
  const [q, setQ] = useState<string | null>(null);        // null: not typing - the value is shown
  const [at, setAt] = useState(0);
  const box = useRef<HTMLInputElement>(null);
  const inUse = new Set(used ?? []);
  const found = useMemo(() => {
    const list = options.filter((o) => !q || matches(o.name, q));
    return list.sort((a, b) => Number(!inUse.has(a.name)) - Number(!inUse.has(b.name))).slice(0, max);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options, q, used, max]);
  const take = (n: string) => { onChange(n); setQ(null); setAt(0); box.current?.blur(); };
  const detail = (o: ColumnChoice) => [o.role === "derived" ? `ƒ ${t("swNewColumns")}` : groupLabel(t, o.role),
    o.min !== undefined && o.max !== undefined ? `${fmtValue(o.min)}–${fmtValue(o.max)}` : ""].filter(Boolean).join(" · ");
  return (
    <span className="sw-complete sw-colsearch">
      <input ref={box} value={q ?? value} aria-label={label} placeholder={label} role="combobox" aria-expanded={q !== null && found.length > 0} aria-autocomplete="list"
        spellCheck={false} dir="ltr" autoComplete="off"
        onFocus={(e) => { setQ(""); requestAnimationFrame(() => e.target.select()); }}
        onBlur={() => window.setTimeout(() => setQ(null), 120)}
        onChange={(e) => { setQ(e.target.value); setAt(0); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setAt(Math.min(found.length - 1, at + 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setAt(Math.max(0, at - 1)); }
          else if (e.key === "Enter" && found[at]) { e.preventDefault(); take(found[at].name); }
          else if (e.key === "Escape") { e.stopPropagation(); setQ(null); box.current?.blur(); }
        }} />
      {q !== null && found.length > 0 && (
        <ul className="sw-complete-list" role="listbox">
          {found.map((o, i) => (
            <li key={o.name} role="option" aria-selected={i === at} className={`${i === at ? "on" : ""}${o.name === value ? " cur" : ""}`}
              onMouseDown={(e) => { e.preventDefault(); take(o.name); }}>
              <span dir="ltr" className="sw-ellipsis" title={o.name}>{o.name}</span><span className="hint">{detail(o)}</span>
            </li>
          ))}
        </ul>
      )}
    </span>
  );
}
