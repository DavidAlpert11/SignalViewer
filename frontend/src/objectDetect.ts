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
export type DetRole = Role | "px" | "py" | "pz";
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
  px: [], py: [], pz: [],                                     // by frame, below
};
const OWN_WORD: Partial<Record<DetRole, string>> = { lat: "lat", lon: "lon", alt: "alt", roll: "roll", pitch: "pitch", yaw: "yaw" };
const WORD_ROLE = new Map<string, DetRole>();
for (const [r, ws] of Object.entries(ALIASES)) for (const w of ws) WORD_ROLE.set(w, r as DetRole);
/** Position in metres: the words, by frame. */
const NED_WORDS: Record<string, DetRole> = { north: "px", east: "py", down: "pz" };
const ENU_WORDS: Record<string, DetRole> = { east: "px", north: "py", up: "pz" };
const XYZ: Record<string, DetRole> = { x: "px", y: "py", z: "pz" };
const FRAME_WORDS = new Set(["ecef", "ned", "enu"]);
const POS_SUB = new Set(["pos", "position", "lla", "geo"]);
const ATT_SUB = new Set(["att", "attitude", "euler", "angles", "ori", "orientation", "q", "quat", "quaternion"]);
const UNIT_WORDS = new Set(["deg", "degs", "degrees", "rad", "rads", "radians", "m", "ft", "meters", "metres", "feet"]);

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
interface Known { cls: ObjClass; attFrom?: string[]; unlessAlso?: string }
export const KNOWN_GROUPS: Record<string, Known> = {
  POS: { cls: "navigation", attFrom: ["ATT"] },                   // ArduPilot: the EKF's output
  GPS: { cls: "receiver", attFrom: ["ATT"], unlessAlso: "POS" },  // ArduPilot receivers (GPS[n])
  GPS2: { cls: "receiver" },
  AHR2: { cls: "navigation" },                                     // the backup AHRS: its own angles
  SIM: { cls: "truth" }, SIM2: { cls: "truth" },                   // SITL's simulated truth
  vehicle_global_position: { cls: "navigation", attFrom: ["vehicle_attitude"] },   // PX4
  vehicle_gps_position: { cls: "receiver" }, sensor_gps: { cls: "receiver" },
  GLOBAL_POSITION_INT: { cls: "navigation", attFrom: ["ATTITUDE", "ATTITUDE_QUATERNION"] },   // MAVLink (.tlog)
  GPS_RAW_INT: { cls: "receiver" }, GPS2_RAW: { cls: "receiver" }, SIM_STATE: { cls: "truth" },
};
const baseOf = (prefix: string) => prefix.replace(/\[[^\]]*\]$/, "");
/** Flight-log groups that only hold an attitude: a top-level "ATT" is that group, not a sub-group. */
const ATT_GROUPS = new Set(["ATT", "ATTITUDE", "ATTITUDE_QUATERNION", "XKF1", "NKF1", "vehicle_attitude"]);

/* ---- parsing one name -------------------------------------------------------------------------- */

const BRACKET_UNIT = /\s*[[(]([^[\]()]*)[\])]\s*$/;
interface Parsed { role: DetRole; word: string; prefix: string; sub?: string; unit?: RolePick["unit"]; frame?: PosKind }
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
  // the role word at the end of the leaf: two tokens (alt_msl, q_w) or one; what is before it is prefix
  let role: DetRole | undefined, word = "", n = 0;
  for (const k of [2, 1]) {
    if (low.length < k) continue;
    const w = low.slice(-k).join("_");
    const r = WORD_ROLE.get(w);
    if (r) { role = r; word = toks.slice(-k).join("_"); n = k; break; }
  }
  const before = toks.slice(0, toks.length - n);
  const join = (ps: string[], extra: string[]) => [ps.join("."), extra.join("_")].filter(Boolean).join(ps.length && extra.length ? "." : "");
  if (role) {
    // a sub-group of the object: nav.att.roll -> nav (att), nav.pos.lat -> nav (pos)
    const last = parents[parents.length - 1]?.toLowerCase();
    let sub: string | undefined;
    const isPos = role === "lat" || role === "lon" || role === "alt";
    const top = parents.length === 1 && (baseOf(parents[0]) in KNOWN_GROUPS || ATT_GROUPS.has(baseOf(parents[0])));   // "ATT.Roll": the log's group
    if (!before.length && last && !top && (isPos ? POS_SUB.has(last) : ATT_SUB.has(last))) { sub = parents[parents.length - 1]; parents = parents.slice(0, -1); }
    return { hit: { role, word, prefix: join(parents, before), sub, unit } };
  }
  // a position in metres: north / east / down (or up) under a position or frame sub-group, x / y / z under a frame word
  const lw = low[low.length - 1];
  const lastSeg = parents[parents.length - 1]?.toLowerCase() ?? "";
  const frameTok = low.length > 1 ? low[low.length - 2] : "";        // ecef_x
  const frameWord = FRAME_WORDS.has(frameTok) ? frameTok : FRAME_WORDS.has(lastSeg) ? lastSeg : "";
  if (lw in XYZ || lw in NED_WORDS || lw === "up") {
    const subOk = POS_SUB.has(lastSeg) || FRAME_WORDS.has(lastSeg) || !!frameWord;
    const frame: PosKind | undefined = frameWord ? (frameWord as PosKind) : lw in XYZ ? undefined : lw === "up" ? "enu" : subOk ? "ned" : undefined;
    const r = frame === "enu" ? ENU_WORDS[lw] : frame === "ned" ? NED_WORDS[lw] : frame === "ecef" ? XYZ[lw] : undefined;
    if (frame && r && subOk) {
      const pre = frameTok === frameWord && frameWord ? toks.slice(0, -2) : toks.slice(0, -1);
      const ps = POS_SUB.has(lastSeg) || FRAME_WORDS.has(lastSeg) ? parents.slice(0, -1) : parents;
      return { hit: { role: r, word: toks[toks.length - 1], prefix: join(ps, pre), sub: subOk && ps !== parents ? parents[parents.length - 1] : undefined, unit, frame } };
    }
    if (lw in XYZ && POS_SUB.has(lastSeg)) return { miss: { role: "px", why: "noframe", detail: leaf, prefix: join(parents.slice(0, -1), toks.slice(0, -1)) } };
    return {};
  }
  return { miss: nearMiss(toks, low, parents, join) };
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
  interface Group { prefix: string; picks: Partial<Record<DetRole, RolePick>>; frames: Partial<Record<PosKind, Partial<Record<DetRole, RolePick>>>>; misses: NearMiss[] }
  const groups = new Map<string, Group>();
  const order: string[] = [];
  const get = (prefix: string) => {
    let g = groups.get(prefix);
    if (!g) { g = { prefix, picks: {}, frames: {}, misses: [] }; groups.set(prefix, g); order.push(prefix); }
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
    const into = hit.frame ? (g.frames[hit.frame] ??= {}) : g.picks;
    if (better(into[hit.role], pick)) into[hit.role] = pick;
  }

  const candidates: Candidate[] = [];
  const incomplete: Incomplete[] = [];
  const hasPos = (g: Group) => !!(g.picks.lat && g.picks.lon) || Object.values(g.frames).some((f) => f && VEC_ROLES.every((r) => f[r]));
  const prefixes = new Set(order.filter((p) => hasPos(groups.get(p)!)));
  for (const prefix of order) {
    const g = groups.get(prefix)!;
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
    candidates.push({
      key: `${run.id}|${prefix}`, runId: run.id, prefix, name: prefix || run.name.replace(/\.[^.]+$/, ""),
      cls: c.cls, clsWhy: { ...(c.word ? { word: c.word } : {}), ...(c.known ? { known: c.known } : {}) },
      pos, picks, attitude, full: attitude !== "none" && (pos !== "lla" || !!picks.alt), missing, nearMisses: [],
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
  // full objects first, then truth, navigation, receiver, other; otherwise in the file's order
  const at = new Map(candidates.map((c, i) => [c, i]));
  candidates.sort((a, b) => Number(b.full) - Number(a.full) || RANK[a.cls] - RANK[b.cls] || at.get(a)! - at.get(b)!);
  return { candidates, incomplete, nearMisses: loose };
}

/** The candidates of several files (the dialog's list), in the files' order. */
export const detectAll = (runs: Pick<RunInfo, "id" | "name" | "signals">[]) => runs.flatMap((r) => detectObjects(r).candidates);
