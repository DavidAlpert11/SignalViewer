import { useEffect, useMemo, useRef, useState } from "react";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { fuzzySort } from "../fuzzy";

export interface PickOption { id: string; label: string; group?: string }

const LIMIT = 80;

/** Searchable signal chooser: replaces <select> lists that become unusable with
 *  thousands of signals. Type to filter (every word must match), arrows + Enter. */
export default function SignalPicker({ value, options, onChange, placeholder, ariaLabel, compact }: {
  value: string | null; options: PickOption[]; onChange: (id: string) => void;
  placeholder?: string; ariaLabel?: string; compact?: boolean;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const current = options.find((o) => o.id === value);

  const matches = useMemo(() => fuzzySort(options, (o) => o.label, q), [q, options]);   // signal names only
  const shown = matches.slice(0, LIMIT);

  useEffect(() => { setSel(0); }, [q, open]);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => { if (!boxRef.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);
  useEffect(() => { listRef.current?.querySelector(".pick-item.on")?.scrollIntoView({ block: "nearest" }); }, [sel]);

  const choose = (id: string) => { onChange(id); setOpen(false); setQ(""); };

  return (
    <div className={`picker${compact ? " compact" : ""}`} ref={boxRef}>
      <button type="button" className="picker-btn" aria-haspopup="listbox" aria-expanded={open} aria-label={ariaLabel}
        onClick={() => setOpen(!open)} title={current?.label}>
        <span className="picker-val">{current ? current.label : <span className="ph">{placeholder ?? t("chooseX")}</span>}</span>
        <Icon.Chevron width={13} height={13} />
      </button>
      {open && (
        <div className="picker-pop" role="dialog">
          <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("searchSignals")} aria-label={t("searchSignals")}
            onKeyDown={(e) => {
              if (e.key === "Escape") { setOpen(false); e.stopPropagation(); }
              else if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(shown.length - 1, s + 1)); }
              else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
              else if (e.key === "Enter" && shown[sel]) { e.preventDefault(); choose(shown[sel].id); }
            }} />
          <div className="picker-list" role="listbox" ref={listRef}>
            {shown.map((o, i) => (
              <button key={o.id} type="button" role="option" aria-selected={o.id === value}
                className={`pick-item${i === sel ? " on" : ""}${o.id === value ? " cur" : ""}`}
                onMouseEnter={() => setSel(i)} onClick={() => choose(o.id)}>
                <span className="nm">{o.label}</span>{o.group && <span className="grp">{o.group}</span>}
              </button>
            ))}
            {!matches.length && <p className="hint pick-more">{t("noMatches", { q })}</p>}
            {matches.length > LIMIT && <p className="hint pick-more">{t("moreMatches", { n: matches.length - LIMIT })}</p>}
          </div>
        </div>
      )}
    </div>
  );
}
