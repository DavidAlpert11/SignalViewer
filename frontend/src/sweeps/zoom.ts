/* A parallel plot's zoom (ParallelPlot): k times, moved by x, y pixels of the canvas. */
export interface Zoom { k: number; x: number; y: number }
export const NO_ZOOM: Zoom = { k: 1, x: 0, y: 0 };
const MAX_ZOOM = 40;
/** zoom by f around the point (x, y) of the canvas; back to 1 is no zoom at all */
export function zoomAt(z: Zoom, f: number, x: number, y: number): Zoom {
  const k = Math.max(1, Math.min(MAX_ZOOM, z.k * f));
  if (k === 1) return NO_ZOOM;
  return { k, x: x - ((x - z.x) * k) / z.k, y: y - ((y - z.y) * k) / z.k };
}
