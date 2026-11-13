/* Above the plot, one line: a line per set or per run, + axis, what the colour means, the count,
   and what to do with the selection. Everything about one axis - its scale, colouring by it,
   reversing, hiding, its ranges - is in that axis's own menu (click its name on the plot); the
   axes are reordered by dragging their names. A control lives in one place (CLAUDE.md). */
import { useT } from "../../i18n";
import { FAILS, FLAG_COLS, HOLDS, rampCss } from "../../sweeps/colors";
import { hasFilter } from "../../sweeps/filters";
import { fmtValue, makeScale } from "../../sweeps/scales";
import { useSweeps, type Study } from "../../sweeps/state";
import { axisChoices, axisOptions, colLabel, modeColumns, presetChoices, scaleOf, scopeKey, shownAxes, type ColumnPreset } from "../../sweeps/view";
import ColumnPicker from "./ColumnPicker";
import type { TKey } from "../../i18n";

export const PRESET_KEY: Record<ColumnPreset, TKey> = { all: "swShowAll", "params-outputs": "swShowParamsOutputs", "params-goal": "swShowParamsGoal",
  params: "swShowParams", scenarios: "swShowScenarios", outputs: "swShowOutputs" };
import { openMenu } from "../Overlays";

export default function PlotToolbar({ study, shown, total, onKeep, onExclude, onExport, onExportPlot }:
  { study: Study; shown: number; total: number; onKeep: () => void; onExclude: () => void; onExport: () => void; onExportPlot: () => void }) {
  const t = useT();
  const { setView } = useSweeps.getState();
  const v = study.view;
  const axes = shownAxes(study);
  const nFilters = Object.values(v.filters).filter(hasFilter).length;
  const scoped = v.scope.key === scopeKey(study) ? v.scope.steps.length : 0;
  const here = new Set(axisChoices(study));
  const off = (v.axesOff ?? []).filter((a) => here.has(a) && !v.axes.includes(a));
  return (
    <div className="sw-plotbar">
      {/* the axes: chosen in one list (type to search, groups as one click); dragged on the plot to reorder */}
      <ColumnPicker options={axisOptions(t, study)} value={axes}
        presets={presetChoices(t, study, axisChoices(study), PRESET_KEY, v.mode === "runs" ? [] : ["scenarios"])}
        label={t("swColumnsAddRemove", { n: axes.length, of: axisChoices(study).length })}
        onChange={(ids) => {
          const here = new Set(axisChoices(study));
          // a scenario axis shown only in All runs, taken off: remembered as off (else it comes back)
          const autoOff = axes.filter((a) => !ids.includes(a) && !v.axes.includes(a));
          useSweeps.getState().setAxes([...ids, ...v.axes.filter((a) => !here.has(a))]);
          if (autoOff.length) useSweeps.getState().setView({ axesOff: [...autoOff, ...(useSweeps.getState().studies[useSweeps.getState().active]?.view.axesOff ?? [])] });
        }} />
      <button className={`btn outline${v.fitAxes ? " on" : ""}`} aria-pressed={!!v.fitAxes} onClick={() => setView({ fitAxes: !v.fitAxes })}
        title={t("swFitAxesHint")}>{t("swFitAxes")}</button>
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
      {/* undo / redo beside them (also Ctrl+Z / Ctrl+Y and the bar above) */}
      <button className="iconbtn sw-undo" aria-label={t("undo")} title={t("undo")} disabled={!study.history?.past.length} onClick={() => useSweeps.getState().undo()}>↶</button>
      <button className="iconbtn sw-redo" aria-label={t("redo")} title={t("redo")} disabled={!study.history?.future.length} onClick={() => useSweeps.getState().redo()}>↷</button>
      <button className="btn outline" disabled={!shown} onClick={onExport} title={t("swExportShownHint")}>{t("swExportShown")}</button>
      <button className="btn outline" onClick={onExportPlot} title={t("swExportPlotHint")}>{t("swExportPlot")}</button>
      {/* S15: the axes taken off lately, one click each to bring back */}
      {off.length > 0 && (
        <div className="sw-axes-off" role="group" aria-label={t("swAxesOff")}>
          <span className="hint">{t("swAxesOff")}</span>
          {off.map((a) => <button key={a} className="sw-tag" title={t("swAxisBack")} onClick={() => useSweeps.getState().toggleAxis(a, true)}>+ {colLabel(t, study, a)}</button>)}
          <button className="iconbtn" aria-label={t("swAxesOffForget")} title={t("swAxesOffForget")} onClick={() => setView({ axesOff: [] })}>×</button>
        </div>
      )}
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
  const flag = !!name && FLAG_COLS.has(name);
  const menu = (e: React.MouseEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const set = (colorBy: string | null) => useSweeps.getState().setView({ colorBy });
    openMenu({ clientX: r.left, clientY: r.bottom + 4, preventDefault() {}, stopPropagation() {} } as React.MouseEvent, [
      { label: t("swHoldsCol"), checked: name === "#holds", run: () => set("#holds") },
      ...(cols.has("#pareto") ? [{ label: t("swParetoCol"), checked: name === "#pareto", run: () => set("#pareto") }] : []),
      ...(cols.has("#partial") ? [{ label: t("swPartialCol"), checked: name === "#partial", run: () => set("#partial") }] : []),
      ...(cols.has("#robustHolds") ? [{ label: t("swRobustHoldsCol"), checked: name === "#robustHolds", run: () => set("#robustHolds") }] : []),
      ...(cols.has("#group") ? [{ label: t("swGroupsCol"), checked: name === "#group", run: () => set("#group") }] : []),
      { label: t("swColourNone"), checked: !name, run: () => set(null) },
      { label: t("swColourByAxisHint"), disabled: true, run: () => {} },
    ]);
  };
  let key: React.ReactNode;
  if (!c) key = <span className="hint">{t("swColourNone")}</span>;
  else if (flag) key = <><span style={{ color: HOLDS }}>■</span> {name === "#holds" ? t("swHolds") : name === "#pareto" ? t("swParetoCol") : name === "#robustHolds" ? t("swRobustHoldsCol") : t("swPartialCol")}
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
