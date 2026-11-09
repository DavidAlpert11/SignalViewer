/* 26.U5: a tolerance's fields (abs / % / time / allowed outside) - every signal's in Compare's
   settings, a signal's own under its comparison (empty there: every signal's, shown greyed). */
import { useEffect, useState } from "react";
import type { TolEntry } from "../api";
import { useT } from "../i18n";

const FIELDS = [
  { k: "abs", label: "tolAbs", hint: "" },
  { k: "pct", label: "tolPct", hint: "" },
  { k: "time", label: "tolTime", hint: "tolTimeHint" },
  { k: "outside_pct", label: "tolOutside", hint: "tolOutsideHint" },
] as const;

function NumField({ value, placeholder, label, title, onChange }: {
  value: number | undefined; placeholder: number | undefined; label: string; title?: string; onChange: (v: number | undefined) => void;
}) {
  const [text, setText] = useState(value === undefined ? "" : String(value));
  // follow a change made elsewhere (a file opened, "use every signal's") unless it is what is typed
  useEffect(() => { setText((cur) => (cur.trim() !== "" && +cur === value ? cur : value === undefined ? "" : String(value))); }, [value]);
  const bad = text.trim() !== "" && !(Number.isFinite(+text) && +text >= 0);
  return (
    <label className="afield" title={title}><span>{label}</span>
      <input inputMode="decimal" value={text} aria-invalid={bad || undefined} placeholder={placeholder === undefined ? "—" : String(placeholder)}
        onChange={(e) => {
          const s = e.target.value;
          setText(s);
          if (s.trim() === "") onChange(undefined);
          else if (Number.isFinite(+s) && +s >= 0) onChange(+s);
        }} /></label>
  );
}

export default function TolFields({ entry, inherited, onChange }: {
  entry: TolEntry; inherited?: TolEntry; onChange: (e: TolEntry) => void;
}) {
  const t = useT();
  return (
    <div className="arow tol-fields">
      {FIELDS.map((f) => (
        <NumField key={f.k} label={t(f.label)} title={f.hint ? t(f.hint) : undefined}
          value={entry[f.k] as number | undefined} placeholder={inherited?.[f.k] as number | undefined}
          onChange={(v) => { const e = { ...entry }; if (v === undefined) delete e[f.k]; else e[f.k] = v; onChange(e); }} />
      ))}
    </div>
  );
}
