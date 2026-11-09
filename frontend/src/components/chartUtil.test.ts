// T1: ink() - every trace colour is drawn at >= 3:1 against the plot in both themes (26.U2)
import { describe, expect, test } from "vitest";
import { ink, PLOT_THEME } from "./chartUtil";
import { TRACE_COLORS } from "../store";

const lum = (hex: string) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
const contrast = (a: string, b: string) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

describe("ink", () => {
  for (const theme of ["light", "dark"] as const) {
    test(`every trace colour reads at 3:1 on the ${theme} plot`, () => {
      for (const c of TRACE_COLORS) expect(contrast(ink(c, theme), PLOT_THEME[theme].bg)).toBeGreaterThanOrEqual(3);
    });
  }
  test("a colour that already reads is unchanged; a named or rgba one is as given", () => {
    expect(ink("#0072B2", "light")).toBe("#0072b2");
    expect(ink("rgba(1,2,3,0.5)", "dark")).toBe("rgba(1,2,3,0.5)");
    expect(ink("red", "light")).toBe("red");
  });
  test("a yellow on the light plot is darkened, not replaced", () => {
    const out = ink("#F0E442", "light");
    expect(out).not.toBe("#f0e442");
    expect(lum(out)).toBeLessThan(lum("#F0E442"));
  });
});
