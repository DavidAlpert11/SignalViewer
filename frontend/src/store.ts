/* ----------------------------------------------------------------------------
   The app's state and the actions on it - the one place to import them from.
   Split by area under store/ (T42): model (the workspace's types), slices/ (the state by area:
   workspace + undo, data, view, live, ui), state (useApp), selectors (reading helpers) and
   actions/ (plots, layout, view, notes). Every workspace change goes through `commit`, which
   records it for Undo / Redo. Signals are referenced by stable ids "<runId>/<name>", never by index.
---------------------------------------------------------------------------- */
import { layoutActions } from "./store/actions/layout";
import { noteActions } from "./store/actions/notes";
import { plotActions } from "./store/actions/plots";
import { viewActions } from "./store/actions/view";

export * from "./store/model";
export * from "./store/types";
export {
  activeTab, plotHasContent, tabHasContent, rangeKey, yRangeKey, recordingExtent, shownSpan, fileLabel, signalName,
  newPlotSignal, nextColor, colorAllocator, colorByFile, fileMark, showFileTags, shade, placePlot, tabFullMessage, fitLayout, pickPath, alwaysState, laneScope, type LaneScope
} from "./store/selectors";
export { useApp, type AppState } from "./store/state";
export { setInspectorByUser } from "./store/inspector";

/** Every action, under the names they always had (`actions.addSignal`, `actions.goToTime`...). */
export const actions = { ...plotActions, ...layoutActions, ...viewActions, ...noteActions };
