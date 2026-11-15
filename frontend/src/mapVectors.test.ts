import { describe, expect, it } from "vitest";
import { suggestVectors } from "./mapObjects";
import type { RunInfo } from "./api";

const run = (names: string[]) => ({ id: "r", signals: names.map((name) => ({ id: `r/${name}`, name })) }) as unknown as RunInfo;

describe("F6 vectors offered by themselves", () => {
  it("a log's wind first (the first EKF core)", () => {
    expect(suggestVectors(run(["GPS.Lat", "XKF2[0].VWN", "XKF2[0].VWE", "XKF2[1].VWN", "XKF2[1].VWE"])))
      .toEqual({ n: "r/XKF2[0].VWN", e: "r/XKF2[0].VWE", kind: "wind" });
    expect(suggestVectors(run(["NKF2.VWN", "NKF2.VWE"]))?.kind).toBe("wind");
  });
  it("a CSV's velocity north / east with the same prefix", () => {
    expect(suggestVectors(run(["time", "phys.lat", "phys.vel.north", "phys.vel.east"])))
      .toEqual({ n: "r/phys.vel.north", e: "r/phys.vel.east", kind: "velocity" });
    expect(suggestVectors(run(["VN", "VE"]))).toEqual({ n: "r/VN", e: "r/VE", kind: "velocity" });
    expect(suggestVectors(run(["vel_n", "vel_e"]))?.e).toBe("r/vel_e");
  });
  it("nothing when there is no pair", () => {
    expect(suggestVectors(run(["lat", "lon", "vel.north"]))).toBeNull();
  });
});
