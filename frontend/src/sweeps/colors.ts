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

/* Colour maps to choose from for the maps and the point plots (S12): perceptually even ones, a
   rainbow that keeps its order (turbo) and greys - each from its low end to its high end. */
export type Cmap = "viridis" | "plasma" | "cividis" | "turbo" | "greys";
export const CMAPS: Record<Cmap, [number, number, number][]> = {
  viridis: STOPS,
  plasma: [[13, 8, 135], [126, 3, 168], [204, 71, 120], [248, 149, 64], [240, 249, 33]],
  cividis: [[0, 32, 77], [65, 77, 108], [124, 123, 120], [187, 175, 113], [255, 234, 70]],
  turbo: [[48, 18, 59], [40, 152, 226], [163, 253, 61], [251, 128, 34], [122, 4, 3]],
  greys: [[30, 30, 30], [90, 90, 90], [150, 150, 150], [205, 205, 205], [245, 245, 245]],
};
/** A colour map as a function of 0..1. */
export function rampOf(name: Cmap = "viridis"): (t: number) => string {
  const st = CMAPS[name] ?? STOPS;
  return (t) => {
    if (!Number.isFinite(t)) return "rgb(128,128,128)";
    const x = Math.max(0, Math.min(1, t)) * (st.length - 1);
    const i = Math.min(st.length - 2, Math.floor(x)), f = x - i;
    const c = st[i].map((a, k) => Math.round(a + (st[i + 1][k] - a) * f));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  };
}
export const rampCssOf = (name: Cmap = "viridis") => `linear-gradient(90deg, ${(CMAPS[name] ?? STOPS).map((c) => `rgb(${c.join(",")})`).join(", ")})`;

const PALETTE = ["#6fa8ff", "#f2a93b", "#c79bf2", "#4cc38a", "#ef6b73", "#5fd0d6", "#d6b45f", "#9aa8ff", "#f08fc0", "#8bd16b"];
export const category = (i: number) => (Number.isFinite(i) ? PALETTE[((i % PALETTE.length) + PALETTE.length) % PALETTE.length] : "rgb(128,128,128)");

export const HOLDS = "#f2a93b";
export const FAILS = "#7f8b9a";

/** Columns that are yes / no (1 / 0): coloured as holds / the others, shown as two categories. */
export const FLAG_COLS = new Set(["#holds", "#pareto", "#partial", "#robustHolds", "#knee"]);
