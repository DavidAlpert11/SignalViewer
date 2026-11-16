// T1: ink() - every trace colour is drawn at >= 3:1 against the plot in both themes (26.U2)
import { describe, expect, test } from "vitest";
import { ink, PLOT_THEME, tickValues } from "./chartUtil";
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

describe("a drag zooms by its direction", () => {
  test("sideways = time, up / down = values, diagonal = a box", async () => {
    const { dragAxes } = await import("./chartUtil");
    expect(dragAxes(300, 0)).toBe("x");
    expect(dragAxes(300, 60)).toBe("x");        // a wobbly sideways drag stays on time
    expect(dragAxes(10, 200)).toBe("y");
    expect(dragAxes(70, 250)).toBe("y");
    expect(dragAxes(300, 200)).toBe("xy");
    expect(dragAxes(150, 150)).toBe("xy");
    expect(dragAxes(8, 5)).toBe("x");           // tiny: the longer side
  });
});

// a user saw values near zero read as 0: the small ticks were rounded to one digit (2.5e-4 -> "3e-4")
describe("tickValues", () => {
  const f = (xs: number[]) => tickValues(null as never, xs);
  test("small and large ticks keep their digits, neighbours stay distinct", () => {
    expect(f([0, 2.5e-4, 5e-4, 7.5e-4])).toEqual(["0", "2.5e-4", "5e-4", "7.5e-4"]);
    expect(f([1e-4, 1.5e-4, 2e-4])).toEqual(["1e-4", "1.5e-4", "2e-4"]);
    expect(f([-2.5e-7, 3.0000000000000004e-4, 1.25e6])).toEqual(["-2.5e-7", "3e-4", "1.25e6"]);
    expect(f([0.5, 1, 2.5])).toEqual(["0.5", "1", "2.5"]);
  });
});
