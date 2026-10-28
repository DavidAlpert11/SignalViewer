/* "One into each plot": several selected signals, one into each of the active tab's plots - a flight
   computer's X, Y, Z beside the true X, Y, Z already plotted one per plot. The signals are paired with
   the plots by the part of their names that differs (X / Y / Z, [0] / [1] / [2], Roll / Pitch / Yaw);
   when the names do not line up, by order. */
import type { Plot } from "./store";

const hue = (hex: string) => {
  const n = parseInt(hex.replace("#", ""), 16), r = (n >> 16 & 255) / 255, g = (n >> 8 & 255) / 255, b = (n & 255) / 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
  if (!d) return 0;
  const h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return (h * 60 + 360) % 360;
};
/** One colour for a set added across plots: of the palette, the one whose hue is furthest from every
 *  line already in those plots - "which line is the flight computer's" is then the same answer in each. */
export function contrastColor(palette: string[], used: string[]): string {
  const free = palette.filter((c) => !used.some((u) => u.toLowerCase() === c.toLowerCase()));
  const pool = free.length ? free : palette;
  if (!used.length) return pool[0];
  const dist = (c: string) => Math.min(...used.map((u) => { const d = Math.abs(hue(c) - hue(u)); return Math.min(d, 360 - d); }));
  return pool.reduce((best, c) => (dist(c) > dist(best) ? c : best), pool[0]);
}

const nameOf = (id: string) => id.slice(id.indexOf("/") + 1);

/** The part of each name that the others do not share: what is left after the longest common start
 *  and end, lower case, without separators. ["Pos_X", "Pos_Y"] -> ["x", "y"]. */
export function distinctParts(names: string[]): string[] {
  if (names.length < 2) return names.map(() => "");
  let pre = names[0].length, suf = names[0].length;
  for (const n of names) {
    let i = 0;
    while (i < pre && i < n.length && n[i] === names[0][i]) i++;
    pre = i;
    let j = 0;
    while (j < suf && j < n.length && n[n.length - 1 - j] === names[0][names[0].length - 1 - j]) j++;
    suf = j;
  }
  const short = Math.min(...names.map((n) => n.length));
  if (pre + suf > short) suf = Math.max(0, short - pre);
  return names.map((n) => n.slice(pre, n.length - suf).toLowerCase().replace(/[\s_.[\]()-]+/g, ""));
}

/** Plots that can take a line over time, in the tab's order, with at least one line already. */
export function targetPlots(plots: Plot[]): number[] {
  return plots.map((p, i) => ({ p, i }))
    .filter(({ p }) => (p.mode ?? "time") === "time" && p.signals.some((s) => !s.state))
    .map(({ i }) => i);
}

export interface Pairing { pairs: { sig: string; plot: number }[]; extra: string[]; byName: boolean }

/** Which plot each signal goes to. Signals with no plot left over go to new plots (`extra`). */
export function pairWithPlots(ids: string[], plots: Plot[], active: number): Pairing {
  const targets = targetPlots(plots);
  if (!ids.length || !targets.length) return { pairs: [], extra: [...ids], byName: false };
  // by name: the selection's distinct parts against the plots' (each plot by its first line)
  if (ids.length >= 2 && targets.length >= 2) {
    const mine = distinctParts(ids.map(nameOf));
    const firsts = targets.map((i) => nameOf(plots[i].signals.find((s) => !s.state)!.sig));
    const theirs = distinctParts(firsts);
    const unique = (xs: string[]) => xs.every((x) => x) && new Set(xs).size === xs.length;
    if (unique(mine) && unique(theirs) && mine.every((m) => theirs.includes(m))) {
      return { pairs: ids.map((sig, k) => ({ sig, plot: targets[theirs.indexOf(mine[k])] })), extra: [], byName: true };
    }
  }
  // by order: from the active plot when the rest of the tab holds them all, else from the first
  const fromActive = targets.indexOf(active);
  const start = fromActive >= 0 && targets.length - fromActive >= ids.length ? fromActive : 0;
  const use = targets.slice(start, start + ids.length);
  return { pairs: use.map((plot, k) => ({ sig: ids[k], plot })), extra: ids.slice(use.length), byName: false };
}
