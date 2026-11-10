import { describe, expect, it } from "vitest";
import { classify, detectObjects, parseName, type Candidate } from "./objectDetect";

let n = 0;
/** A file with these signal names (ids "<run>/<name>", as the backend makes them). */
const run = (names: string[], name = "rec.csv") => {
  const id = `r${++n}`;
  return { id, name, signals: names.map((x) => ({ id: `${id}/${x}`, name: x })) } as unknown as Parameters<typeof detectObjects>[0];
};
const short = (c: Candidate) => ({ prefix: c.prefix, cls: c.cls, ...Object.fromEntries(Object.entries(c.picks).map(([r, p]) => [r, p!.name])) });

const FIXTURE = ["time", "phys.lat", "phys.lon", "phys.alt", "phys.att.roll", "phys.att.pitch", "phys.att.yaw",
  "phys.vel.north", "phys.vel.east", "nav.lat", "nav.lon", "nav.alt", "nav.att.roll", "nav.att.pitch",
  "nav.att.yaw", "nav.vel.north", "nav.vel.east", "gps.lat", "gps.lon", "gps.alt"];

describe("detectObjects (N5)", () => {
  it("finds the fixture's three objects, each from its own prefix only", () => {
    const d = detectObjects(run(FIXTURE));
    expect(d.candidates.map(short)).toEqual([
      { prefix: "phys", cls: "truth", lat: "phys.lat", lon: "phys.lon", alt: "phys.alt", roll: "phys.att.roll", pitch: "phys.att.pitch", yaw: "phys.att.yaw", vn: "phys.vel.north", ve: "phys.vel.east" },
      { prefix: "nav", cls: "navigation", lat: "nav.lat", lon: "nav.lon", alt: "nav.alt", roll: "nav.att.roll", pitch: "nav.att.pitch", yaw: "nav.att.yaw", vn: "nav.vel.north", ve: "nav.vel.east" },
      { prefix: "gps", cls: "receiver", lat: "gps.lat", lon: "gps.lon", alt: "gps.alt" },
    ]);
    const [phys, , gps] = d.candidates;
    expect(phys.full).toBe(true);
    expect(phys.picks.roll).toMatchObject({ rule: "subgroup", via: "att", exact: true });
    expect(phys.clsWhy).toEqual({ word: "phys" });
    expect(gps.attitude).toBe("none");
    expect([phys.picks.vn?.name, phys.picks.ve?.name, phys.picks.vd]).toEqual(["phys.vel.north", "phys.vel.east", undefined]);   // N7: its velocity
    expect(gps.picks.vn).toBeUndefined();                       // position only: still proposed (owner's decision 2)
    expect(gps.missing).toEqual(["roll", "pitch", "yaw"]);
  });

  it("proposes every navigation solution and receiver", () => {
    const d = detectObjects(run(["nav1.lat", "nav1.lon", "nav2.lat", "nav2.lon", "ekf3.lat", "ekf3.lon", "gnss_2.lat", "gnss_2.lon"]));
    expect(d.candidates.map((c) => [c.prefix, c.cls])).toEqual([["nav1", "navigation"], ["nav2", "navigation"], ["ekf3", "navigation"], ["gnss_2", "receiver"]]);
  });

  it("reads _ prefixes, aliases, unit suffixes and sub-groups", () => {
    const d = detectObjects(run(["ins2_latitude", "ins2_lng", "ins2_alt_msl", "ins2_phi", "ins2_theta", "ins2_psi",
      "truth.pos.lat_deg", "truth.pos.lon_deg", "truth.euler.heading"]));
    const ins = d.candidates.find((c) => c.prefix === "ins2")!;
    expect(short(ins)).toMatchObject({ cls: "navigation", lat: "ins2_latitude", lon: "ins2_lng", alt: "ins2_alt_msl", roll: "ins2_phi", yaw: "ins2_psi" });
    expect(ins.picks.lat).toMatchObject({ rule: "prefix", exact: false, word: "latitude" });
    const tr = d.candidates.find((c) => c.prefix === "truth")!;
    expect(tr.picks.lat).toMatchObject({ rule: "subgroup", via: "pos", unit: { unit: "deg", from: "suffix" } });
    expect(tr.picks.yaw).toMatchObject({ via: "euler", word: "heading" });
  });

  it("classifies by whole segments, the deepest one deciding", () => {
    expect(classify("sim.nav").cls).toBe("navigation");
    expect(classify("sim.truth").cls).toBe("truth");
    expect(classify("sim")).toEqual({ cls: "truth", word: "sim" });
    expect(classify("test_rig").cls).toBe("other");            // "est" is not a substring match
    expect(classify("estimate").cls).toBe("other");
    expect(classify("ref").cls).toBe("other");                 // owner's Q2: ref is not truth
    expect(classify("GPS[1]")).toEqual({ cls: "receiver", known: "GPS" });
  });

  it("makes sim.nav and sim.truth two objects and sim none", () => {
    const d = detectObjects(run(["sim.nav.pos.lat", "sim.nav.pos.lon", "sim.nav.att.roll", "sim.truth.lat", "sim.truth.lon"]));
    expect(d.candidates.map((c) => c.prefix)).toEqual(["sim.truth", "sim.nav"]);   // truth first
  });

  it("keeps a CSV with ArduPilot names one aircraft: GPS position + ATT attitude (decision 5)", () => {
    const d = detectObjects(run(["Time", "GPS.Lat [deg]", "GPS.Lng [deg]", "GPS.Alt [m]", "ATT.Roll [deg]", "ATT.Pitch [deg]", "ATT.Yaw [deg]", "GroundSpeed [m/s]"]));
    expect(d.candidates).toHaveLength(1);
    const c = d.candidates[0];
    expect(short(c)).toMatchObject({ prefix: "GPS", cls: "receiver", lat: "GPS.Lat [deg]", yaw: "ATT.Yaw [deg]" });
    expect(c.picks.yaw).toMatchObject({ rule: "known", via: "ATT" });
    expect(c.picks.lat!.unit).toEqual({ unit: "deg", from: "brackets" });
  });

  it("a copter log: POS + ATT first, the receivers and the backup AHRS beside it", () => {
    const d = detectObjects(run(["POS.Lat [deg]", "POS.Lng [deg]", "POS.Alt [m]", "ATT.Roll [deg]", "ATT.Pitch [deg]", "ATT.Yaw [deg]",
      "ATT.DesRoll [deg]", "GPS[0].Lat [deg]", "GPS[0].Lng [deg]", "GPS[0].Alt [m]", "GPS[1].Lat [deg]", "GPS[1].Lng [deg]",
      "AHR2.Roll [deg]", "AHR2.Pitch [deg]", "AHR2.Yaw [deg]", "AHR2.Lat [deg]", "AHR2.Lng [deg]", "AHR2.Alt [m]"], "copter.bin"));
    expect(d.candidates.map((c) => [c.prefix, c.cls, c.attitude])).toEqual([
      ["POS", "navigation", "angles"], ["AHR2", "navigation", "angles"], ["GPS[0]", "receiver", "none"], ["GPS[1]", "receiver", "none"]]);
    expect(d.candidates[0].picks.roll).toMatchObject({ name: "ATT.Roll [deg]", rule: "known" });   // not DesRoll
  });

  it("PX4: the global position with the attitude quaternion", () => {
    const d = detectObjects(run(["vehicle_global_position.lat", "vehicle_global_position.lon", "vehicle_global_position.alt",
      "vehicle_attitude.q[0]", "vehicle_attitude.q[1]", "vehicle_attitude.q[2]", "vehicle_attitude.q[3]",
      "vehicle_gps_position.lat", "vehicle_gps_position.lon"], "px4.ulg"));
    const g = d.candidates[0];
    expect([g.prefix, g.attitude, g.picks.qz?.name]).toEqual(["vehicle_global_position", "quaternion", "vehicle_attitude.q[3]"]);
    expect(d.candidates[1].prefix).toBe("vehicle_gps_position");
  });

  it("positions in metres: NED under a position sub-group, ECEF by its word; velocities are not positions", () => {
    const d = detectObjects(run(["tgt.pos.north", "tgt.pos.east", "tgt.pos.down", "ship.ecef.x", "ship.ecef.y", "ship.ecef.z",
      "nav.vel.north", "nav.vel.east", "nav.vel.down"]));
    expect(d.candidates.map((c) => [c.prefix, c.pos, c.picks.px?.name])).toEqual([["tgt", "ned", "tgt.pos.north"], ["ship", "ecef", "ship.ecef.x"]]);
  });

  it("a plain lat / lon file is one object named after the file", () => {
    const d = detectObjects(run(["Time", "lat", "lon"], "obj_ship.csv"));
    expect(d.candidates.map((c) => [c.prefix, c.name])).toEqual([["", "obj_ship"]]);
  });

  it("explains the near misses", () => {
    const d = detectObjects(run(["nav.lat", "nav.lon", "nav.yaw_cmd", "nav.lattitude", "nav.posLat", "nav2.latitude_deg", "nav2.lon"]));
    const nav = d.candidates.find((c) => c.prefix === "nav")!;
    expect(nav.nearMisses.map((m) => [m.name, m.why, m.role])).toEqual([
      ["nav.yaw_cmd", "suffix", "yaw"], ["nav.lattitude", "spelling", "lat"], ["nav.posLat", "glued", "lat"]]);
    expect(nav.nearMisses[0].detail).toBe("_cmd");
    expect(d.candidates.find((c) => c.prefix === "nav2")).toBeTruthy();   // a unit suffix is accepted
    expect(parseName("tgt.pos.x").miss).toMatchObject({ why: "noframe" });
  });

  it("reports a prefix with half a position", () => {
    const d = detectObjects(run(["radar.lat", "radar.range"]));
    expect(d.candidates).toEqual([]);
    expect(d.incomplete).toEqual([{ runId: expect.any(String), prefix: "radar", has: ["lat"], missing: ["lon"] }]);
  });

  it("is fast on 5000 names and cached", () => {
    const names = Array.from({ length: 5000 }, (_, i) => (i % 50 === 0 ? `obj${i}.lat` : i % 50 === 1 ? `obj${i - 1}.lon` : `sys${i % 20}.sig${i}_val`));
    const r = run(names);
    const t0 = performance.now();
    const d = detectObjects(r);
    expect(performance.now() - t0).toBeLessThan(100);
    expect(d.candidates).toHaveLength(100);
    expect(detectObjects(r)).toBe(d);
  });
});
