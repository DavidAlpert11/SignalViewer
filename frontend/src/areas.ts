/* Work areas (Mission Planner style): each area is a whole activity with its own bar, panels and
 * tabs - Recordings (open recordings, plot, compare, investigate, report) is the first. The top row
 * (TopBar) is shared; everything under it belongs to the area on screen.
 *
 * Adding an area:
 *   1. add its id to AreaId and an entry to AREAS (its label goes through i18n.ts, en + he);
 *   2. give it a bar and a body in AREA_VIEWS (App.tsx) - lazy, so an area costs nothing until opened;
 *   3. its state goes into a slice of its own (store/slices/), never into the Recordings workspace
 *      (`ws`): sessions, templates and autosave of Recordings stay as they are (CLAUDE.md invariants);
 *   4. keyboard shortcuts of one area check `area` first (App.tsx, the keydown handler).
 * With one area the switcher shows only its name; a second entry here makes it a row of tabs. */
import type { TKey } from "./i18n";

export type AreaId = "recordings";

export interface AreaDef {
  id: AreaId;
  /** its name in the top row */
  label: TKey;
}

export const AREAS: readonly AreaDef[] = [
  { id: "recordings", label: "areaRecordings" },
];

export const DEFAULT_AREA: AreaId = "recordings";

export function areaDef(id: AreaId): AreaDef {
  return AREAS.find((a) => a.id === id) ?? AREAS[0];
}
