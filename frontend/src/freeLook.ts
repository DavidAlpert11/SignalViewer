/* 2026-11-16: the Cockpit's free look - the camera stays at the object (moving with it along the replay) and
   looks where the user turned it. The direction is kept relative to north, not to the object's nose: a
   runway, a target or the other vehicle stays on screen while the object turns, rolls or its heading is
   noisy (a multicopter yawing); looking along the nose is what the Cockpit without free look already does. */

export type Look = { hdg: number; pitch: number; fov?: number };

export const LOOK_FOV = 70;                           // the Cockpit's own field of view (degrees)
const FOV_MIN = 15, FOV_MAX = 100, PITCH_MAX = 89;

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const wrap = (h: number) => ((h % 360) + 360) % 360;

/** Free look's first direction: where the object points now, level wings (no jump when it is turned on). */
export function lookFrom(hdg: number | null | undefined, pitch: number | null | undefined, fov?: number): Look {
  const l: Look = { hdg: wrap(Number.isFinite(hdg) ? hdg! : 0), pitch: clamp(Number.isFinite(pitch) ? pitch! : 0, -PITCH_MAX, PITCH_MAX) };
  return fov !== undefined ? { ...l, fov } : l;
}

/** A drag of (dx, dy) pixels on a view `heightPx` tall: the scene moves with the mouse (drag right - look left,
 *  drag down - look up), one pixel the view's angle per pixel, so a point under the mouse stays under it. */
export function lookDrag(l: Look, dx: number, dy: number, heightPx: number): Look {
  const k = (l.fov ?? LOOK_FOV) / Math.max(1, heightPx);
  return { ...l, hdg: wrap(l.hdg - dx * k), pitch: clamp(l.pitch + dy * k, -PITCH_MAX, PITCH_MAX) };
}

/** The wheel zooms the view (its field of view): forward (deltaY < 0) nearer. */
export function lookZoom(l: Look, deltaY: number): Look {
  const fov = clamp((l.fov ?? LOOK_FOV) * Math.exp(deltaY * 0.0015), FOV_MIN, FOV_MAX);
  return { ...l, fov: Math.round(fov * 10) / 10 };
}
