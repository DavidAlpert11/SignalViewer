/* CC22: the 3D view's parts that are not its React life cycle (from Globe3D.tsx): loading Cesium (once, offline),
   telling a software-drawn WebGL, giving a closed view's graphics memory back, an object's height and rates along its
   track, and the camera's constants. */
import type { MapObject } from "../store";
import { groundDistance, type ObjTrack } from "../mapObjects";

export type C = typeof import("cesium");
let cesiumP: Promise<C> | null = null;
let cesiumNow: C | null = null;                 // (loaded: the clean-up of a view needs it at once)
/** Cesium once loaded (null before): a view's clean-up needs it at once, not after a promise. */
export const cesiumLoaded = () => cesiumNow;
export const loadCesium = () => (cesiumP ??= (async () => {
  (window as unknown as { CESIUM_BASE_URL: string }).CESIUM_BASE_URL = "/cesium/";
  const m = await import("cesium");
  m.Ion.defaultAccessToken = "";
  cesiumNow = m;
  return m;
})());

/** WebGL drawn by the processor (no graphics acceleration: virtual machines, remote desktop, blocked
 *  drivers). There every full-screen pass is expensive, so the 3D view uses lighter settings - one
 *  sample per pixel instead of 4 (3x the frame rate measured) and less terrain detail. */
export function softwareWebGL(): boolean {
  try {
    const gl = document.createElement("canvas").getContext("webgl");
    if (!gl) return false;
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    const name = String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return /swiftshader|llvmpipe|softpipe|basic render|software|gdi generic/i.test(name);
  } catch { return false; }
}

/** Destroy a 3D view and give its graphics memory back at once. CesiumWidget.destroy frees the view's GPU
 *  objects but not its WebGL context: Cesium keeps the terrain grid's index buffers in a static cache keyed by
 *  context (TerrainProvider's regular-grid indices, `indexBuffers[context.id]`), which held every closed view's
 *  context - its canvas, framebuffers, MSAA and shadow maps - until the browser dropped the oldest of 16. */
export function releaseWidget(Cz: C, w: import("cesium").CesiumWidget) {
  const canvas = w.canvas;
  const id = (w.scene as unknown as { context?: { id?: string } }).context?.id;
  w.destroy();
  if (id !== undefined) {
    const n = TERRAIN_SIZE;                      // the size of our terrain tiles: the only grid in the cache
    const T = Cz.TerrainProvider as unknown as Record<"getRegularGridIndices" | "getRegularGridIndicesAndEdgeIndices" |
      "getRegularGridAndSkirtIndicesAndEdgeIndices", (w: number, h: number) => object>;
    for (const got of [T.getRegularGridIndices(n, n), T.getRegularGridIndicesAndEdgeIndices(n, n), T.getRegularGridAndSkirtIndicesAndEdgeIndices(n, n)]) {
      const ix = "indices" in got ? got.indices : got;
      const bufs = (ix as unknown as { indexBuffers?: Record<string, unknown> }).indexBuffers;
      if (bufs) delete bufs[id];
    }
  }
  // the context itself: lost now, not when the garbage collector or the browser's limit gets to it
  const gl = (canvas.getContext("webgl2") ?? canvas.getContext("webgl")) as WebGLRenderingContext | null;
  gl?.getExtension("WEBGL_lose_context")?.loseContext();
  canvas.width = canvas.height = 0;
}

export const TERRAIN_SIZE = 65;                        // heights per terrain tile side (CustomHeightmapTerrainProvider)
export const TRACK_POINTS = 3000;                      // drawn track: at most this many points per object
export type Track3 = ObjTrack & { alt: Float32Array | null; pitch: Float32Array | null; roll: Float32Array | null; ground: Float32Array | null };

/** Height above sea level of an object at sample i (its altitude signal, by its reference; without
 *  one, on the ground / the sea). */
export function heightAt(o: MapObject, tr: Track3, i: number): number {
  const g = tr.ground ? tr.ground[i] : 0;
  const ground = Number.isFinite(g) ? g : 0;
  if (!tr.alt) return ground + (o.kind === "ship" ? 0 : o.kind === "vehicle" ? 0.5 : 2);
  const a = tr.alt[i];
  if (!Number.isFinite(a)) return NaN;
  if (o.altRef === "agl") return ground + a;
  if (o.altRef === "home") {
    let i0 = 0;
    while (i0 < tr.alt.length && !Number.isFinite(tr.alt[i0])) i0++;
    const g0 = tr.ground && Number.isFinite(tr.ground[i0]) ? tr.ground[i0] : 0;
    return g0 + a;
  }
  return a;
}

/** An object's values at the time (for the data box and the relations). */
export interface ObjState { id: string; name: string; color: string; pos: import("cesium").Cartesian3; lat: number; lon: number; alt: number;
  agl: number | null; hdg: number | null; pitch: number | null; roll: number | null; gs: number | null; vs: number | null }
export interface Readout { primary: ObjState; rel: { name: string; color: string; horiz: number; dz: number; slant: number; brg: number;
  closure: number | null; aspect: number | null; side: "L" | "R" | null }[] }

/** Ground speed and climb rate (m/s) over about a second around t. */
export function ratesAt(o: MapObject, tr: Track3, t: number): { gs: number | null; vs: number | null } {
  const n = tr.t.length;
  const at = (x: number) => { let lo = 0, hi = n - 1; while (hi - lo > 1) { const k = (lo + hi) >> 1; if (tr.t[k] <= x) lo = k; else hi = k; } return lo; };
  let i0 = at(t - 0.5), i1 = Math.min(n - 1, at(t + 0.5) + 1);
  if (i1 <= i0) { i0 = Math.max(0, i0 - 1); i1 = Math.min(n - 1, i0 + 1); }
  const dt = tr.t[i1] - tr.t[i0];
  if (!(dt > 0)) return { gs: null, vs: null };
  const d = groundDistance(tr.lat[i0], tr.lon[i0], tr.lat[i1], tr.lon[i1]);
  const dh = tr.alt ? heightAt(o, tr, i1) - heightAt(o, tr, i0) : NaN;
  return { gs: Number.isFinite(d) ? d / dt : null, vs: Number.isFinite(dh) ? dh / dt : null };
}

export const SIT_M = 15;                               // On the object: nearer than this, the camera sits on it (its model hidden)
export const FLY_MS = 1200;                            // P9: every camera change flies (~1.2 s, eased)
export const reducedMotion = () => { try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; } };

