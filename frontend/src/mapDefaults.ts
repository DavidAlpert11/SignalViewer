/* P8 (1.26): Settings > "Map and objects" - the one module that reads and writes the `sv3.map.*` settings
   (kept by the app with prefs.ts). Settings apply to new things only: a new object, a new Map, the next
   export; an existing session, template or object is never changed by them. Things drawn live (names, the
   track's width, units, coordinates) are read when drawn. The store keeps a copy (`mapPrefs`) so the views
   re-render when one changes. Also the one formatter of distances (fmtDistance) and of positions
   (fmtCoord) for the app - the pages have theirs in report_assets/relation.js (svDist). */
// the store first: it loads prefs.ts itself (prefs -> api -> store would meet a store not made yet)
import { useApp, type MapObject, type ObjectKind, type Plot } from "./store";
import { getPrefValue, setPref } from "./prefs";

export type ObjClassKey = "truth" | "navigation" | "receiver" | "other";
export interface MapPrefs {
  icon: Record<ObjClassKey, ObjectKind>;
  camera: "free" | "top" | "centre" | "chase";
  drawing: "auto" | "flat";
  relation: "shown" | "hidden";
  names: "shown" | "hidden";
  trackWidth: number;
  modelSize: number;
  units: "metric" | "imperial";
  coords: "dd" | "dms" | "mgrs";
  rate: number;
  story: "on" | "off";
  storyLength: number;
}
export const MAP_DEFAULTS: MapPrefs = {
  icon: { truth: "aircraft", navigation: "aircraft", receiver: "aircraft", other: "aircraft" },
  camera: "free", drawing: "auto", relation: "shown", names: "shown", trackWidth: 2.5, modelSize: 26,
  units: "metric", coords: "dd", rate: 10, story: "on", storyLength: 90,
};
const KINDS: ObjectKind[] = ["aircraft", "uav", "drone", "missile", "ship", "vehicle"];
export const MAP_CHOICES = {
  kinds: KINDS,
  camera: ["free", "top", "centre", "chase"] as const,
  drawing: ["auto", "flat"] as const,
  relation: ["shown", "hidden"] as const,
  names: ["shown", "hidden"] as const,
  trackWidth: [2.5, 1.5, 4],
  modelSize: [26, 18, 36],
  units: ["metric", "imperial"] as const,
  coords: ["dd", "dms", "mgrs"] as const,
  rate: [10, 5, 2, 1],
  story: ["on", "off"] as const,
  storyLength: [90, 45, 180],
};
const CLASSES: ObjClassKey[] = ["truth", "navigation", "receiver", "other"];
const KEY = (k: string) => `sv3.map.${k}`;

/** The settings as kept, each checked against its choices (a bad or missing value: the default). */
export function readMapPrefs(): MapPrefs {
  const one = <T,>(k: string, ok: readonly T[], d: T): T => { const v = getPrefValue<T>(KEY(k)); return v !== undefined && ok.includes(v) ? v : d; };
  const icon = { ...MAP_DEFAULTS.icon };
  for (const c of CLASSES) icon[c] = one(`icon.${c}`, KINDS, MAP_DEFAULTS.icon[c]);
  return {
    icon,
    camera: one("camera", MAP_CHOICES.camera, MAP_DEFAULTS.camera),
    drawing: one("drawing", MAP_CHOICES.drawing, MAP_DEFAULTS.drawing),
    relation: one("relation", MAP_CHOICES.relation, MAP_DEFAULTS.relation),
    names: one("names", MAP_CHOICES.names, MAP_DEFAULTS.names),
    trackWidth: one("trackWidth", MAP_CHOICES.trackWidth, MAP_DEFAULTS.trackWidth),
    modelSize: one("modelSize", MAP_CHOICES.modelSize, MAP_DEFAULTS.modelSize),
    units: one("units", MAP_CHOICES.units, MAP_DEFAULTS.units),
    coords: one("coords", MAP_CHOICES.coords, MAP_DEFAULTS.coords),
    rate: one("rate", MAP_CHOICES.rate, MAP_DEFAULTS.rate),
    story: one("story", MAP_CHOICES.story, MAP_DEFAULTS.story),
    storyLength: one("storyLength", MAP_CHOICES.storyLength, MAP_DEFAULTS.storyLength),
  };
}
/** At start (after loadPrefs): the copy in the store, and the drawing choice (the light flat drawing). */
export function loadMapPrefs(): void {
  const m = readMapPrefs();
  useApp.setState({ mapPrefs: m, ...(m.drawing === "flat" ? { mapFlat: true } : {}) });
}
export const mapPrefs = (): MapPrefs => useApp.getState().mapPrefs;

type Flat = Omit<MapPrefs, "icon">;
export function setMapPref<K extends keyof Flat>(k: K, v: Flat[K]): void {
  setPref(KEY(k), v === MAP_DEFAULTS[k] ? null : v);
  useApp.setState({ mapPrefs: { ...mapPrefs(), [k]: v }, ...(k === "drawing" ? { mapFlat: v === "flat" } : {}) });
}
export function setIconFor(c: ObjClassKey, kind: ObjectKind): void {
  setPref(KEY(`icon.${c}`), kind === MAP_DEFAULTS.icon[c] ? null : kind);
  useApp.setState({ mapPrefs: { ...mapPrefs(), icon: { ...mapPrefs().icon, [c]: kind } } });
}
/** *Reset this group*. */
export function resetMapPrefs(): void {
  for (const c of CLASSES) setPref(KEY(`icon.${c}`), null);
  for (const k of Object.keys(MAP_DEFAULTS)) if (k !== "icon") setPref(KEY(k), null);
  setPref("elevationFolder", null);
  useApp.setState({ mapPrefs: { ...MAP_DEFAULTS, icon: { ...MAP_DEFAULTS.icon } }, mapFlat: false });
}
/** P5's *Elevation files*: the folder the backend reads `.hgt` files from (the key it reads). */
export const elevationFolder = (): string => (getPrefValue<string>("elevationFolder") ?? "");
export const setElevationFolder = (f: string) => setPref("elevationFolder", f.trim() || null);

/* ---- what a setting gives a new thing */
/** A new object's look by its class (the found-objects list, the object dialog). */
export function newObjectLook(cls?: string | null): Pick<MapObject, "kind"> & { size?: number } {
  const m = mapPrefs();
  const kind = m.icon[(CLASSES as string[]).includes(cls ?? "") ? (cls as ObjClassKey) : "other"];
  return { kind, ...(m.modelSize !== 26 ? { size: m.modelSize } : {}) };
}
/** A new Map's camera and relation box. `first`: its first object (On the object / Chase are on it). */
export function newMapFields(first?: string | null): Partial<Plot> {
  const m = mapPrefs();
  const cam: Partial<Plot> = m.camera === "free" ? {} : m.camera === "top" ? { camera: "top" }
    : first ? { followObject: first, ...(m.camera === "chase" ? { camera: "chase" as const } : {}) } : {};
  return { ...cam, ...(m.relation === "hidden" ? { relHidden: true } : {}) };
}

/* ---- the one formatter of distances and heights (metres / km, or feet / nautical miles) */
export function fmtDistance(m: number, lang: string, units: MapPrefs["units"] = mapPrefs().units): string {
  const loc = lang === "he" ? "he-IL" : "en-US";
  if (units === "imperial") {
    return Math.abs(m) < 1852 ? `${Math.round(m / 0.3048).toLocaleString(loc)} ft`
      : `${(m / 1852).toLocaleString(loc, { maximumFractionDigits: 2, minimumFractionDigits: 2 })} NM`;
  }
  return Math.abs(m) < 1000 ? `${Math.round(m).toLocaleString(loc)} m` : `${(m / 1000).toLocaleString(loc, { maximumFractionDigits: 2, minimumFractionDigits: 2 })} km`;
}

/* ---- positions: decimal degrees, degrees-minutes-seconds, MGRS */
function dms(v: number, pos: string, neg: string, prec: number): string {
  const a = Math.abs(v), d = Math.floor(a), mf = (a - d) * 60, mi = Math.floor(mf);
  const sd = Math.max(0, Math.min(2, prec - 4));            // seconds' decimals follow the zoom
  let s = (mf - mi) * 60, mm = mi, dd = d;
  if (Number(s.toFixed(sd)) >= 60) { s = 0; mm += 1; }
  if (mm >= 60) { mm = 0; dd += 1; }
  return `${dd}°${String(mm).padStart(2, "0")}′${s.toFixed(sd).padStart(sd ? 3 + sd : 2, "0")}″${v < 0 ? neg : pos}`;
}
/** A position as the setting asks; `prec`: decimals of a degree (the readout's, by the zoom). */
export function fmtCoord(lat: number, lon: number, prec = 6, style: MapPrefs["coords"] = mapPrefs().coords): string {
  if (style === "dms") return `${dms(lat, "N", "S", prec)} ${dms(lon, "E", "W", prec)}`;
  if (style === "mgrs") return mgrs(lat, lon, Math.max(1, Math.min(5, prec - 1))) ?? `${lat.toFixed(prec)}°, ${lon.toFixed(prec)}°`;
  return `${lat.toFixed(prec)}°, ${lon.toFixed(prec)}°`;
}

/** MGRS (WGS84, UTM zones with Norway's and Svalbard's exceptions) of a point between 80° S and 84° N;
 *  `digits` per coordinate (5 = 1 m). null outside (the polar UPS grid is not done). */
export function mgrs(lat: number, lon: number, digits = 5): string | null {
  if (!(lat >= -80 && lat < 84) || !Number.isFinite(lon)) return null;
  lon = ((lon + 180) % 360 + 360) % 360 - 180;
  let zone = Math.floor((lon + 180) / 6) + 1;
  if (lat >= 56 && lat < 64 && lon >= 3 && lon < 12) zone = 32;
  if (lat >= 72) zone = lon < 9 ? 31 : lon < 21 ? 33 : lon < 33 ? 35 : 37;
  const a = 6378137, f = 1 / 298.257223563, k0 = 0.9996, e2 = f * (2 - f), ep2 = e2 / (1 - e2);
  const r = Math.PI / 180, phi = lat * r, lam0 = ((zone - 1) * 6 - 180 + 3) * r;
  const N = a / Math.sqrt(1 - e2 * Math.sin(phi) ** 2), T = Math.tan(phi) ** 2, C = ep2 * Math.cos(phi) ** 2;
  const A = Math.cos(phi) * (lon * r - lam0);
  const M = a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * phi - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * Math.sin(2 * phi)
    + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * Math.sin(4 * phi) - (35 * e2 ** 3 / 3072) * Math.sin(6 * phi));
  const E = k0 * N * (A + (1 - T + C) * A ** 3 / 6 + (5 - 18 * T + T ** 2 + 72 * C - 58 * ep2) * A ** 5 / 120) + 500000;
  let Nn = k0 * (M + N * Math.tan(phi) * (A ** 2 / 2 + (5 - T + 9 * C + 4 * C ** 2) * A ** 4 / 24 + (61 - 58 * T + T ** 2 + 600 * C - 330 * ep2) * A ** 6 / 720));
  if (lat < 0) Nn += 10000000;
  const band = "CDEFGHJKLMNPQRSTUVWXX"[Math.floor((lat + 80) / 8)];
  const col = ["ABCDEFGH", "JKLMNPQR", "STUVWXYZ"][(zone - 1) % 3][Math.floor(E / 100000) - 1];
  const rows = "ABCDEFGHJKLMNPQRSTUV";
  const row = rows[(Math.floor(Nn / 100000) + (zone % 2 === 0 ? 5 : 0)) % 20];
  const cut = (v: number) => String(Math.floor((v % 100000) / 10 ** (5 - digits))).padStart(digits, "0");
  return `${zone}${band} ${col}${row} ${cut(E)} ${cut(Nn)}`;
}
