import { describe, expect, it } from "vitest";
import { pathThin } from "./thin";

describe("thinning that keeps every excursion (the needle)", () => {
  it("keeps the one spike of any column, the ends, in order, about as many as asked", () => {
    const n = 100_003, a = new Float64Array(n), b = new Float64Array(n);
    for (let i = 0; i < n; i++) { a[i] = Math.sin(i / 50); b[i] = Math.cos(i / 70); }
    a[77_777] = 99; b[12_345] = -99; a[500] = NaN;
    const idx = pathThin([a, b], n, 2000);
    expect(idx.length).toBeLessThan(2400);
    expect(idx).toContain(77_777);
    expect(idx).toContain(12_345);
    expect(idx[0]).toBe(0);
    expect(idx[idx.length - 1]).toBe(n - 1);
    expect(idx.every((v, i) => i === 0 || v > idx[i - 1])).toBe(true);
    expect(pathThin([a], 10, 100)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  });
});
