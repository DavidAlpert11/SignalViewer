import type { RunInfo } from "./api";

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
  if (!g) { g = guessRolesNow(run); guessed.set(run.signals, g); }
  return { ...g };
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


/** An object's signals on one time axis (from the server). */
export interface ObjTrack { t: Float64Array; lat: Float64Array; lon: Float64Array; yaw: Float32Array | null; course: Float32Array; units: Record<string, "deg" | "rad"> }

/** Where an object is at time t (null outside its own time span), and where it points (degrees from
 *  north): its heading signal if it has one, else its direction of travel. */
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
  const loc = lang === "he" ? "he-IL" : "en-US";
  return Math.abs(m) < 1000 ? `${Math.round(m).toLocaleString(loc)} m` : `${(m / 1000).toLocaleString(loc, { maximumFractionDigits: 2, minimumFractionDigits: 2 })} km`;
}
