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

  it("is fast on 5000 names with positions in metres (L1)", () => {
    const names = Array.from({ length: 5000 }, (_, i) => {
      const k = Math.floor(i / 50), j = i % 50;
      return j < 3 ? `obj${k}.ned.${"xyz"[j]}` : j < 6 ? `veh${k}.pos.${["north", "east", "up"][j - 3]}` : j < 9 ? `o${k}.origin.${["lat", "lon", "alt"][j - 6]}` : `sys${i % 20}.sig${i}_val`;
    });
    const r = run(names);
    const t0 = performance.now();
    const d = detectObjects(r);
    expect(performance.now() - t0).toBeLessThan(100);
    expect(d.candidates).toHaveLength(200);
  });
});

/* ---- L1-L3 (round of 2026-11-10): positions in metres, flight-log lanes, origins ------------------ */
const one = (names: string[]) => detectObjects(run(names)).candidates;
const xyz = (pre: string, a: string[]) => a.map((x) => pre + x);

describe("positions in metres by name (L1)", () => {
  it("F3: x / y / z under a NED / ENU frame word, in any form", () => {
    for (const [names, prefix, pos] of [
      [xyz("nav.ned.", ["x", "y", "z"]), "nav", "ned"], [xyz("nav.", ["x_ned", "y_ned", "z_ned"]), "nav", "ned"],
      [xyz("nav.pos_ned_", ["x", "y", "z"]), "nav", "ned"], [xyz("nav.pos.ned.", ["x", "y", "z"]), "nav", "ned"],
      [xyz("tgt.enu.", ["x", "y", "z"]), "tgt", "enu"], [xyz("tgt.", ["x_enu", "y_enu", "z_enu"]), "tgt", "enu"],
    ] as [string[], string, string][]) {
      const c = one(names);
      expect(c.map((x) => [x.prefix, x.pos]), names[0]).toEqual([[prefix, pos]]);
      expect(c[0].picks.px!.name).toBe(names[0]);
      expect(c[0].picks.pz!.name).toBe(names[2]);
    }
  });

  it("F4: ECEF glued, suffix and upper-case forms", () => {
    for (const names of [xyz("ship.ecef", ["X", "Y", "Z"]), xyz("ship.", ["X_ECEF", "Y_ECEF", "Z_ECEF"]), xyz("ship.ecef_", ["X", "Y", "Z"]),
      xyz("ship.", ["x_ecef", "y_ecef", "z_ecef"]), xyz("ship.ecef_", ["x [m]", "y [m]", "z [m]"]), xyz("ship.", ["ecef_x_m", "ecef_y_m", "ecef_z_m"])]) {
      expect(one(names).map((x) => [x.prefix, x.pos, x.picks.px?.name]), names[0]).toEqual([["ship", "ecef", names[0]]]);
    }
    expect(one(["nav.posX", "nav.posY", "nav.posZ"])).toEqual([]);              // a glued x only with a frame word
  });

  it("F5: the frame is decided by the whole group: north / east with up is ENU", () => {
    const c = one(xyz("boat.pos.", ["north", "east", "up"]))[0];
    expect([c.prefix, c.pos, c.picks.px?.name, c.picks.py?.name, c.picks.pz?.name]).toEqual(["boat", "enu", "boat.pos.east", "boat.pos.north", "boat.pos.up"]);
    expect(one(xyz("tgt.pos.", ["north", "east", "down"]))[0].pos).toBe("ned");
  });

  it("F6: single letters n / e / d only right under a position or frame sub-group", () => {
    const c = one(xyz("rov.pos.", ["n", "e", "d"]))[0];
    expect([c.prefix, c.pos, c.picks.px?.name]).toEqual(["rov", "ned", "rov.pos.n"]);
    expect(one(xyz("rov.ned.", ["n", "e", "d"]))[0].pos).toBe("ned");
    expect(one(xyz("nav.", ["n", "e", "d"]))).toEqual([]);                     // nav.n is not a position
  });

  it("F9: flat velocity fields right under a prefix with a position", () => {
    const c = one(["nav.lat", "nav.lon", "nav.alt", "nav.vel_n", "nav.vel_e", "nav.vel_d", "spd.vn", "spd.ve"]);
    expect(c.map((x) => [x.prefix, x.picks.vn?.name, x.picks.vd?.name])).toEqual([["nav", "nav.vel_n", "nav.vel_d"]]);
  });

  it("units: a position in cm is found but flagged, metres are fine; bare x / y / z stay a near miss", () => {
    expect(one(xyz("ship.ecef_", ["x [cm]", "y [cm]", "z [cm]"]))[0].badUnit).toBe("cm");
    expect(one(xyz("ship.ecef_", ["x [m]", "y [m]", "z [m]"]))[0].badUnit).toBeUndefined();
    expect(parseName("/odom.pose.pose.position.x").miss).toMatchObject({ why: "noframe" });   // F10, Q3
  });
});

const COPTER = ["POS.Lat [deg]", "POS.Lng [deg]", "POS.Alt [m]", "ATT.Roll [deg]", "ATT.Pitch [deg]", "ATT.Yaw [deg]",
  ...[0, 1].flatMap((k) => ["Roll [deg]", "Pitch [deg]", "Yaw [deg]", "VN [m/s]", "VE [m/s]", "VD [m/s]", "PN [m]", "PE [m]", "PD [m]"].map((f) => `XKF1[${k}].${f}`)),
  "ORGN[0].Lat [deg]", "ORGN[0].Lng [deg]", "ORGN[0].Alt [m]", "GPS[0].Lat [deg]", "GPS[0].Lng [deg]", "GPS[0].Alt [m]"];

describe("flight-log groups with local positions (L2) and their origins (L3)", () => {
  it("F1: every ArduPilot EKF3 lane, after POS, with its own angles, velocity and the EKF origin", () => {
    const c = one(COPTER);
    expect(c.map((x) => x.prefix)).toEqual(["POS", "XKF1[0]", "XKF1[1]", "GPS[0]"]);
    const lane = c[1];
    expect([lane.pos, lane.attitude, lane.cls, lane.picks.roll?.name, lane.picks.vd?.name, lane.picks.pz?.name])
      .toEqual(["ned", "angles", "navigation", "XKF1[0].Roll [deg]", "XKF1[0].VD [m/s]", "XKF1[0].PD [m]"]);
    expect(lane.picks.roll?.rule).toBe("prefix");                            // its own, not ATT's
    expect(lane.origin).toEqual({ ids: ["r", "ORGN[0].Lat [deg]", "ORGN[0].Lng [deg]", "ORGN[0].Alt [m]"].slice(1).map((n) => `${c[1].runId}/${n}`), via: "ORGN[0]", rule: "known" });
    expect(c[2].lane).toEqual({ ekf: "EKF3", n: 1 });
    expect(one(["NKF1[0].PN", "NKF1[0].PE", "NKF1[0].PD", "NKF1[0].Roll"])[0]).toMatchObject({ prefix: "NKF1[0]", pos: "ned", lane: { ekf: "EKF2", n: 0 } });
  });

  it("F2: PX4 and MAVLink local positions (x / y / z are NED there), with their origins", () => {
    const px4 = one(["vehicle_local_position.x", "vehicle_local_position.y", "vehicle_local_position.z", "vehicle_local_position.vx",
      "vehicle_local_position.vy", "vehicle_local_position.vz", "vehicle_local_position.heading", "vehicle_local_position.ref_lat",
      "vehicle_local_position.ref_lon", "vehicle_local_position.ref_alt", ...[0, 1, 2, 3].map((i) => `vehicle_attitude.q[${i}]`)]);
    expect(px4.map((x) => [x.prefix, x.pos, x.attitude, x.picks.vn?.name])).toEqual([["vehicle_local_position", "ned", "quaternion", "vehicle_local_position.vx"]]);
    expect(px4[0].origin).toMatchObject({ via: "vehicle_local_position.ref", rule: "own", moves: true });
    const mav = one(["LOCAL_POSITION_NED.x", "LOCAL_POSITION_NED.y", "LOCAL_POSITION_NED.z", "GPS_GLOBAL_ORIGIN.latitude [deg]",
      "GPS_GLOBAL_ORIGIN.longitude [deg]", "GPS_GLOBAL_ORIGIN.altitude [m]", "ATTITUDE.roll [rad]", "ATTITUDE.pitch [rad]", "ATTITUDE.yaw [rad]"]);
    expect(mav.map((x) => [x.prefix, x.pos, x.attitude, x.origin?.via])).toEqual([["LOCAL_POSITION_NED", "ned", "angles", "GPS_GLOBAL_ORIGIN"]]);
  });

  it("F7: origins and home points are never objects (nor incomplete)", () => {
    const d = detectObjects(run([...COPTER, "HOME_POSITION.latitude", "HOME_POSITION.longitude", "HOME_POSITION.altitude", "home.lat", "home.lon"]));
    expect(d.candidates.map((x) => x.prefix)).not.toContain("ORGN[0]");
    expect(d.candidates.map((x) => x.prefix)).not.toContain("HOME_POSITION");
    expect(d.incomplete.map((x) => x.prefix)).not.toContain("home");
    expect(one(["vehicle_local_position.ref_lat", "vehicle_local_position.ref_lon", "vehicle_local_position.ref_alt"])).toEqual([]);
  });

  it("origins: own, sibling above, and none", () => {
    const f = one(["time", ...xyz("tgt.ned.", ["x", "y", "z"]), ...xyz("ship.ecef_", ["x", "y", "z"]), ...xyz("boat.pos.", ["north", "east", "up"]),
      ...xyz("rov.pos.", ["n", "e", "d"]), "origin.lat", "origin.lon", "origin.alt"]);
    expect(f.map((x) => [x.prefix, x.pos, x.origin?.via, x.origin?.rule])).toEqual([
      ["tgt", "ned", "origin", "sibling"], ["ship", "ecef", undefined, undefined], ["boat", "enu", "origin", "sibling"], ["rov", "ned", "origin", "sibling"]]);
    expect(one([...xyz("sim.tgt.ned.", ["x", "y", "z"]), "sim.tgt.ref_lat", "sim.tgt.ref_lon", "sim.tgt.ref_alt"])[0].origin).toMatchObject({ via: "sim.tgt.ref", rule: "own" });
    expect(one(xyz("tgt.ned.", ["x", "y", "z"]))[0].origin).toBeUndefined();
    // beside it only with a class word (sim.nav_ref beside sim.tgt); an unrelated top-level x.origin is not its origin
    expect(one([...xyz("sim.tgt.ned.", ["x", "y", "z"]), "sim.nav_ref_lat", "sim.nav_ref_lon", "sim.nav_ref_alt"])[0].origin).toMatchObject({ via: "sim.nav_ref", rule: "sibling" });
    expect(one([...xyz("tgt.ned.", ["x", "y", "z"]), "boat.origin.lat", "boat.origin.lon", "boat.origin.alt"])[0].origin).toBeUndefined();
    expect(one([...xyz("a.tgt.ned.", ["x", "y", "z"]), "a.origin.lat", "a.origin.lon"])[0].origin).toBeUndefined();   // no altitude: not an origin
  });

  it("keeps the older flight-log behaviour", () => {
    expect(one(["XKF1[0].Roll", "XKF1[0].Pitch", "XKF1[0].Yaw"])).toEqual([]);          // angles only: no object
    const g = one(["Time", "GPS.Lat [deg]", "GPS.Lng [deg]", "ATT.Roll [deg]", "XKF1[0].Roll [deg]"]);
    expect(g.map((x) => [x.prefix, x.picks.roll?.name])).toEqual([["GPS", "ATT.Roll [deg]"]]);
  });
});
