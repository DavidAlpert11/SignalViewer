/* Which columns to show - the plot's axes, the raw table's columns: a button that opens the app's
   multi-choice list (MultiSignalPicker: type to search, exact matches to take in one go, similar
   names one by one), grouped by role, with the groups as one-click choices. One control for it in
   the area: it replaced "Show columns" and "+ axis". The order of what was chosen is kept; new
   columns go at the end. */
import { useEffect, useRef, useState } from "react";
import { useT } from "../../i18n";
import MultiSignalPicker, { type MultiOption } from "../MultiSignalPicker";
import { useEscape } from "../Overlays";

const POP_W = 360, POP_MIN_H = 360;

export default function ColumnPicker({ options, value, onChange, presets, label }: {
  options: MultiOption[]; value: string[]; onChange: (ids: string[]) => void;
  presets?: { label: string; ids: string[] }[]; label?: string;
}) {
  const t = useT();
  // fixed on screen under the button: the bar it sits in scrolls sideways and would cut it
  const [open, setOpen] = useState<{ top?: number; bottom?: number; left: number; maxHeight: number } | null>(null);
  const box = useRef<HTMLDivElement>(null);
  useEscape(() => setOpen(null), !!open);
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(null); };
    window.addEventListener("mousedown", away);
    return () => window.removeEventListener("mousedown", away);
  }, [open]);
  // keep the order on screen: what stays keeps its place, what is new is added after it
  const change = (ids: string[]) => {
    const want = new Set(ids);
    onChange([...value.filter((x) => want.has(x)), ...ids.filter((x) => !value.includes(x))]);
  };
  return (
    <div className="sw-colpick" ref={box}>
      <button className="btn outline sw-colpick-btn" aria-expanded={!!open} aria-haspopup="dialog" title={t("swColumnsHint")}
        onClick={(e) => {
          if (open) { setOpen(null); return; }
          const r = e.currentTarget.getBoundingClientRect();
          const left = Math.max(8, Math.min(r.left, window.innerWidth - POP_W - 8));
          // below the button, or above it when there is more room there (the table's bar is low)
          const below = window.innerHeight - r.bottom - 12, above = r.top - 12;
          setOpen(below >= POP_MIN_H || below >= above ? { top: r.bottom + 4, left, maxHeight: Math.min(560, below) }
            : { bottom: window.innerHeight - r.top + 4, left, maxHeight: Math.min(560, above) });
        }}>
        {label ?? t("swColumnsOf", { n: value.length, of: options.length })} ▾
      </button>
      {open && (
        <div className="sw-colpick-pop" role="dialog" aria-label={t("swShowColumns")} style={{ top: open.top, bottom: open.bottom, left: open.left, width: POP_W, maxHeight: open.maxHeight }}>
          <MultiSignalPicker options={options} value={value} onChange={change} noun="columns"
            quick={presets?.map((p) => ({ label: p.label, ids: p.ids }))} />
        </div>
      )}
    </div>
  );
}
