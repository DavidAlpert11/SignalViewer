/* Panels, dialogs, menus, toasts, selection, language / theme. UI state, never saved. */
import type { StoreApi } from "zustand";
import type { Lang } from "../../i18n";
import { uid } from "../model";
import type { MenuItem, PanelId, PickerRequest, Toast } from "../types";
import type { AppState } from "../state";
import { inspectorPref } from "../inspector";

export interface UiSlice {
  theme: "light" | "dark";
  lang: Lang;
  panel: PanelId | null;
  inspectorOpen: boolean;
  inspectorScope: "active" | "all";
  selected: { plotId: string; sig: string } | null;
  multi: { plotId: string; sig: string }[];     // Ctrl+click several legend chips
  paletteOpen: boolean;
  paletteMode: "all" | "open";     // T24: Ctrl+P lists recent files and folders, favourites
  browserStart: string | null;     // T24: the folder the file dialog opens in once (quick open)
  browserOpen: boolean;
  picker: PickerRequest | null;
  importPaths: string[] | null;
  toasts: Toast[];
  menu: { x: number; y: number; items: MenuItem[] } | null;
  startCard: import("../../smartStart").StartCard | null;   // T29: suggestions after the first file (UI only)
  syncFor: string | null;          // the file whose time the sync dialog aligns
  templatesTarget: string | null;  // templates dialog opened for this file (its templates first)
  templatesNew: "tab" | "all" | "collection" | null;   // open the library on a new template (current / all tabs) or collection
  templatesSelect: string | null;  // open the library with this template selected (suggestions in the file panel)
  objectDialog: { plotId: string; objectId?: string } | null;   // adding / editing a map object
  placeDialog: string | null;      // T17c: putting an XYZ plot's tracks on a map / 3D plot (the XYZ plot's id)
  axisDialog: string | null;            // plot id whose axis limits are being edited
  reportPreviewHtml: string | null;
  templatesOpen: boolean;
  transformTargets: string[] | null;     // signals whose change dialog is open
  listSel: string[];                      // signals selected in the file list (Ctrl / Shift + click, or from search)
  listAnchor: string | null;              // where a Shift + click range starts
  listSelUsed: boolean;                   // an action ran on listSel: the next pick starts a new selection
  analysisSeed: string[] | null;          // signals handed to the Analysis panel from the file list
  retarget: { state: any; title: string; fromCurrent: boolean } | null;   // "open with new files"
  sameWorkFor: string | null;              // Q87: "add a run with the same work" as this run
  timeAxisFor: string | null;              // the Time axis dialog of this file (column, unit, offset)
  compareTable: { rows: import("../../api").CompareAllRow[]; baseline: string; fileCount: number; tol: boolean;
    segment?: import("../../segments").SegmentChoice } | null;
  promptDialog: { title: string; label: string; value: string; multiline?: boolean; resolve: (v: string | null) => void } | null;
  uiScale: 1 | 1.12 | 1.25;
  helpOpen: boolean;
  guideOpen: boolean;          // T55: the user guide dialog
  settingsOpen: boolean;       // T18
  /** F28: how the timeline writes time - seconds as recorded (like the axes, the cursor, the
   *  Inspector) or a clock from the start of the recording (m:ss) */
  timeFormat: "seconds" | "clock";
  /** F24: each plot's room left / right of its plot area (px), so a column of plots shares one -
   *  the time axes line up. Reported by the charts; UI only. */
  gutters: Record<string, [number, number]>;

  set: (p: Partial<AppState>) => void;
  toast: (t: Omit<Toast, "id">) => void;
  dismiss: (id: string) => void;
}

export const uiSlice = (set: StoreApi<AppState>["setState"], get: StoreApi<AppState>["getState"]): UiSlice => ({
  theme: window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark",
  lang: (navigator.language || "").startsWith("he") ? "he" : "en",
  panel: "data",
  inspectorOpen: inspectorPref() === "open",   // closed until there is something to show (T08)
  inspectorScope: "active",
  selected: null,
  multi: [],
  paletteOpen: false,
  paletteMode: "all",
  browserStart: null,
  browserOpen: false,
  picker: null,
  importPaths: null,
  toasts: [],
  menu: null,
  startCard: null,
  syncFor: null,
  templatesTarget: null,
  templatesNew: null,
  templatesSelect: null,
  objectDialog: null,
  placeDialog: null,
  axisDialog: null,
  reportPreviewHtml: null,
  templatesOpen: false,
  transformTargets: null,
  listSel: [],
  listSelUsed: false,
  listAnchor: null,
  analysisSeed: null,
  retarget: null,
  sameWorkFor: null,
  timeAxisFor: null,
  compareTable: null,
  promptDialog: null,
  uiScale: 1,
  helpOpen: false,
  guideOpen: false,
  settingsOpen: false,
  timeFormat: "seconds",
  gutters: {},

  set: (p) => set(p),
  toast: (t) => {
    const id = uid("m");
    // the same message again replaces the old one instead of stacking up
    set({ toasts: [...get().toasts.filter((x) => x.text !== t.text), { ...t, id }] });
    window.setTimeout(() => get().dismiss(id), t.ms ?? (t.kind === "error" ? 9000 : 4000));
  },
  dismiss: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
});
