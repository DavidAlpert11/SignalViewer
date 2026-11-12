import type { RunInfo } from "./api";
import { fmtDistance as fmtDistanceUnits } from "./mapDefaults";
import type { MapObject } from "./store";
import { detectObjects } from "./objectDetect";

/* Which signals of a file give a map object's position and attitude, guessed from their names. */

export type Role = "lat" | "lon" | "alt" | "yaw" | "pitch" | "roll" | "qw" | "qx" | "qy" | "qz";
export const QUAT_ROLES: Role[] = ["qw", "qx", "qy", "qz"];
export const ROLES: Role[] = ["lat", "lon", "alt", "yaw", "pitch", "roll"];   // (the quaternion: QUAT_ROLES)
/** A word in a signal name: after the start or a separator, before the end or a separator. */
const word = (alts: string) => new RegExp(`(^|[._\\s/[])(${alts})(?=$|[._\\s[\\]])`, "i");
const PATTERNS: Record<Role, RegExp> = {
  lat: word("lat|latitude"),
  lon: word("lon|lng|long|longitude"),
  alt: word("alt|altitude|height|alt_msl|altmsl"),
  yaw: word("yaw|heading|hdg"),
  pitch: word("pitch"),
  roll: word("roll"),
  qw: /(^|[._\s/[])q(\[0\]|0|_?w)$/i, qx: /(^|[._\s/[])q(\[1\]|1|_?x)$/i, qy: /(^|[._\s/[])q(\[2\]|2|_?y)$/i, qz: /(^|[._\s/[])q(\[3\]|3|_?z)$/i,
};
/** Could this name be any role? (every role pattern needs one of these) */
const MAYBE = /lat|lon|lng|alt|height|yaw|head|hdg|pitch|roll|(^|[._\s/[])q(\[[0-3]\]|[0-3]|_?[wxyz])$/i;
const POS_GROUPS = /^(gps|pos|global_position_int|vehicle_global_position|gps_raw_int|ahr2)\b/i;
const ATT_GROUPS = /^(att|attitude|vehicle_attitude|ahr2|attitude_quaternion)\b/i;
const group = (name: string) => (name.includes(".") ? name.slice(0, name.lastIndexOf(".")) : "");

/** Signals of a file that look like each role, best first. */
/* Guessed once per file (per signal list): the "position on the map" template asks for every file
   whenever the suggestions are worked out, and testing every name of a 5000-signal file each time
   cost ~200 ms (measured). */
const guessed = new WeakMap<RunInfo["signals"], Partial<Record<Role, string>>>();
export function guessRoles(run: RunInfo): Partial<Record<Role, string>> {
  let g = guessed.get(run.signals);
  if (!g) { g = fromDetection(run) ?? guessRolesNow(run); guessed.set(run.signals, g); }
  return { ...g };
}
/** N5: the file's first object found by objectDetect (full objects first, truth first) - its roles all
 *  from one prefix (or a known log group), so the form and the frame suggestions never mix sources.
 *  The old guess stays for files where nothing is found as an object (a lone "heading" signal...). */
function fromDetection(run: RunInfo): Partial<Record<Role, string>> | null {
  const c = detectObjects(run).candidates.find((x) => x.pos === "lla");
  if (!c) return null;
  const out: Partial<Record<Role, string>> = {};
  for (const r of [...ROLES, ...QUAT_ROLES]) { const p = c.picks[r]; if (p) out[r] = p.id; }
  return out;
}

function guessRolesNow(run: RunInfo): Partial<Record<Role, string>> {
  // one pass with one test keeps only the few names that could be a role at all; the role patterns
  // then run on those (5000 names x 20 patterns each time was the cost)
  const names = run.signals.map((s) => s.name).filter((n) => MAYBE.test(n));
  const pick = (role: Role, prefer?: (n: string) => number) => {
    const hits = names.filter((n) => PATTERNS[role].test(n.split(".").pop() ?? n) || PATTERNS[role].test(n));
    hits.sort((a, b) => (prefer ? prefer(b) - prefer(a) : 0) || a.length - b.length);
    return hits[0];
  };
  const out: Partial<Record<Role, string>> = {};
  out.lat = pick("lat", (n) => (POS_GROUPS.test(n) ? 2 : 0) + (/^gps\./i.test(n) ? 1 : 0));
  const g = out.lat ? group(out.lat) : "";
  const same = (n: string) => (group(n) === g ? 5 : 0);
  out.lon = pick("lon", (n) => same(n) + (POS_GROUPS.test(n) ? 1 : 0));
  out.alt = pick("alt", (n) => same(n) + (POS_GROUPS.test(n) ? 1 : 0));
  for (const r of ["yaw", "pitch", "roll"] as const) out[r] = pick(r, (n) => (ATT_GROUPS.test(n) ? 3 : 0) + same(n));
  // no angles but a quaternion in the attitude group (PX4: vehicle_attitude.q[0..3]): that, all four from one group
  if (!out.yaw && !out.pitch && !out.roll) {
    const qw = pick("qw", (n) => (ATT_GROUPS.test(n) ? 3 : 0));
    const g = qw ? group(qw) : "";
    const q = { qw, qx: pick("qx", (n) => (group(n) === g ? 5 : 0)), qy: pick("qy", (n) => (group(n) === g ? 5 : 0)), qz: pick("qz", (n) => (group(n) === g ? 5 : 0)) };
    if (q.qw && q.qx && q.qy && q.qz && [q.qx, q.qy, q.qz].every((n) => group(n!) === g)) Object.assign(out, q);
  }
  for (const r of [...ROLES, ...QUAT_ROLES]) if (out[r]) out[r] = `${run.id}/${out[r]}`; else delete out[r];
  return out;
}


/* ---- N5: where an object's attitude comes from (owner's decision 3) ---------------------------- */

/** It has angles of its own (three angles or a whole quaternion). */
export const hasOwnAttitude = (o: Pick<MapObject, "yaw" | "pitch" | "roll" | "qw" | "qx" | "qy" | "qz">) =>
  !!(o.yaw || o.pitch || o.roll || (o.qw && o.qx && o.qy && o.qz));

export type AttitudeOf = { kind: "own" } | { kind: "motion" } | { kind: "borrowed"; from: MapObject } | { kind: "none" };
/** What its attitude is drawn from. Its own signals win; "motion" or another object's (that object's
 *  own angles only - no chains; a source gone or without angles falls back to motion). An object
 *  with no angles and no source (made before) is "none": it points along its course, as before. */
export function attitudeOf(o: MapObject, all: MapObject[]): AttitudeOf {
  if (hasOwnAttitude(o)) return { kind: "own" };
  const src = o.attitudeSource;
  if (src && typeof src === "object") {
    const from = all.find((x) => x.id === src.object && x.id !== o.id);
    return from && hasOwnAttitude(from) ? { kind: "borrowed", from } : { kind: "motion" };
  }
  return src === "motion" ? { kind: "motion" } : { kind: "none" };
}
/** The request for its track: a borrowed attitude is the other object's angle signals (the server
 *  puts them on this object's times, the short way round); a motion attitude is worked out there. */
export function trackRequest(o: MapObject, all: MapObject[]) {
  const a = attitudeOf(o, all);
  if (a.kind === "borrowed") {
    const f = a.from;
    return { ...o, yaw: f.yaw ?? null, pitch: f.pitch ?? null, roll: f.roll ?? null, qw: f.qw ?? null, qx: f.qx ?? null, qy: f.qy ?? null, qz: f.qz ?? null,
      angleUnit: f.angleUnit, attitude: null };
  }
  return { ...o, attitude: a.kind === "motion" ? ("motion" as const) : null, minSpeed: o.minSpeed };
}
/** What its fetched track depends on (the views refetch when it changes). */
export function trackKey(o: MapObject, all: MapObject[]): string {
  const r = trackRequest(o, all);
  return [o.id, r.lat, r.lon, r.alt, r.yaw, r.pitch, r.roll, r.qw, r.qx, r.qy, r.qz, o.trackColor, o.colorSig, r.attitude, o.minSpeed].join(":");
}
/** The angle unit its attitude is drawn in (a borrowed one: the source's). */
export const angleUnitOf = (o: MapObject, all: MapObject[]) => { const a = attitudeOf(o, all); return a.kind === "borrowed" ? a.from.angleUnit : o.angleUnit; };
/** Its attitude is not its own (from motion or borrowed): drawn outlined, with a ≈ on its chip. */
export const derivedAttitude = (o: MapObject, all: MapObject[]) => { const k = attitudeOf(o, all).kind; return k === "motion" || k === "borrowed"; };
/** The look of a class (owner's spec): navigation dashed, a receiver as points, the rest a line. */
export const trackOfClass = (cls?: MapObject["cls"]): MapObject["track"] =>
  cls === "navigation" ? "dash" : cls === "receiver" ? "points" : undefined;

/** An object's signals on one time axis (from the server). */
export interface ObjTrack { t: Float64Array; lat: Float64Array; lon: Float64Array; yaw: Float32Array | null; course: Float32Array; units: Record<string, "deg" | "rad">;
  color?: Float32Array | null; alt?: Float32Array | null }

/** N7: the altitude at time t (linear between samples; null without an altitude or outside it). */
export function altAt(tr: ObjTrack, t: number): number | null {
  const a = tr.alt, n = tr.t.length;
  if (!a || !n || t < tr.t[0] || t > tr.t[n - 1]) return null;
  let lo = 0, hi = n - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (tr.t[m] <= t) lo = m; else hi = m; }
  const f = tr.t[hi] > tr.t[lo] ? (t - tr.t[lo]) / (tr.t[hi] - tr.t[lo]) : 0;
  const v = Number.isFinite(a[lo]) && Number.isFinite(a[hi]) ? a[lo] + (a[hi] - a[lo]) * f : Number.isFinite(a[lo]) ? a[lo] : a[hi];
  return Number.isFinite(v) ? v : null;
}

/* A track coloured by a signal (owner, 2026-11-03): a colour per point, and the key that says what
   each colour is. A state (the flight mode): a colour per value, named by the signal's texts. A value:
   a colour scale from its lowest to its highest along the track, in steps (each a stretch of track). */
const STATE_COLORS = ["#3D8BFD", "#F07B3F", "#2FBF9F", "#E5677A", "#9B7BFF", "#B8A33A", "#4FC3E8", "#D08CE8", "#7CC35A", "#FF8FB1", "#A0522D", "#6B7280"];
const RAMP = ["#440154", "#482878", "#3e4989", "#31688e", "#26828e", "#1f9e89", "#35b779", "#6ece58", "#b5de2b", "#fde725"];   // viridis
export interface TrackColors { at: (string | null)[]; key: { color: string; label: string }[]; ramp?: { lo: number; hi: number; colors: string[] } }
export function trackColors(mode: "state" | "value", v: Float32Array, labels: Record<string, string> | null,
  fmt: (x: number) => string, stateCol?: (code: number) => string): TrackColors | null {
  const at: (string | null)[] = new Array(v.length).fill(null);
  if (mode === "state") {
    const order: number[] = [];
    for (const x of v) if (Number.isFinite(x) && !order.includes(x)) order.push(x);
    if (!order.length) return null;
    // the state lanes' colour for each code (the map and the plots agree), else one per value seen
    const col = new Map(order.map((x, i) => [x, stateCol ? stateCol(x) : STATE_COLORS[i % STATE_COLORS.length]]));
    for (let i = 0; i < v.length; i++) at[i] = Number.isFinite(v[i]) ? col.get(v[i])! : null;
    return { at, key: order.map((x) => ({ color: col.get(x)!, label: labels?.[String(x)] ?? fmt(x) })) };
  }
  let lo = Infinity, hi = -Infinity;
  for (const x of v) if (Number.isFinite(x)) { if (x < lo) lo = x; if (x > hi) hi = x; }
  if (!Number.isFinite(lo)) return null;
  const span = hi > lo ? hi - lo : 1;
  for (let i = 0; i < v.length; i++) {
    if (!Number.isFinite(v[i])) continue;
    at[i] = RAMP[Math.min(RAMP.length - 1, Math.floor(((v[i] - lo) / span) * RAMP.length))];
  }
  return { at, key: [], ramp: { lo, hi, colors: RAMP } };
}
/** The points [i0, i1) in stretches of one colour (each stretch shares its first point with the
 *  previous one, so the line has no gaps). */
export function colorRuns(at: (string | null)[], i0: number, i1: number): { a: number; b: number; color: string }[] {
  const out: { a: number; b: number; color: string }[] = [];
  let a = i0;
  for (let i = i0 + 1; i <= i1; i++) {
    if (i === i1 || at[i] !== at[a]) {
      if (at[a]) out.push({ a: Math.max(i0, a - (a > i0 ? 1 : 0)), b: i, color: at[a]! });
      a = i;
    }
  }
  return out;
}

/** Where an object is at time t (null outside its own time span), and where it points (degrees from
 *  north): its heading signal if it has one, else its direction of travel. */
/** The time an object is drawn at. Live mode: a time past the end of its track holds its LAST state
 *  (the other files, or a faster message such as the IMU, are already further on - the vehicle must
 *  not vanish from the map until its next GPS sample arrives). Otherwise the time as it is. */
export function trackTime(tr: { t: ArrayLike<number> }, t: number | null, live: boolean): number {
  const n = tr.t.length;
  if (!n) return t ?? NaN;
  if (t === null) return tr.t[n - 1];
  return live && t > tr.t[n - 1] ? tr.t[n - 1] : t;
}

export function objectAt(tr: ObjTrack, t: number, unit: "auto" | "deg" | "rad" = "auto"): { lat: number; lon: number; heading: number | null } | null {
  const n = tr.t.length;
  if (!n || t < tr.t[0] || t > tr.t[n - 1]) return null;
  let lo = 0, hi = n - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (tr.t[m] <= t) lo = m; else hi = m; }
  const f = tr.t[hi] > tr.t[lo] ? (t - tr.t[lo]) / (tr.t[hi] - tr.t[lo]) : 0;
  const lerp = (a: number, b: number) => (Number.isFinite(a) && Number.isFinite(b) ? a + (b - a) * f : Number.isFinite(a) ? a : b);
  const lat = lerp(tr.lat[lo], tr.lat[hi]), lon = lerp(tr.lon[lo], tr.lon[hi]);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  const ang = (a: number, b: number) => {                   // the short way round
    if (!Number.isFinite(a)) return b;
    if (!Number.isFinite(b)) return a;
    const d = ((b - a + 540) % 360) - 180;
    return a + d * f;
  };
  let heading: number | null = null;
  if (tr.yaw) {
    const rad = unit === "rad" || (unit === "auto" && tr.units.yaw === "rad");
    const k = rad ? 180 / Math.PI : 1;
    heading = ang(tr.yaw[lo] * k, tr.yaw[hi] * k);
  }
  if (heading === null || !Number.isFinite(heading)) heading = ang(tr.course[lo], tr.course[hi]);
  return { lat, lon, heading: Number.isFinite(heading) ? heading : null };
}



const RTL = /[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\uFB1D-\uFDFF\uFE70-\uFEFF]/;
/** Text in display order for drawing that knows no direction (3D labels draw characters left to
 *  right): a right-to-left text (Hebrew, Arabic) has its runs reversed and the characters of its
 *  RTL runs reversed, while numbers and Latin words keep their own order ("מטוס 12" stays readable). */
export function visualOrder(text: string): string {
  if (!RTL.test(text)) return text;
  const runs = text.match(/[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\uFB1D-\uFDFF\uFE70-\uFEFF]+|[^\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\uFB1D-\uFDFF\uFE70-\uFEFF]+/g) ?? [text];
  const mirror: Record<string, string> = { "(": ")", ")": "(", "[": "]", "]": "[", "<": ">", ">": "<" };
  return runs.reverse().map((r) => {
    if (RTL.test(r)) return [...r].reverse().join("");
    if (/^[\s\p{P}]+$/u.test(r)) return [...r].reverse().map((c) => mirror[c] ?? c).join("");
    // a number / Latin word keeps its order; the spaces around it change sides
    const m = r.match(/^(\s*)(.*?)(\s*)$/s)!;
    return m[3] + m[2] + m[1];
  }).join("");
}

/* ---------------------------------------------------------------- distances on the earth */
const R_EARTH = 6371008.8;
const rad = (d: number) => (d * Math.PI) / 180;
/** Great-circle distance in metres. */
export function groundDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const a = Math.sin(rad(lat2 - lat1) / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lon2 - lon1) / 2) ** 2;
  return 2 * R_EARTH * Math.asin(Math.min(1, Math.sqrt(a)));
}
/** Initial bearing from point 1 to point 2, degrees from north (0..360). */
export function bearing(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const y = Math.sin(rad(lon2 - lon1)) * Math.cos(rad(lat2));
  const x = Math.cos(rad(lat1)) * Math.sin(rad(lat2)) - Math.sin(rad(lat1)) * Math.cos(rad(lat2)) * Math.cos(rad(lon2 - lon1));
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}
/** Metres as "850 m" / "12.35 km". */
export function fmtDistance(m: number, lang: string): string {
  return fmtDistanceUnits(m, lang);                // P8: metres / km or feet / NM - mapDefaults.ts is the one formatter
}

/** P6: the objects a map draws - every one not hidden. Drawing loops and Fit use this; lookups of
 *  another object (a borrowed attitude, the pair) use the whole list. */
export function shownObjects(plot: { objects?: MapObject[] }): MapObject[] {
  return (plot.objects ?? []).filter((o) => !o.hidden);
}

/** P4 (1.26): the Map is the 3D view. A plot is "the Map" when it is a 3D map, or a map ("geo") with objects
 *  (a 2D-era map: drawn in 3D, From above). A map without objects stays the plain lon / lat X-Y on a map. */
export function isMapPlot(p: { mode?: string; objects?: MapObject[] }): boolean {
  return p.mode === "3d" || (p.mode === "geo" && (p.objects?.length ?? 0) > 0);
}

export type MapCamera = "free" | "top" | "centre" | "chase" | "lookat" | "cockpit";

/** P4: the Map's camera - General, From above, On the object, Chase (Look at: from one object to another).
 *  Saved values are unchanged: absent on a "geo" plot = From above (it was a 2D map), absent on a "3d" plot
 *  = General or, with a followed object, On the object (as before). */
export function mapCamera(p: { mode?: string; camera?: string; followObject?: string | null }): MapCamera {
  if (p.camera === "top") return "top";
  if (p.camera === "free") return "free";
  if (!p.camera && p.mode === "geo") return "top";
  if (!p.followObject) return "free";
  return p.camera === "chase" ? "chase" : p.camera === "lookat" ? "lookat" : p.camera === "cockpit" ? "cockpit" : "centre";
}
