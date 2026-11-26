/* CC22: the map's own parts that know nothing of React (from GeoChart.tsx): the Web-Mercator projection, fitting a
   view to tracks, the tiles shared by every map (fetched through the app, an LRU cache), the attributions, and the
   offline map's country borders and place names (loaded once). */
import type { Country } from "../worldCountries";

export interface Track { id: string; lon: Float64Array; lat: Float64Array; t: Float64Array }
/** cx, cy: map centre in Web-Mercator world units (0..1); z: zoom (256 * 2^z pixels across the world). */
export interface View { cx: number; cy: number; z: number }

/* The offline map: tiles the app draws itself from bundled data (terrain, water, roads), so a map
   works on a machine with no internet; also what fills in for an online tile that cannot be had. */
export const OFFLINE_MAXZ = 14;
export const offlineSrc = (dark: boolean) => (dark ? "offline_topo_dark" : "offline_topo");
export const OVERLAY: Record<string, string> = { light: "light_ref", dark: "dark_ref" };    // labels, drawn over the map
const ESRI_ATT = "Esri, HERE, Garmin, © OpenStreetMap contributors, GIS User Community";
export const ATTRIB: Record<string, string> = {
  osm: "© OpenStreetMap contributors", esri: ESRI_ATT, light: ESRI_ATT, dark: ESRI_ATT,
  satellite: "Tiles © Esri — Esri, Maxar, Earthstar Geographics, GIS User Community",
  satroads: "Tiles © Esri — Esri, Maxar, Earthstar Geographics, HERE, Garmin, © OpenStreetMap contributors, GIS User Community",
  topo: "© OpenStreetMap contributors, SRTM | © OpenTopoMap (CC-BY-SA)",
  offline: "Natural Earth · Terrain Tiles (Mapzen: SRTM, GMTED2010, ETOPO1) · © OpenStreetMap contributors",
};

/* --------------------------------------------------------------- projection */
const LAT_MAX = 85.05112878;
export const mx = (lon: number) => (lon + 180) / 360;
export const my = (lat: number) => {
  const s = Math.sin((Math.max(-LAT_MAX, Math.min(LAT_MAX, lat)) * Math.PI) / 180);
  return 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI);
};
export const lonOf = (x: number) => x * 360 - 180;
export const latOf = (y: number) => (Math.atan(Math.sinh(Math.PI * (1 - 2 * y))) * 180) / Math.PI;

/** Longitudes given as 0..360 are shown as -180..180, like the map. */
export function normLon(lon: Float64Array): Float64Array {
  let lo = Infinity, hi = -Infinity;
  for (const v of lon) if (Number.isFinite(v)) { if (v < lo) lo = v; if (v > hi) hi = v; }
  if (lo >= 0 && hi > 180 && hi <= 360) return Float64Array.from(lon, (v) => (v > 180 ? v - 360 : v));
  return lon;
}

export const HINT_PREF = "mapHintSeen";
export const reducedMotion = () => { try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; } };

export function fitView(tracks: Track[], w: number, h: number): View | null {
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const t of tracks) for (let i = 0; i < t.lon.length; i++) {
    const a = t.lon[i], b = t.lat[i];
    if (!Number.isFinite(a) || !Number.isFinite(b) || Math.abs(b) > 90 || Math.abs(a) > 360) continue;
    const X = mx(a), Y = my(b);
    if (X < x0) x0 = X; if (X > x1) x1 = X; if (Y < y0) y0 = Y; if (Y > y1) y1 = Y;
  }
  if (!Number.isFinite(x0)) return null;
  const dx = Math.max(x1 - x0, 2e-9) * 1.25, dy = Math.max(y1 - y0, 2e-9) * 1.25;
  const z = Math.log2(Math.min(w / dx, h / dy) / 256);
  return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, z: Math.max(1, Math.min(21, z)) };
}

/* --------------------------------------------------------------- tiles (shared by every map) */
const tileCache = new Map<string, HTMLImageElement | "failed">();
const loading = new Set<string>();
let listeners: (() => void)[] = [];
/** Called whenever a tile arrives or fails (every map redraws); returns the unsubscribe. */
export function onTile(f: () => void): () => void {
  listeners.push(f);
  return () => { listeners = listeners.filter((g) => g !== f); };
}
/** A tile already asked for: its picture, "failed", or undefined (not yet). */
export const tileState = (key: string) => tileCache.get(key);
export function getTile(src: string, z: number, x: number, y: number): HTMLImageElement | null {
  const key = `${src}/${z}/${x}/${y}`;
  const hit = tileCache.get(key);
  if (hit === "failed") return null;
  if (hit) { tileCache.delete(key); tileCache.set(key, hit); return hit; }          // LRU order
  if (!loading.has(key) && loading.size < 24) {
    loading.add(key);
    const img = new Image();
    img.onload = () => { loading.delete(key); tileCache.set(key, img); trim(); listeners.forEach((f) => f()); };
    img.onerror = () => { loading.delete(key); tileCache.set(key, "failed"); listeners.forEach((f) => f()); };
    img.src = `/api/tiles/${key}`;
  }
  return null;
}
function trim() {
  while (tileCache.size > 800) tileCache.delete(tileCache.keys().next().value!);
}

let countriesP: Promise<Country[]> | null = null;
export const loadCountries = () => (countriesP ??= import("../worldCountries").then((m) => m.COUNTRIES));
/** Place / airport names for the offline map (x lon, y lat, n English, h Hebrew, r rank: 1 = most important). */
export interface Place { x: number; y: number; n: string; h: string; r: number; a?: number }
let placesP: Promise<Place[]> | null = null;
export const loadPlaces = () => (placesP ??= fetch("/api/basemap/places").then((r) => r.json()).then((d) => d.places as Place[]).catch(() => []));

