/* P7 (1.26): places, as in Google Earth - named points, lines and areas on every Map, and saved camera views.
   Two lists: the session's (Workspace.places - Undo, travels with the session and the template) and My
   places (the user's own, in every session: the app keeps them in ~/.signalviewer/places.json, a file that
   can be given to a colleague). Their actions are in store/actions/places.ts; this module reads them. */
import { api } from "./api";
import { useApp, type Place, type PlaceIcon } from "./store";

/** Every place, the session's first; `mine` says which list it is in. */
export type ListedPlace = Place & { mine: boolean };
export function allPlaces(st = useApp.getState()): ListedPlace[] {
  return [...(st.ws.places ?? []).map((p) => ({ ...p, mine: false })), ...st.myPlaces.map((p) => ({ ...p, mine: true }))];
}
/** What a Map draws: the shown points, lines and areas (a saved view is not drawn). */
export function shownPlaces(st = useApp.getState()): ListedPlace[] {
  return allPlaces(st).filter((p) => !p.hidden && p.kind !== "view");
}
export const findPlace = (id: string | null | undefined, st = useApp.getState()) => (id ? allPlaces(st).find((p) => p.id === id) ?? null : null);

/** Metres on the ground between two points (haversine, as the map's readout). */
export function placeDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371008.8, r = Math.PI / 180;
  const a = Math.sin(((lat2 - lat1) * r) / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(((lon2 - lon1) * r) / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
}

/** The nearest shown place within `maxM` (a line / area: its nearest vertex) - the mouse readout's
 *  "1.24 km from Runway 27". */
export function nearestPlace(lat: number, lon: number, places: Place[], maxM = 50_000): { place: Place; d: number } | null {
  let best: { place: Place; d: number } | null = null;
  for (const p of places) {
    if (p.kind === "view") continue;
    const pts = p.points?.length ? p.points : [[p.lat, p.lon] as [number, number]];
    for (const [a, b] of pts) {
      const d = placeDistance(lat, lon, a, b);
      if (d <= maxM && (!best || d < best.d)) best = { place: p, d };
    }
  }
  return best;
}

/** The box of the shown places [south, west, north, east] - Fit on a Map with no objects. */
export function placesBounds(places: Place[]): [number, number, number, number] | null {
  let s = Infinity, w = Infinity, n = -Infinity, e = -Infinity;
  for (const p of places) for (const [a, b] of p.points?.length ? p.points : [[p.lat, p.lon] as [number, number]]) {
    s = Math.min(s, a); n = Math.max(n, a); w = Math.min(w, b); e = Math.max(e, b);
  }
  return Number.isFinite(s) ? [s, w, n, e] : null;
}

/* the icons: small vector shapes (no image files), one colour, a white outline so they read on any map */
const SHAPES: Record<PlaceIcon, string> = {
  pin: '<path d="M12 22s-7-7.2-7-12.2A7 7 0 0 1 19 9.8C19 14.8 12 22 12 22z"/><circle cx="12" cy="9.8" r="2.6" fill="#fff" stroke="none"/>',
  airfield: '<circle cx="12" cy="12" r="9.5"/><path d="M12 5.5v13M8 8.5l8 7M16 8.5l-8 7" stroke="#fff" stroke-width="2" fill="none"/>',
  target: '<circle cx="12" cy="12" r="9.5"/><circle cx="12" cy="12" r="5.5" fill="#fff" stroke="none"/><circle cx="12" cy="12" r="2.6"/>',
  antenna: '<path d="M12 9l-5 13h2.6l2.4-6.4 2.4 6.4H17z"/><circle cx="12" cy="7" r="2.6"/><path d="M6.2 3.5a8 8 0 0 0 0 7M17.8 3.5a8 8 0 0 1 0 7" fill="none" stroke-width="2"/>',
  flag: '<path d="M5 22V3"/><path d="M5 3.5h12.5l-3 4 3 4H5z"/>',
  home: '<path d="M3 11.5 12 3.5l9 8V21h-6.5v-6h-5v6H3z"/>',
  camera: '<rect x="2.5" y="7" width="19" height="13" rx="2.5"/><path d="M8 7l1.8-3h4.4L16 7z"/><circle cx="12" cy="13.5" r="3.6" fill="#fff" stroke="none"/>',
};
/** The icon as an SVG data URL (Cesium billboards, <img>), in the place's colour. */
export function placeIconSvg(icon: PlaceIcon | undefined, color: string | undefined, px = 24): string {
  const c = color || "#d29922";
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${px}" height="${px}" viewBox="0 0 24 24" fill="${c}" stroke="${c === "#ffffff" ? "#333" : "#fff"}" stroke-width="1.4" stroke-linejoin="round">${SHAPES[icon ?? "pin"] ?? SHAPES.pin}</svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}
export const PLACE_COLOR = "#d29922";

/* ---- My places: loaded once at start, saved shortly after each change (one request for a burst) */
let saveTimer = 0;
export async function loadMyPlaces(): Promise<void> {
  try { useApp.setState({ myPlaces: (await api.myPlaces()).places ?? [] }); } catch { /* the app keeps none yet */ }
}
export function setMyPlaces(list: Place[]): void {
  useApp.setState({ myPlaces: list });
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => {
    api.putMyPlaces(useApp.getState().myPlaces).catch((e) => useApp.getState().toast({ kind: "error", text: String((e as Error).message) }));
  }, 300);
}

/** "32.687, 35.39" or 32°41'13"N 35°23'24"E -> a position (the backend's one parser), else null. */
export async function parsePlace(q: string): Promise<{ lat: number; lon: number } | null> {
  if (!q.trim()) return null;
  try { const r = await api.parsePlace(q); return r.ok && r.lat !== undefined && r.lon !== undefined ? { lat: r.lat, lon: r.lon } : null; } catch { return null; }
}
