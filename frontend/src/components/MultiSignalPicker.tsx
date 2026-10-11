import { useMemo, useState } from "react";
import { useT } from "../i18n";
import { fuzzySort, exactMatch } from "../fuzzy";
import { Icon } from "../icons";

export interface MultiOption { id: string; label: string; group?: string }
const SHOWN = 150;

/** Choose several signals by typing, without plotting them first.
 *  - nothing is chosen behind the user's back: the choice is always listed as chips;
 *  - "select the N results" REPLACES the choice with exactly what the search shows;
 *    adding to the choice is a separate, explicit link;
 *  - chosen signals that the search hides are called out, with a one-click fix. */
export default function MultiSignalPicker({ options, value, onChange, quick }: {
  options: MultiOption[]; value: string[]; onChange: (ids: string[]) => void;
  quick?: { label: string; ids: string[] }[];
}) {
  const t = useT();
  const [q, setQ] = useState("");
  const chosen = useMemo(() => new Set(value), [value]);
  const byId = useMemo(() => new Map(options.map((o) => [o.id, o])), [options]);
  // bulk selection uses EXACT matches only: "select all" must never take approximate guesses
  // the SIGNAL NAME only: matching the file name too made "r" pick every signal of "run_a.csv"
  const matches = useMemo(() => (!q.trim() ? options : options.filter((o) => exactMatch(o.label, q))), [q, options]);
  const similar = useMemo(() => (q.trim() && !matches.length ? fuzzySort(options, (o) => o.label, q).slice(0, 5) : []), [q, matches, options]);
  const matchIds = useMemo(() => new Set(matches.map((o) => o.id)), [matches]);
  const hidden = q.trim() ? value.filter((id) => !matchIds.has(id)) : [];
  const toggle = (id: string) => onChange(chosen.has(id) ? value.filter((x) => x !== id) : [...value, id]);
  const label = (id: string) => { const o = byId.get(id); return o ? (o.group ? `${o.label} · ${o.group}` : o.label) : id; };

  return (
    <div className="msp">
      <div className="msp-top">
        <span className="msp-count">{t("nChosen", { n: value.length })}</span>
        {quick?.filter((x) => x.ids.length).map((x) => (
          <button key={x.label} type="button" className="linklike" onClick={() => onChange(Array.from(new Set(x.ids)))}>{x.label}</button>
        ))}
        {value.length > 0 && <button type="button" className="linklike" onClick={() => onChange([])}>{t("clearSelection")}</button>}
      </div>
      {value.length > 0 && (
        <div className="msp-chips">
          {value.slice(0, 12).map((id) => (
            <span key={id} className="msp-chip">{label(id)}
              <button type="button" aria-label={t("remove")} onClick={() => toggle(id)}><Icon.X width={10} height={10} /></button></span>
          ))}
          {value.length > 12 && <span className="msp-more">+{value.length - 12}</span>}
        </div>
      )}
      <label className="filter msp-filter"><Icon.Search />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("mspSearch")} aria-label={t("mspSearch")} /></label>
      {q.trim() !== "" && matches.length > 0 && (
        <div className="msp-actions">
          <button type="button" className="btn outline sm" onClick={() => onChange(matches.map((o) => o.id))}>{t("selectOnlyResults", { n: matches.length })}</button>
          <button type="button" className="linklike" onClick={() => onChange(Array.from(new Set([...value, ...matches.map((o) => o.id)])))}>{t("addResults")}</button>
        </div>
      )}
      {hidden.length > 0 && (
        <p className="msp-warn">{t("hiddenChosen", { n: hidden.length })}{" "}
          <button type="button" className="linklike" onClick={() => onChange(value.filter((id) => matchIds.has(id)))}>{t("keepOnlyResults")}</button></p>
      )}
      <div className="msp-list">
        {matches.slice(0, SHOWN).map((o) => (
          <label key={o.id} className="acheck msp-item">
            <input type="checkbox" checked={chosen.has(o.id)} onChange={() => toggle(o.id)} />
            <span className="nm">{o.label}</span>{o.group && <span className="grp">{o.group}</span>}
          </label>
        ))}
        {matches.length > SHOWN && <p className="hint">{t("moreMatches", { n: matches.length - SHOWN })}</p>}
        {!matches.length && <p className="hint">{t("noMatches", { q })}</p>}
        {similar.length > 0 && <>
          <p className="hint msp-similar">{t("similarNames")}</p>
          {similar.map((o) => (
            <label key={o.id} className="acheck msp-item">
              <input type="checkbox" checked={chosen.has(o.id)} onChange={() => toggle(o.id)} />
              <span className="nm">{o.label}</span>{o.group && <span className="grp">{o.group}</span>}
            </label>
          ))}
        </>}
      </div>
    </div>
  );
}
