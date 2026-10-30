/* An axis's menu: its scale, colour by it, reverse, hide, and the values it keeps (ranges for a
   number, a list for categories) typed exactly. */
import { useEffect, useRef } from "react";
import { useT } from "../../i18n";
import type { Col, Filter, Scale } from "../../sweeps/model";
import { fmtValue, labelOf, makeScale } from "../../sweeps/scales";

const SCALES: { s: Scale; key: "swScaleLinear" | "swScaleLog" | "swScaleCategory" | "swScaleOrdinal" }[] =
  [{ s: "linear", key: "swScaleLinear" }, { s: "log", key: "swScaleLog" }, { s: "category", key: "swScaleCategory" }, { s: "ordinal", key: "swScaleOrdinal" }];

export interface AxisMenuProps {
  col: Col; label: string; at: DOMRect; scale: Scale; reversed: boolean; filter?: Filter; colouring: boolean;
  onScale: (s: Scale) => void; onReverse: () => void; onColour: () => void; onHide: () => void;
  onFilter: (f: Filter | null) => void; onClose: () => void;
}

export default function AxisMenu(p: AxisMenuProps) {
  const t = useT();
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const off = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) p.onClose(); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") p.onClose(); };
    window.addEventListener("mousedown", off); window.addEventListener("keydown", esc);
    return () => { window.removeEventListener("mousedown", off); window.removeEventListener("keydown", esc); };
  }, [p]);
  const sc = makeScale(p.col, p.scale);
  const places = sc.places;
  const ranges = p.filter?.kind === "ranges" ? p.filter.ranges : [];
  const kept = p.filter?.kind === "values" ? p.filter.values : null;
  const setRange = (i: number, j: 0 | 1, v: number) => {
    const r = ranges.map((x) => [...x] as [number, number]);
    r[i][j] = v;
    p.onFilter({ kind: "ranges", ranges: r });
  };
  const left = Math.min(Math.max(8, p.at.left - 110), window.innerWidth - 290);
  return (
    <div className="popover sw-axis-menu" ref={box} role="dialog" aria-label={p.label} style={{ position: "fixed", left, top: p.at.bottom + 6 }}>
      <h3>{p.label}</h3>
      <div className="sw-seg" role="radiogroup" aria-label={t("swScale")}>
        {SCALES.map(({ s, key }) => (
          <button key={s} role="radio" aria-checked={p.scale === s} className={p.scale === s ? "on" : ""}
            disabled={p.col.kind === "cat" && (s === "linear" || s === "log")} onClick={() => p.onScale(s)}>{t(key)}</button>
        ))}
      </div>
      <div className="sw-keep">
        <span className="hint">{t("swKeep")}</span>
        {places ? (
          <div className="sw-keep-values">
            {places.map((v) => {
              const on = !kept || kept.includes(v);
              return (
                <label key={v} className="acheck"><input type="checkbox" checked={on} onChange={() => {
                  const cur = kept ?? places;
                  const next = on ? cur.filter((x) => x !== v) : [...cur, v];
                  p.onFilter(next.length === places.length ? null : { kind: "values", values: next });
                }} />{labelOf(p.col, v)}</label>
              );
            })}
          </div>
        ) : (
          <>
            {ranges.map(([a, b], i) => (
              <div key={i} className="sw-range">
                <input type="number" aria-label={t("swFrom")} defaultValue={fmtValue(Math.min(a, b))} onBlur={(e) => setRange(i, 0, Number(e.target.value))} />
                <span>–</span>
                <input type="number" aria-label={t("swTo")} defaultValue={fmtValue(Math.max(a, b))} onBlur={(e) => setRange(i, 1, Number(e.target.value))} />
                <button className="iconbtn" aria-label={t("swRemoveRange")} onClick={() => {
                  const r = ranges.filter((_, j) => j !== i);
                  p.onFilter(r.length ? { kind: "ranges", ranges: r } : null);
                }}>×</button>
              </div>
            ))}
            <button className="linklike" onClick={() => p.onFilter({ kind: "ranges", ranges: [...ranges, [sc.inv(0.25), sc.inv(0.75)]] })}>{t("swAddRange")}</button>
            <span className="hint">{t("swRangeHint")}</span>
          </>
        )}
      </div>
      <div className="sw-menu-items">
        <button className={p.colouring ? "on" : ""} onClick={p.onColour}>{t("swColourByThis")}</button>
        <button onClick={p.onReverse}>{p.reversed ? t("swUnreverse") : t("swReverse")}</button>
        {p.filter && <button onClick={() => p.onFilter(null)}>{t("swClearFilter")}</button>}
        <button onClick={p.onHide}>{t("swHideAxis")}</button>
      </div>
    </div>
  );
}
