// A1 (plan 2026-11-14 §5.1): every text token reads at WCAG AA (4.5:1) on every surface, in both themes,
// and a verdict's colour reads on its own -soft tint (a tinted card). Read from index.css itself.
import { describe, expect, test } from "vitest";
import raw from "./index.css?raw";

const css = raw.replace(/\/\*[\s\S]*?\*\//g, "");

/** The custom properties of every block whose selector names the theme (later blocks win). */
function tokens(theme: "dark" | "light"): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (!m[1].includes(`[data-theme="${theme}"]`)) continue;
    for (const d of m[2].matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) out[d[1]] = d[2].trim();
  }
  return out;
}

type RGBA = [number, number, number, number];
function parse(v: string, t: Record<string, string>): RGBA {
  const ref = v.match(/^var\((--[\w-]+)\)$/);
  if (ref) return parse(t[ref[1]], t);
  const hex = v.match(/^#([0-9a-f]{6})$/i);
  if (hex) return [0, 2, 4].map((i) => parseInt(hex[1].slice(i, i + 2), 16)).concat(1) as RGBA;
  const rgba = v.match(/^rgba\(([^)]+)\)$/);
  if (rgba) return rgba[1].split(",").map(Number) as RGBA;
  throw new Error(`not a colour: ${v}`);
}
const over = (fg: RGBA, bg: RGBA): RGBA => [0, 1, 2].map((i) => fg[3] * fg[i] + (1 - fg[3]) * bg[i]).concat(1) as RGBA;
const lum = (c: RGBA) => {
  const [r, g, b] = c.slice(0, 3).map((x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a: RGBA, b: RGBA) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

const TEXT = ["--ink", "--ink-strong", "--muted", "--faint", "--amber", "--info", "--ok", "--warn", "--danger", "--axis"];
const SURFACES = ["--bg", "--panel", "--panel-2", "--raised", "--plot-bg"];
const VERDICTS = ["--info", "--ok", "--warn", "--danger", "--amber"];

describe.each(["dark", "light"] as const)("tokens, %s theme", (theme) => {
  const t = tokens(theme);
  test("the new tokens exist", () => {
    for (const k of ["--warn", "--ok-soft", "--warn-soft", "--danger-soft", "--info-soft", "--shadow-md", "--shadow-lg", "--select"]) {
      expect(t[k], k).toBeTruthy();
    }
  });
  test.each(TEXT)("%s reads on every surface", (fg) => {
    for (const s of SURFACES) expect(contrast(parse(t[fg], t), parse(t[s], t)), `${fg} on ${s}`).toBeGreaterThanOrEqual(4.5);
  });
  test.each(VERDICTS)("%s reads on its own tint (a card on a panel)", (v) => {
    const soft = v === "--amber" ? "--amber-soft" : `${v}-soft`;
    const card = over(parse(t[soft], t), parse(t["--panel"], t));
    expect(contrast(parse(t[v], t), card)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(parse(t["--ink"], t), card)).toBeGreaterThanOrEqual(4.5);
  });
  test("the primary button's ink reads on the selection colour", () => {
    expect(contrast(parse(t["--select-ink"], t), parse(t["--select"], t))).toBeGreaterThanOrEqual(4.5);
  });
});
