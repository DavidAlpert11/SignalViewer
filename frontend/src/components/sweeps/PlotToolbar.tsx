/* Above the plot: a line per set or per run, the axes (drag to reorder, × to remove, + to add),
   the colour, and the filters. */
import { useState } from "react";
import { useT } from "../../i18n";
import { rampCss } from "../../sweeps/colors";
import { hasFilter } from "../../sweeps/filters";
import { useSweeps, type Study } from "../../sweeps/state";
import { axisChoices, colLabel, modeColumns, scopeKey, shownAxes } from "../../sweeps/view";

export default function PlotToolbar({ study, shown, total, onKeep, onExclude, onExport }:
  { study: Study; shown: number; total: number; onKeep: () => void; onExclude: () => void; onExport: () => void }) {
  const t = useT();
  const { setView, moveAxis, toggleAxis } = useSweeps.getState();
  const [drag, setDrag] = useState<number | null>(null);
  const v = study.view;
  const axes = shownAxes(study);
  const choices = axisChoices(study).filter((c) => !axes.includes(c));
  const nFilters = Object.values(v.filters).filter(hasFilter).length;
  const scoped = v.scope.key === scopeKey(study) ? v.scope.steps.length : 0;
  const { cols } = modeColumns(study);
  const colourCol = v.colorBy ? cols.get(v.colorBy) : undefined;
  return (
    <div className="sw-plotbar">
      <div className="sw-seg" role="radiogroup" aria-label={t("swLines")}>
        <button role="radio" aria-checked={v.mode === "sets"} className={v.mode === "sets" ? "on" : ""} onClick={() => setView({ mode: "sets", pinned: v.pinned })}>{t("swPerSet")}</button>
        <button role="radio" aria-checked={v.mode === "runs"} className={v.mode === "runs" ? "on" : ""} onClick={() => setView({ mode: "runs" })}>{t("swPerRun")}</button>
      </div>
      <div className="sw-chips" aria-label={t("swAxes")}>
        {axes.map((a) => {
          const i = v.axes.indexOf(a);
          return (
            <span key={a} className={`sw-chip${drag === i ? " dragging" : ""}`} draggable
              onDragStart={() => setDrag(i)} onDragEnd={() => setDrag(null)}
              onDragOver={(e) => e.preventDefault()} onDrop={() => { if (drag !== null) moveAxis(drag, i); setDrag(null); }}>
              <span className="grip" aria-hidden="true">⋮⋮</span>{colLabel(t, study, a)}
              <button aria-label={t("swHideAxisOf", { c: a })} onClick={() => toggleAxis(a, false)}>×</button>
            </span>
          );
        })}
        {choices.length > 0 && (
          <select className="sw-add" aria-label={t("swAddAxis")} value="" onChange={(e) => e.target.value && toggleAxis(e.target.value, true)}>
            <option value="">{t("swAddAxis")}</option>
            {choices.map((c) => <option key={c} value={c}>{colLabel(t, study, c)}</option>)}
          </select>
        )}
      </div>
      <label className="sw-colour">{t("swColourBy")}
        <select value={v.colorBy ?? ""} onChange={(e) => setView({ colorBy: e.target.value || null })}>
          <option value="">{t("swColourNone")}</option>
          <option value="#holds">{t("swHoldsCol")}</option>
          {[...cols.keys()].filter((c) => c !== "#holds" && c !== "#set" && c !== "#row").map((c) => <option key={c} value={c}>{colLabel(t, study, c)}</option>)}
        </select>
        {colourCol && colourCol.kind === "num" && v.colorBy !== "#holds" && <span className="sw-ramp" style={{ background: rampCss }} aria-hidden="true" />}
      </label>
      <span className="hint sw-count">{t("swShown", { n: shown.toLocaleString(), of: total.toLocaleString() })}</span>
      {nFilters > 0 && <button className="btn outline" onClick={() => setView({ filters: {} })}>{t("swClearFilters", { n: nFilters })}</button>}
      {/* HiPlot's Keep / Exclude / Restore: narrow what is shown to the selection, step by step */}
      <div className="sw-scope">
        <button className="btn outline" disabled={!nFilters || !shown} onClick={onKeep} title={t("swKeepHint")}>{t("swKeepSel")}</button>
        <button className="btn outline" disabled={!nFilters || shown === total} onClick={onExclude} title={t("swExcludeHint")}>{t("swExcludeSel")}</button>
        {scoped > 0 && <>
          <button className="btn outline" onClick={() => useSweeps.getState().restore(false)} title={t("swStepBackHint")}>{t("swStepBack")}</button>
          <button className="btn outline" onClick={() => useSweeps.getState().restore(true)}>{t("swRestore", { n: scoped })}</button>
        </>}
        <button className="btn outline" disabled={!shown} onClick={onExport} title={t("swExportShownHint")}>{t("swExportShown")}</button>
      </div>
    </div>
  );
}
