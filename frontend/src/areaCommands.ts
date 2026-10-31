/* An area other than Recordings gives the app its keys and its commands here, when its code loads
 * (areas are lazy: the main bundle must not import them). App.tsx asks for the keys of the area on
 * screen, the command palette (Ctrl+K) for its commands. Recordings keeps its own, in App.tsx and
 * CommandPalette.tsx, as before. */
import type { AreaId } from "./areas";

export interface AreaCommand { id: string; label: string; group: string; run: () => void; keys?: string; icon?: "undo" | "redo" | "open" | "save" | "report" }
interface AreaHooks {
  /** the area's commands, in the language on screen */
  commands?: () => AreaCommand[];
  /** a key pressed while the area is on screen and nothing is being typed; true when it was used */
  onKey?: (e: KeyboardEvent) => boolean;
}

const hooks = new Map<AreaId, AreaHooks>();

export function registerArea(area: AreaId, h: AreaHooks) { hooks.set(area, h); }
export const areaCommands = (area: AreaId): AreaCommand[] => hooks.get(area)?.commands?.() ?? [];
export const areaKey = (area: AreaId, e: KeyboardEvent): boolean => hooks.get(area)?.onKey?.(e) ?? false;
