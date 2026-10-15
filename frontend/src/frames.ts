import { api, type RunInfo } from "./api";
import { useApp } from "./store";

/** Coordinate frames (svcore/analysis.py "frame"): one derived signal per output axis. */
export type Frame = "ned" | "enu" | "body" | "ecef" | "lla";
export type Qty = "vector" | "position";
export const AXES: Record<Frame, string[]> = { ned: ["N", "E", "D"], enu: ["E", "N", "U"], body: ["X", "Y", "Z"], ecef: ["X", "Y", "Z"], lla: ["lat", "lon", "alt"] };

/** Default group name: target_kind_source, e.g. "ned_Pos_lla" (LLA position -> NED). */
export const frameGroupName = (src: Frame, dst: Frame, qty: Qty) => `${dst}_${qty === "position" ? "Pos" : "Vec"}_${src}`;

/** A group name not taken yet ("ned_Pos_lla", "ned_Pos_lla_2"...), so the three axes always
 *  share one group - the backend's own "name (2)" would number each axis on its own. */
export function freeGroup(base: string, runs: RunInfo[], axes: string[]): string {
  const sigs = runs.find((r) => r.format === "derived")?.signals ?? [];
  const names = new Set(sigs.map((s) => s.name));
  const groups = new Set(sigs.map((s) => s.params?.group));
  const free = (g: string) => !groups.has(g) && axes.every((a) => !names.has(`${g}.${a}`));
  if (free(base)) return base;
  for (let k = 2; ; k++) if (free(`${base}_${k}`)) return `${base}_${k}`;
}

/**
 * Create the three axes of one conversion as one nested group "<group>.<axis>" (params.group,
 * saved with the formula, so sessions and autosave keep the nesting; old files have no group and
 * stay flat). All or nothing: if an axis fails the ones already made are removed.
 * Returns the ids in axis order.
 */
export async function createFrameGroup(sources: string[], params: Record<string, unknown>, group: string): Promise<string[]> {
  const axes = AXES[params.dst as Frame];
  // "/" separates run id and name in signal ids (the backend does the same to names)
  const g = freeGroup(group.trim().replace(/\//g, "∕"), useApp.getState().runs, axes);
  const made: string[] = [];
  try {
    for (const [axis, lbl] of axes.entries()) {
      const r = await api.createDerived("frame", sources, { ...params, axis, group: g }, `${g}.${lbl}`);
      useApp.setState({ runs: r.runs });
      made.push(r.id);
    }
  } catch (e) {
    for (const id of made) await api.deleteDerived(id.slice("derived/".length)).catch(() => {});
    if (made.length) useApp.setState({ runs: await api.listRuns() });
    throw e;
  }
  return made;
}
