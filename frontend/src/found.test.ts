// AU1-AU3: every name rule of the *Found in this file* line, on names alone
import { describe, expect, it } from "vitest";
import type { RunInfo } from "./api";
import { copySets, findIn, platformOf, truthNavPairs } from "./found";
import { detectObjects } from "./objectDetect";
import { NAMING_HEADER } from "./components/NamingDialog";

let k = 0;
const run = (names: string[], opts: { labels?: string[]; name?: string } = {}): RunInfo => {
  const id = `f${++k}`;
  return { id, name: opts.name ?? `${id}.csv`, format: "csv", signals: names.map((x) => ({ id: `${id}/${x}`, name: x,
    ...(opts.labels?.includes(x) ? { labels: { 0: "A", 1: "B" } } : {}) })) } as unknown as RunInfo;
};
const ids = (r: RunInfo) => findIn(r, [r]).map((f) => f.id);
const obj = (p: string) => [`${p}.lat`, `${p}.lon`, `${p}.alt`, `${p}.att.roll`, `${p}.att.pitch`, `${p}.att.yaw`];

describe("truth and navigation of one platform (AU2)", () => {
  it("6dof / ins, physics / nav: the owner's words are a truth and a navigation system", () => {
    for (const [a, b] of [["6dof", "ins"], ["physics", "nav"], ["truth", "ekf"], ["sim", "navigation"], ["groundtruth", "kf"]]) {
      const r = run(["time", ...obj(a), ...obj(b)]);
      const pairs = truthNavPairs(detectObjects(r).candidates);
      expect(pairs.map((p) => [p.truth.name, p.nav.name])).toEqual([[a, b]]);
      expect(ids(r)).toContain("truthnav");
    }
  });
  it("pairs by platform: uav1.truth with uav1.nav, never with uav2.nav", () => {
    expect(platformOf("uav1.truth")).toBe("uav1");
    expect(platformOf("6dof")).toBe("");
    const r = run([...obj("uav1.truth"), ...obj("uav1.nav"), ...obj("uav2.truth"), ...obj("uav2.nav")]);
    const pairs = truthNavPairs(detectObjects(r).candidates).map((p) => `${p.truth.prefix}>${p.nav.prefix}`);
    expect(pairs.sort()).toEqual(["uav1.truth>uav1.nav", "uav2.truth>uav2.nav"]);
  });
  it("no truth, or a receiver only: nothing to compare", () => {
    expect(ids(run([...obj("nav"), "gps.lat", "gps.lon"]))).not.toContain("truthnav");
    expect(ids(run([...obj("a"), ...obj("b")]))).not.toContain("truthnav");
  });
});

describe("sensors in several copies (AU3)", () => {
  it("IMU[0] / IMU[1] with the same fields", () => {
    const s = copySets(run(["IMU[0].AccX", "IMU[0].AccY", "IMU[0].TimeUS", "IMU[1].AccX", "IMU[1].AccY", "IMU[1].TimeUS"]).signals);
    expect(s).toHaveLength(1);
    expect(s[0].copies).toEqual(["IMU[0]", "IMU[1]"]);
    expect(s[0].fields.map((f) => f.field)).toEqual(["AccX", "AccY"]);          // not the time
    expect(s[0].fields[0].ids.map((x) => x.split("/")[1])).toEqual(["IMU[0].AccX", "IMU[1].AccX"]);
  });
  it("imu1 / imu2 when most fields are shared; XKF1 / XKF2 (different messages) are not copies", () => {
    expect(copySets(run(["imu1.ax", "imu1.ay", "imu1.az", "imu2.ax", "imu2.ay", "imu2.az"]).signals)[0].base).toBe("imu");
    expect(copySets(run(["XKF1.Roll", "XKF1.Pitch", "XKF1.TimeUS", "XKF2.AX", "XKF2.AY", "XKF2.TimeUS"]).signals)).toEqual([]);
  });
  it("a number on the field itself (RCOU.C1, motor1) is not a copy; one copy alone is none", () => {
    expect(copySets(run(["RCOU.C1", "RCOU.C2", "RCOU.C3"]).signals)).toEqual([]);
    expect(copySets(run(["imu[0].ax", "imu[0].ay"]).signals)).toEqual([]);
  });
});

describe("findIn (AU1)", () => {
  it("each find from its names: pairs, objects, modes, copies, actuators, byte columns", () => {
    const r = run(["time", "ctrl.roll_cmd", "ctrl.roll", "mode", ...obj("uav"), "imu[0].ax", "imu[1].ax", "act.throttle", "byte_0", "byte_1"], { labels: ["mode"] });
    const f = findIn(r, [r]);
    expect(f.map((x) => x.id)).toEqual(["pairs", "objects", "states", "copies", "effort", "bytes"]);
    expect(f[0].why).toEqual(["ctrl.roll_cmd → ctrl.roll"]);
    expect(f.find((x) => x.id === "states")!.why).toEqual(["mode"]);
  });
  it("an object already on a map is not offered again", () => {
    const r = run(obj("uav"));
    expect(findIn(r, [r], () => true).map((x) => x.id)).not.toContain("objects");
  });
  it("three files with the same names: an envelope; two: none", () => {
    const a = run(["t", "x"]), b = run(["t", "x"]), c = run(["t", "x"]);
    expect(findIn(a, [a, b, c]).map((x) => x.id)).toContain("envelope");
    expect(findIn(a, [a, b]).map((x) => x.id)).not.toContain("envelope");
  });
  it("a file with plain names finds nothing", () => {
    expect(findIn(run(["time", "temperature", "pressure"]), [])).toEqual([]);
  });
  it("Name your signals' header (the example recording's) lights up every one-file find", () => {
    const r = run(NAMING_HEADER.split(","), { labels: ["mode"] });
    expect(ids(r)).toEqual(["pairs", "objects", "truthnav", "states", "copies", "effort"]);
    expect(findIn(r, [r]).find((x) => x.id === "pairs")!.n).toBe(3);
  });
});
