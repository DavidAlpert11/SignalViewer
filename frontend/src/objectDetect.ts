import type { RunInfo } from "./api";
import type { Role } from "./mapObjects";
import { pathCuts } from "./signalGroups";

/*
 * N5: the map objects of a recording, found from the signal names. An object is a PREFIX: every
 * prefix (at any depth, with "." / "/" or "_") that has a latitude and a longitude under it - or a
 * north / east / down, east / north / up or ECEF x / y / z position - is a candidate. Its roles come
 * only from its own prefix and its sub-groups (nav.att.roll, nav.pos.lat), never from another
 * object's, except for the well-known flight-log groups (ArduPilot POS + ATT, PX4, MAVLink), which
 * are paired as before - in any file (owner's decision 5). Every choice carries its reason, as data,
 * for the dialog's *Why?*.
 */

export type ObjClass = "truth" | "navigation" | "receiver" | "other";
export type PosKind = "lla" | "ned" | "enu" | "ecef";
/** px / py / pz: a position in metres (north / east / down for NED, east / north / up for ENU, x / y / z for ECEF). */
export type DetRole = Role | "px" | "py" | "pz" | "vn" | "ve" | "vd";
export const POS_ROLES: DetRole[] = ["lat", "lon", "alt"];
export const VEC_ROLES: DetRole[] = ["px", "py", "pz"];
export const ATT_ROLES: DetRole[] = ["roll", "pitch", "yaw"];
export const QUAT: DetRole[] = ["qw", "qx", "qy", "qz"];

/** How a signal was chosen for a role. */
export interface RolePick {
  role: DetRole; id: string; name: string;
  /** prefix: a name right under the object's prefix; subgroup: under one of its sub-groups (att, pos...);
   *  known: a well-known flight-log group paired with this one (ATT for POS) */
  rule: "prefix" | "subgroup" | "known";
  word: string;            // the role word as written ("Lng", "phi", "alt_msl")
  exact: boolean;          // the role's own word (lat, lon, alt, roll, pitch, yaw), not an alias
  via?: string;            // the sub-group or the paired group
  unit?: { unit: string; from: "suffix" | "brackets" };
}
/** A name that almost gave a role, and why it did not. */
export interface NearMiss {
  id: string; name: string; role: DetRole;
  why: "spelling" | "suffix" | "glued" | "noframe";
  detail: string;          // the misspelt word, the suffix ("_cmd"), the glued word ("navLat")
}
export interface Candidate {
  key: string;             // runId + "|" + prefix: stable while the file is open
  runId: string; prefix: string;
  name: string;            // the proposed object name: the prefix (the file's name when there is none)
  cls: ObjClass;
  clsWhy: { word?: string; known?: string };   // the prefix word or the known group that decided the class
  pos: PosKind;
  picks: Partial<Record<DetRole, RolePick>>;
  attitude: "angles" | "quaternion" | "none";
  full: boolean;           // position (with altitude) and attitude
  missing: DetRole[];      // alt / roll / pitch / yaw not found
  nearMisses: NearMiss[];
  /** L3: where a NED / ENU position is placed on Earth - three lat / lon / alt signal ids. own: reference
   *  fields of its own prefix (PX4 ref_lat...); known: the flight-log group's origin (XKF1 -> ORGN[0]);
   *  sibling: an origin / ref / home / datum group beside or above it. moves: the log may reset it. */
  origin?: { ids: [string, string, string]; via: string; rule: "own" | "known" | "sibling"; moves?: boolean };
  /** L1: a position in metres written in another unit (cm, mm, km, ft): not added without a conversion */
  badUnit?: string;
  /** L2: an EKF lane of a flight log (XKF1[1] -> EKF3, 1) - for *Why?* */
  lane?: { ekf: string; n: number };
}
/** A prefix with some position but not enough for an object (lat without lon...). */
export interface Incomplete { runId: string; prefix: string; has: DetRole[]; missing: DetRole[] }
export interface Detection { candidates: Candidate[]; incomplete: Incomplete[]; nearMisses: NearMiss[] }

/* ---- the tables (one place, easy to extend) ---------------------------------------------------- */

const ALIASES: Record<DetRole, string[]> = {
  lat: ["lat", "latitude"], lon: ["lon", "lng", "long", "longitude"],
  alt: ["alt", "altitude", "height", "hgt", "alt_msl", "altmsl"],
  roll: ["roll", "phi"], pitch: ["pitch", "theta"], yaw: ["yaw", "heading", "hdg", "psi"],
  qw: ["qw", "q0", "q[0]", "q_w"], qx: ["qx", "q1", "q[1]", "q_x"], qy: ["qy", "q2", "q[2]", "q_y"], qz: ["qz", "q3", "q[3]", "q_z"],
  px: [], py: [], pz: [], vn: [], ve: [], vd: [],             // by frame / velocity sub-group, below
};
const OWN_WORD: Partial<Record<DetRole, string>> = { lat: "lat", lon: "lon", alt: "alt", roll: "roll", pitch: "pitch", yaw: "yaw" };
const WORD_ROLE = new Map<string, DetRole>();
for (const [r, ws] of Object.entries(ALIASES)) for (const w of ws) WORD_ROLE.set(w, r as DetRole);
/** Position in metres: the words, by frame. */
const XYZ: Record<string, DetRole> = { x: "px", y: "py", z: "pz" };
const FRAME_WORDS = new Set(["ecef", "ned", "enu"]);
/** L1: the axis words of a local position; NED or ENU is decided by the whole group (down -> NED,
 *  up -> ENU), not by each name. Single letters only right under a position / frame sub-group. */
type Axis = "n" | "e" | "d" | "u";
const AXIS_WORDS: Record<string, Axis> = { north: "n", east: "e", down: "d", up: "u" };
const AXIS_LETTERS: Record<string, Axis> = { n: "n", e: "e", d: "d", u: "u" };
const LOCAL_ROLE: Record<"ned" | "enu", Partial<Record<Axis, DetRole>>> = { ned: { n: "px", e: "py", d: "pz" }, enu: { e: "px", n: "py", u: "pz" } };
/** L1: a position in metres must be in metres to be added as it is (Q6: no silent scaling) */
const GLUED = /^(?:(ecef|ned|enu)([xyz])|([xyz])(ecef|ned|enu))$/i;
const METRES = new Set(["m", "meter", "meters", "metre", "metres"]);
const POS_SUB = new Set(["pos", "position", "lla", "geo"]);
/** N7: a velocity sub-group - its north / east / down (vn / ve / vd) compare between objects */
const VEL_SUB = new Set(["vel", "velocity", "v_ned", "velned"]);
const VEL_WORDS: Record<string, DetRole> = { north: "vn", east: "ve", down: "vd", n: "vn", e: "ve", d: "vd" };
export const VEL_ROLES: DetRole[] = ["vn", "ve", "vd"];
/** NED velocity fields right under an object's prefix (XKF1[0].VN, nav.vel_n) - one table, also used by
 *  frames.ts for its conversion suggestions. Taken only by a prefix that has a position. */
export const NED_VEL: string[][] = [["vn", "ve", "vd"], ["veln", "vele", "veld"], ["vel_n", "vel_e", "vel_d"], ["vel_n_m_s", "vel_e_m_s", "vel_d_m_s"]];
const FLAT_VEL = new Map<string, DetRole>();
for (const t of NED_VEL) t.forEach((w, i) => FLAT_VEL.set(w, VEL_ROLES[i]));
const FLAT_VEL_LAST = new Set([...FLAT_VEL.keys()].map((w) => w.split("_").pop()!));   // a quick test before the table
const ATT_SUB = new Set(["att", "attitude", "euler", "angles", "ori", "orientation", "q", "quat", "quaternion"]);
const UNIT_WORDS = new Set(["deg", "degs", "degrees", "rad", "rads", "radians", "m", "ft", "meters", "metres", "feet", "cm", "mm", "km"]);

/** Class words, matched to WHOLE segments of the prefix (a number may follow: nav2, ekf_3, gps[1]);
 *  the deepest matching segment decides (sim.nav is navigation). "ref" is left out (owner's Q2). */
export const CLASS_WORDS: Record<Exclude<ObjClass, "other">, string[]> = {
  truth: ["phys", "truth", "true", "sim", "model", "plant", "dyn"],
  navigation: ["nav", "ins", "ekf", "ahrs", "est", "kf", "filter", "fusion"],
  receiver: ["gps", "gnss", "rcv", "rx", "pvt", "ublox", "novatel"],
};
const CLASS_OF = new Map<string, ObjClass>();
for (const [c, ws] of Object.entries(CLASS_WORDS)) for (const w of ws) CLASS_OF.set(w, c as ObjClass);

/** Well-known flight-log groups (any file: a CSV exported from a .bin has the same names). The base
 *  name is the prefix without its instance ("GPS[1]" -> "GPS"). attFrom: the attitude group paired
 *  with a position group that has none of its own - for GPS only when the file has no POS (as before:
 *  a log's main object was GPS + ATT). */
/* L2: ned / vel - the group's own field words for a NED position / velocity (lower case); origin - the
 * groups (exact prefixes, in order) that hold its origin (L3); originMoves - the log may reset that
 * origin during the flight (the first value is used, said in *Why?*); skip - fields that are not what
 * their word says (PX4's local "heading" is not the attitude); order - the list order among the known
 * groups of one class (POS, then the EKF lanes, then AHR2); lane - the EKF an instance is a lane of. */
interface Known {
  cls: ObjClass; attFrom?: string[]; unlessAlso?: string;
  ned?: [string, string, string]; vel?: [string, string, string]; origin?: string[]; originMoves?: boolean;
  skip?: string[]; order?: number; lane?: string;
}
export const KNOWN_GROUPS: Record<string, Known> = {
  POS: { cls: "navigation", attFrom: ["ATT"], order: 0 },         // ArduPilot: the EKF's output
  GPS: { cls: "receiver", attFrom: ["ATT"], unlessAlso: "POS" },  // ArduPilot receivers (GPS[n])
  GPS2: { cls: "receiver" },
  // ArduPilot EKF3 / EKF2 lanes: NED from the EKF origin (ORGN[0]; ORGN[1] is the AHRS home), own angles
  XKF1: { cls: "navigation", ned: ["pn", "pe", "pd"], vel: ["vn", "ve", "vd"], origin: ["ORGN[0]", "ORGN"], order: 1, lane: "EKF3" },
  NKF1: { cls: "navigation", ned: ["pn", "pe", "pd"], vel: ["vn", "ve", "vd"], origin: ["ORGN[0]", "ORGN"], order: 1, lane: "EKF2" },
  AHR2: { cls: "navigation", order: 2 },                           // the backup AHRS: its own angles
  SIM: { cls: "truth" }, SIM2: { cls: "truth" },                   // SITL's simulated truth
  vehicle_global_position: { cls: "navigation", attFrom: ["vehicle_attitude"], order: 0 },   // PX4
  vehicle_local_position: { cls: "navigation", ned: ["x", "y", "z"], vel: ["vx", "vy", "vz"], attFrom: ["vehicle_attitude"],
    originMoves: true, skip: ["heading"], order: 1 },              // origin: its own ref_lat / ref_lon / ref_alt
  vehicle_gps_position: { cls: "receiver" }, sensor_gps: { cls: "receiver" },
  GLOBAL_POSITION_INT: { cls: "navigation", attFrom: ["ATTITUDE", "ATTITUDE_QUATERNION"], order: 0 },   // MAVLink (.tlog)
  LOCAL_POSITION_NED: { cls: "navigation", ned: ["x", "y", "z"], vel: ["vx", "vy", "vz"], attFrom: ["ATTITUDE", "ATTITUDE_QUATERNION"],
    origin: ["GPS_GLOBAL_ORIGIN", "HOME_POSITION"], originMoves: true, order: 1 },
  GPS_RAW_INT: { cls: "receiver" }, GPS2_RAW: { cls: "receiver" }, SIM_STATE: { cls: "truth" },
};
/** The flight-log groups whose plain x / y / z are north / east / down (frames.ts builds its pattern from it). */
export const NED_XYZ_GROUPS = Object.keys(KNOWN_GROUPS).filter((k) => KNOWN_GROUPS[k].ned?.[0] === "x");
const baseOf = (prefix: string) => prefix.replace(/\[[^\]]*\]$/, "");
/** Flight-log groups that only hold an attitude: a top-level "ATT" is that group, not a sub-group.
 *  (XKF1 / NKF1 left it in L2: they are known groups now - a position of their own - and the same
 *  "top-level group" rule protects them through KNOWN_GROUPS.) */
const ATT_GROUPS = new Set(["ATT", "ATTITUDE", "ATTITUDE_QUATERNION", "vehicle_attitude"]);
/** L3: origins and home points belong to the object they are the origin of - never objects themselves. */
const ORIGIN_WORDS = ["origin", "ref", "home", "datum"];
const ORIGIN_GROUPS = new Set(["ORGN", "HOME_POSITION", "GPS_GLOBAL_ORIGIN", "home_position", "HOME"]);
const lastWord = (prefix: string) => (prefix.split(/[./_]/).pop() ?? "").replace(/\[[^\]]*\]$/, "").toLowerCase();
const isOriginGroup = (prefix: string) => !!prefix && (ORIGIN_WORDS.includes(lastWord(prefix)) || ORIGIN_GROUPS.has(baseOf(prefix)));

/* ---- parsing one name -------------------------------------------------------------------------- */

const BRACKET_UNIT = /\s*[[(]([^[\]()]*)[\])]\s*$/;
/** frame: the position's frame when the name says it; axis without frame: north / east / down / up whose
 *  frame (NED or ENU) the whole group decides (role is then a placeholder). */
interface Parsed { role: DetRole; word: string; prefix: string; sub?: string; unit?: RolePick["unit"]; frame?: PosKind; axis?: Axis }
type Miss = Omit<NearMiss, "id" | "name"> & { prefix: string };

/** The role of a name and the object prefix it belongs to (null when it is no role), or a near miss. */
export function parseName(name: string): { hit?: Parsed; miss?: Miss } {
  let br = BRACKET_UNIT.exec(name);
  if (br && /^\d*$/.test(br[1].trim())) br = null;              // "q[0]" is an index, not a unit
  const base = br ? name.slice(0, br.index) : name;
  const p = pathCuts(base);
  // the path's segments ("phys", "att", "roll"); a name with no "." / "/" is one segment, split by "_" below
  const segs = p ? [base.slice(p.start, p.cuts[0] - 1), ...p.cuts.map((c, i) => base.slice(c, i + 1 < p.cuts.length ? p.cuts[i + 1] - 1 : base.length))] : [base];
  const leaf = segs[segs.length - 1];
  let parents = segs.slice(0, -1);
  const toks = leaf.split("_");
  let unit: RolePick["unit"] | undefined = br && br[1].trim() ? { unit: br[1].trim(), from: "brackets" } : undefined;
  if (toks.length > 1 && UNIT_WORDS.has(toks[toks.length - 1].toLowerCase())) unit = { unit: toks.pop()!, from: "suffix" };
  const low = toks.map((x) => x.toLowerCase());
  const join = (ps: string[], extra: string[]) => [ps.join("."), extra.join("_")].filter(Boolean).join(ps.length && extra.length ? "." : "");
  // L2: a known flight-log group's own fields (XKF1[0].PN, vehicle_local_position.x / vx, not its "heading")
  const kn = parents.length === 1 && toks.length === 1 ? KNOWN_GROUPS[baseOf(parents[0])] : undefined;
  if (kn) {
    if (kn.skip?.includes(low[0])) return {};
    const ni = kn.ned?.indexOf(low[0]) ?? -1;
    if (ni >= 0) return { hit: { role: VEC_ROLES[ni], word: toks[0], prefix: parents[0], unit, frame: "ned" } };
    const vi = kn.vel?.indexOf(low[0]) ?? -1;
    if (vi >= 0) return { hit: { role: VEL_ROLES[vi], word: toks[0], prefix: parents[0], unit } };
  }
  // the role word at the end of the leaf: two tokens (alt_msl, q_w) or one; what is before it is prefix
  let role: DetRole | undefined, word = "", n = 0;
  for (const k of [2, 1]) {
    if (low.length < k) continue;
    const w = low.slice(-k).join("_");
    const r = WORD_ROLE.get(w);
    if (r) { role = r; word = toks.slice(-k).join("_"); n = k; break; }
  }
  const before = toks.slice(0, toks.length - n);
  if (role) {
    // a sub-group of the object: nav.att.roll -> nav (att), nav.pos.lat -> nav (pos)
    const last = parents[parents.length - 1]?.toLowerCase();
    let sub: string | undefined;
    const isPos = role === "lat" || role === "lon" || role === "alt";
    const top = parents.length === 1 && (baseOf(parents[0]) in KNOWN_GROUPS || ATT_GROUPS.has(baseOf(parents[0])));   // "ATT.Roll": the log's group
    if (!before.length && last && !top && (isPos ? POS_SUB.has(last) : ATT_SUB.has(last))) { sub = parents[parents.length - 1]; parents = parents.slice(0, -1); }
    return { hit: { role, word, prefix: join(parents, before), sub, unit } };
  }
  // N7: a velocity: north / east / down under a velocity sub-group (nav.vel.north)
  const lw = low[low.length - 1];
  const lastSeg = parents[parents.length - 1]?.toLowerCase() ?? "";
  if (lw in VEL_WORDS && VEL_SUB.has(lastSeg) && toks.length === 1) {
    return { hit: { role: VEL_WORDS[lw], word: toks[0], prefix: join(parents.slice(0, -1), []), sub: parents[parents.length - 1], unit } };
  }
  // L1: a flat NED velocity right under the prefix (XKF1[0].VN, nav.vel_n); kept only where there is a position
  const lj = FLAT_VEL_LAST.has(lw) ? low.join("_") : "";
  if (lj) for (const [w, r] of FLAT_VEL) {
    if (lj === w || lj.endsWith("_" + w)) {
      const k = w.split("_").length;
      return { hit: { role: r, word: toks.slice(-k).join("_"), prefix: join(parents, toks.slice(0, -k)), unit } };
    }
  }
  // only a leaf ending in an axis or frame word can be a position in metres (most names are not: keep it fast)
  const pos = lw in XYZ || lw in AXIS_WORDS || lw in AXIS_LETTERS || FRAME_WORDS.has(lw) || GLUED.test(lw) ? metricPosition(toks, parents, join, unit) : undefined;
  if (pos) return pos;
  return { miss: nearMiss(toks, low, parents, join) };
}

/** L1: a position in metres. The frame from a frame word in any form - a sub-group (ned.x, pos.ned.x),
 *  a token (ecef_x, x_ecef, pos_ned_x) or glued to the axis (ecefX) - or, for north / east / down / up
 *  under a position sub-group (pos.north), decided later by the whole group. x / y / z need a frame word. */
function metricPosition(toks: string[], parents: string[], join: (ps: string[], extra: string[]) => string, unit: RolePick["unit"] | undefined): { hit?: Parsed; miss?: Miss } | undefined {
  // ecefX / Xecef: a frame word glued to its axis (only with a frame word: never a bare posX)
  const tk = toks.flatMap((x) => { const m = GLUED.exec(x); return m ? (m[1] ? [m[1], m[2]] : [m[3], m[4]]) : [x]; });
  const lo = tk.map((x) => x.toLowerCase());
  const isAxis = (w: string) => w in XYZ || w in AXIS_WORDS;
  let fw = "", aw = "", word = "", pre: string[] = [], ps = parents;
  const subs: string[] = [];
  const last = lo[lo.length - 1], prev = lo[lo.length - 2] ?? "";
  if (lo.length >= 2 && isAxis(last) && FRAME_WORDS.has(prev)) { fw = prev; aw = last; word = tk[tk.length - 1]; pre = tk.slice(0, -2); }
  else if (lo.length >= 2 && FRAME_WORDS.has(last) && isAxis(prev)) { fw = last; aw = prev; word = tk[tk.length - 2]; pre = tk.slice(0, -2); }
  else if (lo.length === 1 && (isAxis(last) || last in AXIS_LETTERS)) {
    aw = last; word = tk[0];
    const seg = (i: number) => ps[ps.length - i]?.toLowerCase() ?? "";
    if (FRAME_WORDS.has(seg(1))) { fw = seg(1); subs.unshift(ps[ps.length - 1]); ps = ps.slice(0, -1); }
    else if (!POS_SUB.has(seg(1))) return undefined;                    // nav.x, nav.n: not a position
  } else return undefined;
  if (pre.length && POS_SUB.has(pre[pre.length - 1].toLowerCase())) pre = pre.slice(0, -1);        // nav.pos_ned_x
  if (!pre.length && POS_SUB.has(ps[ps.length - 1]?.toLowerCase() ?? "")) { subs.unshift(ps[ps.length - 1]); ps = ps.slice(0, -1); }   // nav.pos.ned.x
  const prefix = join(ps, pre);
  const sub = subs.length ? subs.join(".") : undefined;
  if (fw === "ecef") return aw in XYZ ? { hit: { role: XYZ[aw], word, prefix, sub, unit, frame: "ecef" } } : {};
  if (fw === "ned" || fw === "enu") {
    const r = aw in XYZ ? XYZ[aw] : LOCAL_ROLE[fw][AXIS_WORDS[aw] ?? AXIS_LETTERS[aw]];
    return r ? { hit: { role: r, word, prefix, sub, unit, frame: fw } } : {};
  }
  // under a position sub-group with no frame word
  if (aw in XYZ) return { miss: { role: "px", why: "noframe", detail: tk.join("_"), prefix } };
  return { hit: { role: "px", word, prefix, sub, unit, axis: AXIS_WORDS[aw] ?? AXIS_LETTERS[aw] } };
}

/** Why a leaf almost gave a role: a suffix after the role word (yaw_cmd), a misspelling (lattitude),
 *  a role word glued to another (navLat, latDeg). */
function nearMiss(toks: string[], low: string[], parents: string[], join: (ps: string[], extra: string[]) => string): Miss | undefined {
  for (let i = 0; i < low.length - 1; i++) {                          // role word, then something else
    const r = WORD_ROLE.get(low[i]);
    if (r && OWN_WORD[r] !== undefined) return { role: r, why: "suffix", detail: "_" + toks.slice(i + 1).join("_"), prefix: join(parents, toks.slice(0, i)) };
  }
  const leaf = toks.join("_");
  const g = /^(.*[a-z0-9])(Lat|Lon|Lng|Alt|Roll|Pitch|Yaw|Heading|Latitude|Longitude|Altitude)$/.exec(leaf)
    ?? /^([Ll]at|[Ll]on|[Ll]ng|[Aa]lt|[Rr]oll|[Pp]itch|[Yy]aw|[Hh]eading|[Ll]atitude|[Ll]ongitude|[Aa]ltitude)([A-Z0-9].*)$/.exec(leaf);
  if (g) {
    const w = (WORD_ROLE.has(g[2].toLowerCase()) ? g[2] : g[1]).toLowerCase();
    const r = WORD_ROLE.get(w);
    if (r) return { role: r, why: "glued", detail: leaf, prefix: join(parents, []) };
  }
  const l = leaf.toLowerCase();
  if (l.length >= 5 && l.length <= 11 && /^[a-z]+$/.test(l)) {
    for (const [w, r] of WORD_ROLE) if (w.length >= 5 && Math.abs(w.length - l.length) <= 1 && edit1(l, w)) return { role: r, why: "spelling", detail: `${leaf} ≈ ${w}`, prefix: join(parents, []) };
  }
  return undefined;
}
/** Exactly one insertion, deletion or substitution apart. */
function edit1(a: string, b: string): boolean {
  if (a === b) return false;
  if (a.length > b.length) [a, b] = [b, a];
  let i = 0;
  while (i < a.length && a[i] === b[i]) i++;
  return a.length === b.length ? a.slice(i + 1) === b.slice(i + 1) : a.slice(i) === b.slice(i + 1);
}

/** The class of a prefix: the known group, else the deepest whole segment that is a class word. */
export function classify(prefix: string): { cls: ObjClass; word?: string; known?: string } {
  const k = KNOWN_GROUPS[baseOf(prefix)];
  if (k) return { cls: k.cls, known: baseOf(prefix) };
  const segs = prefix.split(/[./_]/).map((s) => s.replace(/\[[^\]]*\]$/, "").toLowerCase()).filter(Boolean);
  for (let i = segs.length - 1; i >= 0; i--) {
    const m = /^([a-z]+?)(\d+)?$/.exec(segs[i]);
    const c = m && CLASS_OF.get(m[1]);
    if (c) return { cls: c, word: segs[i] };
  }
  return { cls: "other" };
}

/* ---- the objects of a file --------------------------------------------------------------------- */

const RANK: Record<ObjClass, number> = { truth: 0, navigation: 1, receiver: 2, other: 3 };
const cache = new WeakMap<RunInfo["signals"], Detection>();

/** The candidates of one file, worked out once per signal list (a 5000-signal file in a few ms). */
export function detectObjects(run: Pick<RunInfo, "id" | "name" | "signals">): Detection {
  let d = cache.get(run.signals);
  if (!d) { d = detectNow(run); cache.set(run.signals, d); }
  return d;
}

function detectNow(run: Pick<RunInfo, "id" | "name" | "signals">): Detection {
  interface Group { prefix: string; picks: Partial<Record<DetRole, RolePick>>; frames: Partial<Record<PosKind, Partial<Record<DetRole, RolePick>>>>;
    loose: Partial<Record<Axis, RolePick>>; misses: NearMiss[] }
  const groups = new Map<string, Group>();
  const order: string[] = [];
  const get = (prefix: string) => {
    let g = groups.get(prefix);
    if (!g) { g = { prefix, picks: {}, frames: {}, loose: {}, misses: [] }; groups.set(prefix, g); order.push(prefix); }
    return g;
  };
  // the role's own word first (alt over alt_msl), then right under the prefix, then the shorter name
  const score = (x: RolePick) => (x.exact ? 0 : 2) + (x.rule === "prefix" ? 0 : 1);
  const better = (a: RolePick | undefined, b: RolePick) => !a || score(b) < score(a) || (score(b) === score(a) && b.name.length < a.name.length);
  const misses: (NearMiss & { prefix: string })[] = [];
  for (const s of run.signals) {
    const { hit, miss } = parseName(s.name);
    if (miss) { misses.push({ id: s.id, name: s.name, role: miss.role, why: miss.why, detail: miss.detail, prefix: miss.prefix }); continue; }
    if (!hit) continue;
    const g = get(hit.prefix);
    const pick: RolePick = { role: hit.role, id: s.id, name: s.name, rule: hit.sub ? "subgroup" : "prefix", word: hit.word,
      exact: OWN_WORD[hit.role] === hit.word.toLowerCase(), ...(hit.sub ? { via: hit.sub } : {}), ...(hit.unit ? { unit: hit.unit } : {}) };
    if (hit.axis && !hit.frame) { if (better(g.loose[hit.axis], pick)) g.loose[hit.axis] = pick; continue; }
    const into = hit.frame ? (g.frames[hit.frame] ??= {}) : g.picks;
    if (better(into[hit.role], pick)) into[hit.role] = pick;
  }
  // L1: north / east with down is NED, with up ENU - decided once per group (pos.north / east / up is ENU)
  for (const g of groups.values()) {
    const l = g.loose;
    if (!l.n || !l.e || !(l.d || l.u)) continue;
    const fr = l.d ? "ned" : "enu";
    const into = (g.frames[fr] ??= {});
    for (const [a, r] of Object.entries(LOCAL_ROLE[fr]) as [Axis, DetRole][]) {
      const p = l[a];
      if (p && better(into[r], { ...p, role: r })) into[r] = { ...p, role: r };
    }
  }

  const candidates: Candidate[] = [];
  const incomplete: Incomplete[] = [];
  const hasPos = (g: Group) => !!(g.picks.lat && g.picks.lon) || Object.values(g.frames).some((f) => f && VEC_ROLES.every((r) => f[r]));
  const prefixes = new Set(order.filter((p) => hasPos(groups.get(p)!) && !isOriginGroup(p)));
  const lla = (p: string) => { const g = groups.get(p); return g?.picks.lat && g.picks.lon && g.picks.alt ? g : undefined; };
  const parentOf = (p: string) => { const i = Math.max(p.lastIndexOf("."), p.lastIndexOf("_")); return i < 0 ? "" : p.slice(0, i); };
  const origins = order.filter((p) => isOriginGroup(p) && !ORIGIN_GROUPS.has(baseOf(p)) && lla(p)).map((p) => ({ p, owner: parentOf(p) }));
  /** L3: the origin of a local position: its own reference fields, the known group's origin, an origin group beside or above */
  const originOf = (prefix: string, kn: Known | undefined): Candidate["origin"] => {
    const make = (p: string, rule: "own" | "known" | "sibling") => { const g = lla(p)!; return { ids: [g.picks.lat!.id, g.picks.lon!.id, g.picks.alt!.id] as [string, string, string], via: p, rule, ...(kn?.originMoves ? { moves: true } : {}) }; };
    for (const w of ORIGIN_WORDS) for (const sep of [".", "_"]) { const p = prefix ? prefix + sep + w : w; if (lla(p)) return make(p, "own"); }
    for (const p of kn?.origin ?? []) if (lla(p)) return make(p, "known");
    // an origin group whose owner (the path before its last word) is above the prefix, or beside it with a
    // class word (nav.origin, nav_ref beside nav.tgt); the nearest (deepest owner) wins
    const above = (a: string) => a === "" || prefix.startsWith(a + ".") || prefix.startsWith(a + "_");
    let best: { p: string; depth: number } | undefined;
    for (const { p, owner } of origins) {
      if (owner === prefix) continue;
      const ok = above(owner) || (owner !== "" && parentOf(owner) === parentOf(prefix) && CLASS_OF.has(lastWord(owner).replace(/\d+$/, "")));
      if (ok && (!best || owner.length > best.depth)) best = { p, depth: owner.length };
    }
    return best ? make(best.p, "sibling") : undefined;
  };
  for (const prefix of order) {
    const g = groups.get(prefix)!;
    if (isOriginGroup(prefix)) continue;              // L3: an origin / home point is not an object
    if (!hasPos(g)) {
      const has = (Object.keys(g.picks) as DetRole[]).filter((r) => r === "lat" || r === "lon");
      if (has.length) incomplete.push({ runId: run.id, prefix, has, missing: (["lat", "lon"] as DetRole[]).filter((r) => !g.picks[r]) });
      continue;
    }
    const picks: Partial<Record<DetRole, RolePick>> = {};
    let pos: PosKind = "lla";
    if (g.picks.lat && g.picks.lon) { picks.lat = g.picks.lat; picks.lon = g.picks.lon; if (g.picks.alt) picks.alt = g.picks.alt; }
    else {
      pos = (["ned", "enu", "ecef"] as PosKind[]).find((f) => { const fr = g.frames[f]; return fr && VEC_ROLES.every((r) => fr[r]); })!;
      Object.assign(picks, g.frames[pos]);
    }
    for (const r of [...ATT_ROLES, ...QUAT]) if (g.picks[r]) picks[r] = g.picks[r];
    if (g.picks.vn && g.picks.ve) for (const r of VEL_ROLES) if (g.picks[r]) picks[r] = g.picks[r];   // N7: north and east at least
    // a known flight-log group with no attitude of its own: the paired attitude group, as before
    const kn = KNOWN_GROUPS[baseOf(prefix)];
    if (kn?.attFrom && !ATT_ROLES.some((r) => picks[r]) && !QUAT.every((r) => picks[r])
      && !(kn.unlessAlso && order.some((p) => baseOf(p) === kn.unlessAlso && prefixes.has(p)))) {
      for (const a of kn.attFrom) {
        const src = order.map((p) => groups.get(p)!).find((x) => baseOf(x.prefix) === a && (ATT_ROLES.some((r) => x.picks[r]) || QUAT.every((r) => x.picks[r])));
        if (!src) continue;
        for (const r of [...ATT_ROLES, ...QUAT]) { const p = src.picks[r]; if (p) picks[r] = { ...p, rule: "known", via: src.prefix }; }
        break;
      }
    }
    const angles = ATT_ROLES.some((r) => picks[r]);
    if (!angles) for (const r of ATT_ROLES) delete picks[r];
    if (angles || !QUAT.every((r) => picks[r])) for (const r of QUAT) delete picks[r];
    const attitude = angles ? "angles" : picks.qw ? "quaternion" : "none";
    const missing = [...(pos === "lla" && !picks.alt ? ["alt" as DetRole] : []), ...(attitude === "none" ? ATT_ROLES : attitude === "angles" ? ATT_ROLES.filter((r) => !picks[r]) : [])];
    const c = classify(prefix);
    const origin = pos === "ned" || pos === "enu" ? originOf(prefix, kn) : undefined;
    const u = pos === "lla" ? undefined : VEC_ROLES.map((r) => picks[r]?.unit?.unit).find((x) => x && !METRES.has(x.toLowerCase()));
    const inst = /\[(\d+)\]$/.exec(prefix);
    candidates.push({
      key: `${run.id}|${prefix}`, runId: run.id, prefix, name: prefix || run.name.replace(/\.[^.]+$/, ""),
      cls: c.cls, clsWhy: { ...(c.word ? { word: c.word } : {}), ...(c.known ? { known: c.known } : {}) },
      pos, picks, attitude, full: attitude !== "none" && (pos !== "lla" || !!picks.alt), missing, nearMisses: [],
      ...(origin ? { origin } : {}), ...(u ? { badUnit: u } : {}),
      ...(kn?.lane ? { lane: { ekf: kn.lane, n: inst ? Number(inst[1]) : 0 } } : {}),
    });
  }
  // a near miss belongs to the candidate of its prefix (or of the prefix above a sub-group)
  const byPrefix = new Map(candidates.map((c) => [c.prefix, c]));
  const loose: NearMiss[] = [];
  for (const m of misses) {
    const up = m.prefix.includes(".") ? m.prefix.slice(0, m.prefix.lastIndexOf(".")) : "";
    const c = byPrefix.get(m.prefix) ?? byPrefix.get(up);
    const { prefix: _p, ...nm } = m;
    if (c) { if (c.nearMisses.length < 8) c.nearMisses.push(nm); } else if (loose.length < 20) loose.push(nm);
  }
  // full objects first, then truth, navigation, receiver, other; among the known groups of a class their
  // order (POS, the EKF lanes, AHR2); otherwise in the file's order
  const at = new Map(candidates.map((c, i) => [c, i]));
  const ko = (c: Candidate) => KNOWN_GROUPS[baseOf(c.prefix)]?.order ?? 50;
  candidates.sort((a, b) => Number(b.full) - Number(a.full) || RANK[a.cls] - RANK[b.cls] || ko(a) - ko(b) || at.get(a)! - at.get(b)!);
  return { candidates, incomplete, nearMisses: loose };
}

/** The candidates of several files (the dialog's list), in the files' order. */
export const detectAll = (runs: Pick<RunInfo, "id" | "name" | "signals">[]) => runs.flatMap((r) => detectObjects(r).candidates);
