// FR4: one colour rule for two runs - the same signal from several files in one plot takes each FILE's colour,
// whichever way the plot was made (a template / Compare tab, a signal joining its namesake), units or not.
import { describe, expect, it } from "vitest";
import type { RunInfo } from "./api";
import { colorByFile, sameSignalKey } from "./store/selectors";
import type { Plot } from "./store/model";

const A = "#3D8BFD", B = "#E5677A";
const runs = [
  { id: "sim", name: "sim.mat", format: "mat", tag: "A", color: A, signals: [] },
  { id: "flt", name: "flight.bin", format: "bin", tag: "B", color: B, signals: [] },
] as unknown as RunInfo[];
const line = (sig: string, color = "#0072B2") => ({ sig, color, width: 1.5, scale: 1, offset: 0 });

describe("FR4: the file's colour", () => {
  it("a model's name and its log's name with a unit are the same signal", () => {
    expect(sameSignalKey("sim/ATT.Roll")).toBe(sameSignalKey("flt/ATT.Roll [deg]"));
    expect(sameSignalKey("sim/imu[1]")).toBe("imu[1]");                    // an index is not a unit
    expect(sameSignalKey("sim/ATT.Roll")).not.toBe(sameSignalKey("flt/ATT.Pitch [deg]"));
  });
  it("the sim-against-flight demo's plots: every line of A blue, every line of B rose", () => {
    const plots: Plot[] = ["Roll", "DesRoll", "Pitch"].map((n) => ({ id: n, title: n, signals: [line(`sim/ATT.${n}`, "#009E73"), line(`flt/ATT.${n} [deg]`, "#CC79A7")] }));
    plots.forEach((p) => colorByFile(p, runs));
    for (const p of plots) expect(p.signals.map((s) => s.color)).toEqual([A, B]);
  });
  it("a colour chosen by hand (or by the template) is kept", () => {
    const p: Plot = { id: "p", title: "", signals: [line("sim/ATT.Roll", "#123456"), line("flt/ATT.Roll [deg]")] };
    colorByFile(p, runs, false, (s) => s.sig === "sim/ATT.Roll");
    expect(p.signals.map((s) => s.color)).toEqual(["#123456", B]);
  });
  it("lines of one file only are not recoloured (no comparison)", () => {
    const p: Plot = { id: "p", title: "", signals: [line("sim/ATT.Roll", "#111111"), line("sim/ATT.Pitch", "#222222")] };
    expect(colorByFile(p, runs)).toBe(0);
    expect(p.signals.map((s) => s.color)).toEqual(["#111111", "#222222"]);
  });
});
