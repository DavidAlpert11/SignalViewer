/* M1 / M3 / M4: the map's backgrounds beyond the built-in ones - My maps (an MBTiles file or the user's own tile
   server, layers "my:<id>", backend app/mymaps.py) and the kept areas (app/tilekeep.py). One small cache of My
   maps for every map view (the picker, the 2D map's zoom limit and attribution, the 3D globe). */
import { useSyncExternalStore } from "react";
import { call } from "./api";

export interface MyMap {
  id: string; src: string; kind: "mbtiles" | "xyz" | "tms"; name: string; path?: string; url?: string;
  minzoom: number; maxzoom: number; bounds: [number, number, number, number] | null; attribution: string;
  ok: boolean; problem: string; localOnly: boolean;
}
export interface KeepEstimate {
  src: string; bounds: number[]; zmin: number; zmax: number; maxZoom: number; tiles: number; have: number; bytes: number;
  allowed: boolean; reason: string; tooMany: boolean; limit: number; network: boolean;
}
export interface KeptArea { id: string; name: string; src: string; bounds: number[]; zmin: number; zmax: number; tiles: number; created: string; present: number; bytes: number }
export interface KeepProgress { running: boolean; id?: string; name?: string; total?: number; done?: number; failed?: number; stopped?: boolean; error?: string }

const INITIAL: MyMap[] = [];
let maps: MyMap[] = INITIAL;
let loaded = false;
const subs = new Set<() => void>();
const emit = () => subs.forEach((f) => f());

export async function loadMyMaps(): Promise<MyMap[]> {
  try {
    maps = (await call<{ maps: MyMap[] }>("/api/mymaps")).maps;
  } catch {
    maps = [];
  }
  loaded = true;
  emit();
  return maps;
}

/** the first view that asks for the maps loads them - on subscribe, not while rendering (a side effect there) */
function subscribe(f: () => void): () => void {
  subs.add(f);
  if (!loaded) { loaded = true; void loadMyMaps(); }
  return () => { subs.delete(f); };
}

/** My maps (loaded once, then kept current by add / remove). */
export function useMyMaps(): MyMap[] {
  return useSyncExternalStore(subscribe, () => maps);
}

export const myMapsLoaded = (): boolean => loaded && maps !== INITIAL;
export const isMyMap = (b: string): boolean => b.startsWith("my:");
export const myMap = (b: string): MyMap | undefined => maps.find((m) => m.src === b);

export async function addMyMap(body: { kind: string; path?: string; url?: string; name?: string; maxzoom?: number | null }): Promise<MyMap> {
  const m = await call<MyMap>("/api/mymaps", body);
  await loadMyMaps();
  return m;
}

export async function removeMyMap(src: string): Promise<void> {
  maps = (await call<{ maps: MyMap[] }>(`/api/mymaps/${encodeURIComponent(src)}`, undefined, "DELETE")).maps;
  emit();
}

const BUILT_IN_MAXZ: Record<string, number> = { osm: 19, esri: 19, light: 16, dark: 16, satellite: 19, satroads: 19, topo: 17, offline: 14 };

/** The deepest zoom a layer has (the map magnifies beyond it). */
export function layerMaxZoom(b: string): number {
  return isMyMap(b) ? (myMap(b)?.maxzoom ?? 19) : (BUILT_IN_MAXZ[b] ?? 19);
}

/** The attribution a layer asks for (My maps: what the file / the user gave, else its name). */
export function myMapAttribution(b: string): string {
  const m = myMap(b);
  return m ? (m.attribution || m.name) : "";
}

export const keepApi = {
  estimate: (src: string, bounds: number[], zmin: number, zmax: number) =>
    call<KeepEstimate>("/api/tiles/keep/estimate", { src, bounds, zmin, zmax }),
  start: (src: string, bounds: number[], zmin: number, zmax: number, name: string) =>
    call<KeptArea>("/api/tiles/keep", { src, bounds, zmin, zmax, name }),
  progress: () => call<KeepProgress>("/api/tiles/keep/progress"),
  stop: () => call<KeepProgress>("/api/tiles/keep/stop", {}),
  areas: () => call<{ areas: KeptArea[] }>("/api/tiles/areas"),
  remove: (id: string) => call<{ removed: number; freed: number }>(`/api/tiles/areas/${encodeURIComponent(id)}`, undefined, "DELETE"),
};

/** The tile (z, x, y) under a point - the picker's thumbnails show the place on screen. */
export function tileAt(lat: number, lon: number, z: number): [number, number, number] {
  const n = 2 ** z;
  const la = Math.max(-85.05, Math.min(85.05, lat)) * Math.PI / 180;
  const x = Math.min(n - 1, Math.max(0, Math.floor(((lon + 180) / 360) * n)));
  const y = Math.min(n - 1, Math.max(0, Math.floor((0.5 - Math.log((1 + Math.sin(la)) / (1 - Math.sin(la))) / (4 * Math.PI)) * n)));
  return [z, x, y];
}

/** The box around tracks, a little wider, as [south, west, north, east]; null when there is no position. */
export function boundsOf(tracks: { lat: ArrayLike<number>; lon: ArrayLike<number> }[]): number[] | null {
  let s = Infinity, w = Infinity, n = -Infinity, e = -Infinity;
  for (const tr of tracks) {
    for (let i = 0; i < tr.lat.length; i++) {
      const la = tr.lat[i], lo = tr.lon[i];
      if (!Number.isFinite(la) || !Number.isFinite(lo) || Math.abs(la) > 90 || Math.abs(lo) > 180) continue;
      if (la < s) s = la; if (la > n) n = la; if (lo < w) w = lo; if (lo > e) e = lo;
    }
  }
  if (!Number.isFinite(s)) return null;
  const pl = Math.max((n - s) * 0.1, 0.002), po = Math.max((e - w) * 0.1, 0.002);
  return [Math.max(-85, s - pl), Math.max(-180, w - po), Math.min(85, n + pl), Math.min(180, e + po)];
}
