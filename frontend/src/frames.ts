import { api, type RunInfo } from "./api";
import { useApp } from "./store";
import { guessRoles } from "./mapObjects";

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
  return createAxesGroup("frame", sources, params, group, AXES[params.dst as Frame]);
}

/** One derived signal per output axis (params.axis), as one group; all or nothing. */
async function createAxesGroup(op: string, sources: string[], params: Record<string, unknown>, group: string, axes: string[]): Promise<string[]> {
  // "/" separates run id and name in signal ids (the backend does the same to names)
  const g = freeGroup(group.trim().replace(/\//g, "∕"), useApp.getState().runs, axes);
  const made: string[] = [];
  try {
    for (const [axis, lbl] of axes.entries()) {
      const r = await api.createDerived(op, sources, { ...params, axis, group: g }, `${g}.${lbl}`);
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

/* ------------------------------------------------------------- Q102: vector smoothing */

export type SmoothKind = "vector" | "lla";
/** The axis names of a smoothed vector: lat / lon / alt, else the components' own field names
 *  (vn, ve, vd), else x / y / z. */
export function smoothLabels(sources: string[], kind: SmoothKind): string[] {
  if (kind === "lla") return ["lat", "lon", "alt"].slice(0, sources.length);
  const own = sources.map((s) => (s.split("/").pop() ?? s).split(".").pop()!.replace(/\s*\[[^\]]*\]$/, "").replace(/[^\w-]+/g, "_"));
  return new Set(own).size === own.length && own.every((x) => x) ? own : ["x", "y", "z"].slice(0, sources.length);
}
export const smoothGroupName = (window: number) => `smooth_${String(window).replace(".", "p")}s`;
/** A vector's 2-3 components smoothed over `window` seconds (svcore "vecsmooth"), as one group. */
export async function createSmoothGroup(sources: string[], window: number, kind: SmoothKind, group?: string, alignment = "linear"): Promise<string[]> {
  return createAxesGroup("vecsmooth", sources, { window, kind, alignment }, group || smoothGroupName(window), smoothLabels(sources, kind));
}

/* ------------------------------------------------------------------ T30: suggested conversions */

/** A conversion the names of a file suggest, with everything filled in; the user only confirms. */
export interface FrameSuggestion {
  key: string;
  group: string;                                  // where the signals come from ("GPS[0]", "IMU[0]")
  qty: Qty; src: Frame; dst: Frame;
  vec: string[];                                  // signal ids, in the source frame's axis order
  att?: { kind: "euler" | "quat"; sigs: string[]; unit: "deg" | "rad" };
}

const field = (n: string) => (n.split(".").pop() ?? n).replace(/ \[[^\]]*\]$/, "").toLowerCase();
const groupOf = (n: string) => (n.includes(".") ? n.slice(0, n.lastIndexOf(".")) : "");
/** Angle unit from the name ("[deg]" / "[rad]"); without one, MAVLink attitude is in radians and
 *  ArduPilot / most logs in degrees. */
const angleUnit = (n: string): "deg" | "rad" => (/\[rad\]/i.test(n) ? "rad" : /\[deg\]/i.test(n) ? "deg" : /^ATTITUDE\./.test(n) ? "rad" : "deg");

/** Axis triples by field name, in the frame's order (the first set that matches a group wins). */
const NED_VEL = [["vn", "ve", "vd"], ["veln", "vele", "veld"], ["vel_n", "vel_e", "vel_d"], ["vel_n_m_s", "vel_e_m_s", "vel_d_m_s"]];
const NED_XYZ_GROUPS = /^(LOCAL_POSITION_NED|vehicle_local_position)(\[\d+\])?$/i;     // x/y/z there are north/east/down
const BODY_ACC = [["accx", "accy", "accz"], ["xacc", "yacc", "zacc"], ["acc_x", "acc_y", "acc_z"]];

function triples(names: string[], sets: string[][], groupOk?: (g: string) => boolean): { group: string; names: string[] }[] {
  const byGroup = new Map<string, Map<string, string>>();
  for (const n of names) {
    const g = groupOf(n);
    if (groupOk && !groupOk(g)) continue;
    if (!byGroup.has(g)) byGroup.set(g, new Map());
    const m = byGroup.get(g)!;
    if (!m.has(field(n))) m.set(field(n), n);
  }
  const out: { group: string; names: string[] }[] = [];
  for (const [g, m] of byGroup) {
    const set = sets.find((s) => s.every((f) => m.has(f)));
    if (set) out.push({ group: g, names: set.map((f) => m.get(f)!) });
  }
  return out.sort((a, b) => a.group.localeCompare(b.group));
}

/**
 * Conversions a file's names suggest, the most common first: a geodetic position to NED, a NED
 * velocity into the body frame and a body acceleration into NED (both with the file's attitude).
 * Uses the same position / attitude guess as the map objects (guessRoles).
 */
export function suggestFrames(run: RunInfo | undefined): FrameSuggestion[] {
  if (!run || run.format === "derived") return [];
  const names = run.signals.filter((s) => !s.labels).map((s) => s.name);
  const id = (n: string) => `${run.id}/${n}`;
  const g = guessRoles(run);
  const out: FrameSuggestion[] = [];
  if (g.lat && g.lon && g.alt) {
    out.push({ key: "lla-ned", group: groupOf(g.lat.slice(run.id.length + 1)), qty: "position", src: "lla", dst: "ned", vec: [g.lat, g.lon, g.alt] });
  }
  const att: FrameSuggestion["att"] | undefined = g.roll && g.pitch && g.yaw
    ? { kind: "euler", sigs: [g.roll, g.pitch, g.yaw], unit: angleUnit(g.roll.slice(run.id.length + 1)) }
    : g.qw && g.qx && g.qy && g.qz ? { kind: "quat", sigs: [g.qw, g.qx, g.qy, g.qz], unit: "rad" } : undefined;
  if (att) {
    const vel = [...triples(names, NED_VEL), ...triples(names, [["vx", "vy", "vz"]], (x) => NED_XYZ_GROUPS.test(x))];
    for (const v of vel.slice(0, 2)) out.push({ key: `ned-body:${v.group}`, group: v.group, qty: "vector", src: "ned", dst: "body", vec: v.names.map(id), att });
    for (const a of triples(names, BODY_ACC).slice(0, 2)) out.push({ key: `body-ned:${a.group}`, group: a.group, qty: "vector", src: "body", dst: "ned", vec: a.names.map(id), att });
  }
  return out;
}
