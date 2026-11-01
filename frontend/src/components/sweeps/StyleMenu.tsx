/* How the plots look (S12): the colour map, a point's size and opacity, the grid and its minor
   lines, the numbers on a map's cells - one style for the study's maps, point plots and *Which
   parameter matters*, kept with it and used by the report. Only the choices a plot uses are shown. */
import { useEffect, useRef, useState } from "react";
import { useT } from "../../i18n";
import { CMAPS, rampCssOf, type Cmap } from "../../sweeps/colors";
import type { PlotStyle } from "../../sweeps/model";
import { useSweeps, type Study } from "../../sweeps/state";
import { styleOf } from "../../sweeps/view";
import { useEscape } from "../Overlays";

type Part = "cmap" | "points" | "grid" | "numbers";

export default function StyleMenu({ study, parts }: { study: Study; parts: Part[] }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEscape(() => setOpen(false), open);
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    window.addEventListener("mousedown", away);
    return () => window.removeEventListener("mousedown", away);
  }, [open]);
  const st = styleOf(study);
  const set = (p: Partial<PlotStyle>) => useSweeps.getState().setView({ style: { ...(study.view.style ?? {}), ...p } });
  return (
    <div className="sw-style" ref={box}>
      <button className="btn outline" aria-expanded={open} onClick={() => setOpen(!open)}>{t("swStyle")} ▾</button>
      {open && (
        <div className="sw-style-pop" role="dialog" aria-label={t("swStyle")}>
          {parts.includes("cmap") && (
            <label className="sw-field">{t("swCmap")}
              <select value={st.cmap} onChange={(e) => set({ cmap: e.target.value as Cmap })}>
                {(Object.keys(CMAPS) as Cmap[]).map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <span className="sw-legend-ramp" style={{ background: rampCssOf(st.cmap) }} />
            </label>
          )}
          {parts.includes("points") && <>
            <label className="sw-field">{t("swPointSize", { n: st.size })}
              <input type="range" min={1} max={10} step={1} value={st.size} onChange={(e) => set({ size: Number(e.target.value) })} /></label>
            <label className="sw-field">{t("swOpacity", { n: st.opacity === undefined ? t("swAuto") : `${Math.round(st.opacity * 100)}%` })}
              <input type="range" min={0.1} max={1} step={0.05} value={st.opacity ?? 0.85} onChange={(e) => set({ opacity: Number(e.target.value) })} /></label>
          </>}
          {parts.includes("grid") && <>
            <label className="acheck"><input type="checkbox" checked={st.grid} onChange={(e) => set({ grid: e.target.checked })} />{t("swGrid")}</label>
            <label className="acheck"><input type="checkbox" checked={st.minor} disabled={!st.grid} onChange={(e) => set({ minor: e.target.checked })} />{t("swMinorGrid")}</label>
          </>}
          {parts.includes("numbers") && (
            <label className="acheck"><input type="checkbox" checked={st.numbers} onChange={(e) => set({ numbers: e.target.checked })} />{t("swCellNumbers")}</label>
          )}
          <button className="linklike" onClick={() => useSweeps.getState().setView({ style: undefined })}>{t("swStyleReset")}</button>
        </div>
      )}
    </div>
  );
}
