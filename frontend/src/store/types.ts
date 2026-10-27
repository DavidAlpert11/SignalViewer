export type Range = [number, number] | null;
/** One step of zoom history: the x window before it, and the value-axis window if that changed too. */
export interface ZoomStep { x: Range; y?: { key: string; r: Range } }
export type ZoomMode = "x" | "y" | "xy";
export type NewFilesMode = "ask" | "auto" | "ignore";
export interface CursorState { on: boolean; dual: boolean; t1: number | null; t2: number | null; active?: 1 | 2 }
export interface Toast { id: string; kind: "info" | "error"; text: string; action?: { label: string; run: () => void }; ms?: number;
  /** its action undoes the LAST workspace change: valid only until the next change / undo / redo */
  undoesWs?: boolean }
export type PanelId = "data" | "analysis" | "compare" | "report" | "log" | "fleet" | "investigate";
/** One condition in one file: its stretches [start, end] as shown, or why it could not be looked for. */
export interface CondResult { intervals?: [number, number][]; count?: number; total?: number; missing?: string[];
  error?: string; ranges?: Record<string, [number, number]>; cut?: boolean }
export type LogMarkers = "off" | "important" | "all";
export type PlayMode = "cursor" | "draw" | "window";
export interface MenuItem { label: string; icon?: string; run: () => void; disabled?: boolean; danger?: boolean; sep?: boolean;
  /** one of a set of choices (a plot's type): the current one is marked */
  checked?: boolean;
  /** its keyboard shortcut, shown at the end (Ctrl+O) */
  keys?: string;
  /** a submenu (T21b): the item opens these instead of running */
  items?: MenuItem[] }
export interface PickerRequest {
  mode: "open" | "save" | "folder";     // folder: choose a folder (only folders are listed)
  title: string;
  exts?: string[];                 // e.g. [".svsession"]; default: data files
  defaultName?: string;
  resolve: (path: string | null) => void;
}
/** A dashed line computed but not kept (Create signals > Preview). */
export interface PreviewLine { label: string; x: Float64Array; y: Float32Array }

