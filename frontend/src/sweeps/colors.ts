/* Line colours: a scale for a number (dark violet to yellow, readable on both themes), a palette for
   categories, and holds / fails. */
const STOPS: [number, number, number][] = [[68, 1, 84], [59, 82, 139], [33, 145, 140], [94, 201, 98], [253, 231, 37]];

export function ramp(t: number): string {
  if (!Number.isFinite(t)) return "rgb(128,128,128)";
  const x = Math.max(0, Math.min(1, t)) * (STOPS.length - 1);
  const i = Math.min(STOPS.length - 2, Math.floor(x)), f = x - i;
  const c = STOPS[i].map((a, k) => Math.round(a + (STOPS[i + 1][k] - a) * f));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export const rampCss = `linear-gradient(90deg, ${STOPS.map((c) => `rgb(${c.join(",")})`).join(", ")})`;

const PALETTE = ["#6fa8ff", "#f2a93b", "#c79bf2", "#4cc38a", "#ef6b73", "#5fd0d6", "#d6b45f", "#9aa8ff", "#f08fc0", "#8bd16b"];
export const category = (i: number) => (Number.isFinite(i) ? PALETTE[((i % PALETTE.length) + PALETTE.length) % PALETTE.length] : "rgb(128,128,128)");

export const HOLDS = "#f2a93b";
export const FAILS = "#7f8b9a";
