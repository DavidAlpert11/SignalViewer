import { describe, expect, it } from "vitest";
import { groupByPrefix, nameTree, pathCuts, type TreeEntry } from "./signalGroups";

/** The tree as plain text: "phys{att{roll,pitch,yaw},vel{north,east}},..." - labels only. */
const show = (es: TreeEntry<string>[]): string =>
  es.map((e) => (e.kind === "item" ? e.label : `${e.node.label}{${show(e.node.entries)}}`)).join(",");
const tree = (names: string[]) => nameTree(names, (n) => n);

// the round's fixture (examples/three_objects.csv, tools/make_objects_fixture.py)
const FIXTURE = ["phys.lat", "phys.lon", "phys.alt", "phys.att.roll", "phys.att.pitch", "phys.att.yaw",
  "phys.vel.north", "phys.vel.east", "nav.lat", "nav.lon", "nav.alt", "nav.att.roll", "nav.att.pitch",
  "nav.att.yaw", "nav.vel.north", "nav.vel.east", "gps.lat", "gps.lon", "gps.alt"];

describe("nameTree (N1)", () => {
  it("nests the 19-signal fixture, which the old thresholds listed flat", () => {
    expect(groupByPrefix(FIXTURE, (n) => n)).toBeNull();          // the bug: under GROUP_MIN
    expect(show(tree(FIXTURE)!)).toBe(
      "phys{lat,lon,alt,att{roll,pitch,yaw},vel{north,east}}," +
      "nav{lat,lon,alt,att{roll,pitch,yaw},vel{north,east}},gps{lat,lon,alt}");
  });

  it("goes to any depth (a .mat struct)", () => {
    expect(show(tree(["sim.nav.pos.x", "sim.nav.pos.y", "sim.nav.att.phi", "sim.nav.att.theta", "sim.truth.pos.x", "sim.truth.pos.y"])!))
      .toBe("sim{nav{pos{x,y},att{phi,theta}},truth.pos{x,y}}");
  });

  it("folds a chain of single-child levels into one row and keeps the full key", () => {
    const t = tree(["a.b.c.x", "a.b.c.y", "z"])!;
    expect(show(t)).toBe("a.b.c{x,y},z");
    expect(t[0].kind === "group" && t[0].node.key).toBe("a.b.c");
  });

  it("makes no group of one signal", () => {
    expect(show(tree(["temp.value", "gps.lat", "gps.lon"])!)).toBe("temp.value,gps{lat,lon}");
    expect(show(tree(["phys.att.roll", "phys.lat", "phys.lon"])!)).toBe("phys{att.roll,lat,lon}");
  });

  it("treats / like . and skips a leading / (ROS topics)", () => {
    expect(show(tree(["/imu/data.x", "/imu/data.y", "/odom/pose.x", "/odom/pose.y"])!)).toBe("imu/data{x,y},odom/pose{x,y}");   // the label keeps the name's own separator
  });

  it("keeps a trailing unit in the label and out of the split", () => {
    expect(pathCuts("vel (m/s)")).toBeNull();
    expect(show(tree(["GPS.Lat [deg]", "GPS.Lng [deg]", "ATT.Roll [deg]", "ATT.Pitch [deg]", "GroundSpeed [m/s]"])!))
      .toBe("GPS{Lat [deg],Lng [deg]},ATT{Roll [deg],Pitch [deg]},GroundSpeed [m/s]");
  });

  it("does not split numbers or free text", () => {
    for (const n of ["bus_1.5V", "fw v2.1", "x.5", "3.14", "a..b", "a.", "ratio 1/2", "vel (m/s)"]) expect(pathCuts(n), n).toBeNull();
    expect(tree(["bus_1.5V", "fw v2.1", "vel (m/s)"])).toBeNull();     // nothing explicit: the caller keeps the old way
  });

  it("accepts indexed, hyphenated, spaced and non-Latin segments", () => {
    for (const n of ["IMU[0].Acc", "q[2].w", "left-wing.flap", "Motor 1.rpm", "חיישן.טמפ"]) expect(pathCuts(n), n).not.toBeNull();
  });

  it("keeps the heuristics for _ and : among the other names", () => {
    const mot = Array.from({ length: 24 }, (_, i) => `MOT_${(i % 8) + 1}_${["PWM", "RPM", "CUR"][i >> 3]}`);
    const bat = Array.from({ length: 24 }, (_, i) => `BAT_${(i % 4) + 1}_${["V", "A", "T", "SOC", "R", "W"][i >> 2]}`);
    const t = tree([...mot, "gps.lat", ...bat, "gps.lon"])!;
    expect(t.map((e) => (e.kind === "group" ? e.node.key : e.label))).toEqual(["~MOT", "gps", "~BAT"]);
    expect(t[0].kind === "group" && t[0].node.all.length).toBe(24);
    expect(t[0].kind === "group" && t[0].node.entries[0]).toMatchObject({ label: "MOT_1_PWM" });   // as before: whole names
  });

  it("collects every signal under a group in `all`, in order", () => {
    const t = tree(FIXTURE)!;
    expect(t[0].kind === "group" && t[0].node.all).toEqual(FIXTURE.slice(0, 8));
  });

  it("is fast on 5000 names", () => {
    const names = Array.from({ length: 5000 }, (_, i) => `sys${i % 20}.sub${i % 7}.sig${i}`);
    const t0 = performance.now();
    nameTree(names, (n) => n);
    expect(performance.now() - t0).toBeLessThan(200);
  });
});
