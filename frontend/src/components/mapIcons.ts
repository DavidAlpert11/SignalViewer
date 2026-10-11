import type { ObjectKind } from "../store";

/* Top-view silhouettes of the objects drawn on the map, in a 100 x 100 box around (0, 0) with the
   nose pointing up (north): rotating by the heading points them where they go. Vector paths, so they
   stay sharp at any size and need no image files (the app works offline). */

const P = (d: string) => new Path2D(d);
export const OBJECT_KINDS: ObjectKind[] = ["aircraft", "uav", "drone", "missile", "ship", "vehicle"];

const SHAPES: Record<ObjectKind, { body: Path2D; detail?: Path2D }> = {
  aircraft: {
    body: P("M0,-48 C6,-44 6,-30 6,-18 L46,4 L46,12 L6,4 L5,30 L18,40 L18,46 L0,42 L-18,46 L-18,40 L-5,30 L-6,4 L-46,12 L-46,4 L-6,-18 C-6,-30 -6,-44 0,-48 Z"),
  },
  uav: {      // long straight wings, slender body, twin tail booms
    body: P("M0,-40 C4,-38 5,-32 5,-26 L5,-12 L48,-10 L50,-3 L13,-1 L13,34 L16,42 L-16,42 L-13,34 L-13,-1 L-50,-3 L-48,-10 L-5,-12 L-5,-26 C-5,-32 -4,-38 0,-40 Z"),
    detail: P("M-9,-1 L9,-1 L9,32 L-9,32 Z"),
  },
  drone: {    // a quadcopter: X arms, four rotors, a mark at the front
    body: P("M-6,-6 L-30,-30 L-26,-34 L0,-8 L26,-34 L30,-30 L6,-6 L30,30 L26,34 L0,8 L-26,34 L-30,30 L-6,6 Z" +
      "M-28,-46 a14,14 0 1,0 0.1,0 Z M28,-46 a14,14 0 1,0 0.1,0 Z M-28,18 a14,14 0 1,0 0.1,0 Z M28,18 a14,14 0 1,0 0.1,0 Z" +
      "M-12,-12 L12,-12 L12,12 L-12,12 Z"),
    detail: P("M0,-22 L7,-10 L-7,-10 Z"),
  },
  missile: {
    body: P("M0,-50 C5,-42 5,-36 5,-30 L5,30 L14,44 L14,50 L5,46 L5,48 L-5,48 L-5,46 L-14,50 L-14,44 L-5,30 L-5,-30 C-5,-36 -5,-42 0,-50 Z"),
  },
  ship: {
    body: P("M0,-48 C12,-30 14,-12 14,10 L14,40 C14,46 10,48 0,48 C-10,48 -14,46 -14,40 L-14,10 C-14,-12 -12,-30 0,-48 Z"),
    detail: P("M-8,4 L8,4 L8,20 L-8,20 Z"),
  },
  vehicle: {
    body: P("M-16,-34 Q-16,-42 -8,-42 L8,-42 Q16,-42 16,-34 L16,36 Q16,42 10,42 L-10,42 Q-16,42 -16,36 Z"),
    detail: P("M-12,-26 L12,-26 L10,-14 L-10,-14 Z"),
  },
};

/** Draw an object at (x, y) pointing `headingDeg` (0 = north, clockwise), `size` px across. */
export function drawObjectIcon(ctx: CanvasRenderingContext2D, kind: ObjectKind, x: number, y: number,
  headingDeg: number | null, size: number, color: string, dark: boolean) {
  const sh = SHAPES[kind] ?? SHAPES.aircraft;
  ctx.save();
  ctx.translate(x, y);
  if (headingDeg !== null && Number.isFinite(headingDeg)) ctx.rotate((headingDeg * Math.PI) / 180);
  ctx.scale(size / 100, size / 100);
  ctx.lineJoin = "round";
  ctx.lineWidth = 9;
  ctx.strokeStyle = dark ? "rgba(10,14,20,.9)" : "rgba(255,255,255,.95)";
  ctx.stroke(sh.body);                                     // outline: readable on terrain and water
  ctx.fillStyle = color;
  ctx.fill(sh.body, "nonzero");
  if (sh.detail) { ctx.fillStyle = dark ? "rgba(255,255,255,.75)" : "rgba(0,0,0,.35)"; ctx.fill(sh.detail); }
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = dark ? "rgba(0,0,0,.55)" : "rgba(0,0,0,.45)";
  ctx.stroke(sh.body);
  ctx.restore();
}

/** A small preview of an icon (for buttons): an SVG data URL. */
export function iconSvg(kind: ObjectKind, color: string): string {
  const d: Record<ObjectKind, string> = {
    aircraft: "M0,-48 C6,-44 6,-30 6,-18 L46,4 L46,12 L6,4 L5,30 L18,40 L18,46 L0,42 L-18,46 L-18,40 L-5,30 L-6,4 L-46,12 L-46,4 L-6,-18 C-6,-30 -6,-44 0,-48 Z",
    uav: "M0,-40 C4,-38 5,-32 5,-26 L5,-12 L48,-10 L50,-3 L13,-1 L13,34 L16,42 L-16,42 L-13,34 L-13,-1 L-50,-3 L-48,-10 L-5,-12 L-5,-26 C-5,-32 -4,-38 0,-40 Z",
    drone: "M-6,-6 L-30,-30 L-26,-34 L0,-8 L26,-34 L30,-30 L6,-6 L30,30 L26,34 L0,8 L-26,34 L-30,30 L-6,6 Z M-28,-46 a14,14 0 1,0 0.1,0 Z M28,-46 a14,14 0 1,0 0.1,0 Z M-28,18 a14,14 0 1,0 0.1,0 Z M28,18 a14,14 0 1,0 0.1,0 Z M-12,-12 L12,-12 L12,12 L-12,12 Z",
    missile: "M0,-50 C5,-42 5,-36 5,-30 L5,30 L14,44 L14,50 L5,46 L5,48 L-5,48 L-5,46 L-14,50 L-14,44 L-5,30 L-5,-30 C-5,-36 -5,-42 0,-50 Z",
    ship: "M0,-48 C12,-30 14,-12 14,10 L14,40 C14,46 10,48 0,48 C-10,48 -14,46 -14,40 L-14,10 C-14,-12 -12,-30 0,-48 Z",
    vehicle: "M-16,-34 Q-16,-42 -8,-42 L8,-42 Q16,-42 16,-34 L16,36 Q16,42 10,42 L-10,42 Q-16,42 -16,36 Z",
  };
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="-56 -56 112 112"><path d="${d[kind]}" fill="${color}" stroke="#000" stroke-opacity=".45" stroke-width="4" stroke-linejoin="round"/></svg>`;
  return "data:image/svg+xml;utf8," + encodeURIComponent(svg);
}
