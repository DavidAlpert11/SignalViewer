/* Above the plot, one line: a line per set or per run, + axis, what the colour means, the count,
   and what to do with the selection. Everything about one axis - its scale, colouring by it,
   reversing, hiding, its ranges - is in that axis's own menu (click its name on the plot); the
   axes are reordered by dragging their names. A control lives in one place (CLAUDE.md). */
import { useT } from "../../i18n";
import { FAILS, HOLDS, rampCss } from "../../sweeps/colors";
import { hasFilter } from "../../sweeps/filters";
import { fmtValue, makeScale } from "../../sweeps/scales";
import { useSweeps, type Study } from "../../sweeps/state";
import { axisChoices, colLabel, modeColumns, scaleOf, scopeKey, shownAxes } from "../../sweeps/view";
import { openMenu } from "../Overlays";

export default function PlotToolbar({ study, shown, total, onKeep, onExclude, onExport }:
  { study: Study; shown: number; total: number; onKeep: () => void; onExclude: () => void; onExport: () => void }) {
  const t = useT();
  const { setView, toggleAxis } = useSweeps.getState();
  const v = study.view;
  const axes = shownAxes(study);
  const choices = axisChoices(study).filter((c) => !axes.includes(c));
  const nFilters = Object.values(v.filters).filter(hasFilter).length;
  const scoped = v.scope.key === scopeKey(study) ? v.scope.steps.length : 0;
  return (
    <div className="sw-plotbar">
      <div className="sw-seg" role="radiogroup" aria-label={t("swLines")}>
        <button role="radio" aria-checked={v.mode === "sets"} className={v.mode === "sets" ? "on" : ""} onClick={() => setView({ mode: "sets" })}>{t("swPerSet")}</button>
        <button role="radio" aria-checked={v.mode === "runs"} className={v.mode === "runs" ? "on" : ""} onClick={() => setView({ mode: "runs" })}>{t("swPerRun")}</button>
      </div>
      {choices.length > 0 && (
        <select className="sw-add" aria-label={t("swAddAxis")} value="" onChange={(e) => e.target.value && toggleAxis(e.target.value, true)}>
          <option value="">{t("swAddAxis")}</option>
          {choices.map((c) => <option key={c} value={c}>{colLabel(t, study, c)}</option>)}
        </select>
      )}
      <ColourKey study={study} />
      <span className="hint sw-count">{t("swShown", { n: shown.toLocaleString(), of: total.toLocaleString() })}</span>
      {nFilters > 0 && <button className="btn outline" onClick={() => setView({ filters: {} })}>{t("swClearFilters", { n: nFilters })}</button>}
      {/* HiPlot's Keep / Exclude / Restore: narrow what is shown to the selection, step by step */}
      <button className="btn outline" disabled={!nFilters || !shown} onClick={onKeep} title={t("swKeepHint")}>{t("swKeepSel")}</button>
      <button className="btn outline" disabled={!nFilters || shown === total} onClick={onExclude} title={t("swExcludeHint")}>{t("swExcludeSel")}</button>
      {scoped > 0 && <>
        <button className="btn outline" onClick={() => useSweeps.getState().restore(false)} title={t("swStepBackHint")}>{t("swStepBack")}</button>
        <button className="btn outline" onClick={() => useSweeps.getState().restore(true)}>{t("swRestore", { n: scoped })}</button>
      </>}
      <button className="btn outline" disabled={!shown} onClick={onExport} title={t("swExportShownHint")}>{t("swExportShown")}</button>
    </div>
  );
}

/** What the colour means - not a second way to choose it (that is "Colour by this" in an axis's
 *  menu): the colours of holds / fails, or the column's scale and range. A click offers the
 *  colourings that are not a column (holds, the Pareto front, one colour). */
function ColourKey({ study }: { study: Study }) {
  const t = useT();
  const v = study.view;
  const { cols } = modeColumns(study);
  const name = v.colorBy && cols.has(v.colorBy) ? v.colorBy : null;
  const c = name ? cols.get(name)! : null;
  const flag = name === "#holds" || name === "#pareto" || name === "#partial";
  const menu = (e: React.MouseEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const set = (colorBy: string | null) => useSweeps.getState().setView({ colorBy });
    openMenu({ clientX: r.left, clientY: r.bottom + 4, preventDefault() {}, stopPropagation() {} } as React.MouseEvent, [
      { label: t("swHoldsCol"), checked: name === "#holds", run: () => set("#holds") },
      ...(cols.has("#pareto") ? [{ label: t("swParetoCol"), checked: name === "#pareto", run: () => set("#pareto") }] : []),
      ...(cols.has("#partial") ? [{ label: t("swPartialCol"), checked: name === "#partial", run: () => set("#partial") }] : []),
      { label: t("swColourNone"), checked: !name, run: () => set(null) },
      { label: t("swColourByAxisHint"), disabled: true, run: () => {} },
    ]);
  };
  let key: React.ReactNode;
  if (!c) key = <span className="hint">{t("swColourNone")}</span>;
  else if (flag) key = <><span style={{ color: HOLDS }}>■</span> {name === "#holds" ? t("swHolds") : name === "#pareto" ? t("swParetoCol") : t("swPartialCol")}
    <span style={{ color: FAILS }}>■</span> {t("swOthers")}</>;
  else if (c.kind === "num") {
    const sc = makeScale(c, scaleOf(study, c.name, c) === "log" ? "log" : "linear");
    const ends = [sc.inv(0), sc.inv(1)];
    key = <>{colLabel(t, study, c.name)} <span className="hint">{fmtValue(ends[0])}</span><span className="sw-ramp" style={{ background: rampCss }} /><span className="hint">{fmtValue(ends[1])}</span></>;
  } else key = <>{colLabel(t, study, c.name)} <span className="hint">· {t("swDistinct", { n: c.labels?.length ?? 0 })}</span></>;
  return (
    <button className="sw-colour-key" onClick={menu} title={t("swColourKeyHint")} aria-label={t("swColourBy")}>
      <span className="hint">{t("swColourBy")}:</span> {key}
    </button>
  );
}
