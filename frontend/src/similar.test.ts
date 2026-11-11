import { describe, expect, it } from "vitest";
import { angleWrap, familiesOf, findFamilies, referenceOf } from "./similar";

const sigs = (names: string[]) => names.map((n) => ({ id: `r/${n}`, name: n }));
const THREE = "phys.lat,phys.lon,phys.alt,phys.att.roll,phys.att.pitch,phys.att.yaw,phys.vel.north,phys.vel.east,nav.lat,nav.lon,nav.alt,nav.att.roll,nav.att.pitch,nav.att.yaw,nav.vel.north,nav.vel.east,gps.lat,gps.lon,gps.alt".split(",");

describe("similar signals (L9)", () => {
  it("class words: phys / nav / gps - one family per leaf, the truth as reference", () => {
    const f = findFamilies(sigs(THREE));
    const roll = f.find((x) => x.leaf === "*.att.roll")!;
    expect(roll.how).toBe("class");
    expect(roll.members.map((m) => m.seg)).toEqual(["phys", "nav"]);
    expect(referenceOf(roll).seg).toBe("phys");
    expect(f.find((x) => x.leaf === "*.lat")!.members).toHaveLength(3);
  });
  it("instances and numbers: XKF1[0] / XKF1[1], nav1 / nav2, ekf_2 / ekf_3", () => {
    const f = findFamilies(sigs(["XKF1[0].Roll [deg]", "XKF1[1].Roll [deg]", "XKF1[0].PN [m]", "XKF1[1].PN [m]", "nav1.att.roll", "nav2.att.roll", "ekf_2.v", "ekf_3.v"]));
    expect(f.map((x) => [x.leaf, x.how])).toEqual([["XKF1[*].Roll", "instance"], ["XKF1[*].PN", "instance"], ["nav*.att.roll", "number"], ["ekf*.v", "number"]]);
    // beside ATT.Roll (the same leaf, an unrelated group): the lanes are still their own family
    const g = findFamilies(sigs(["ATT.Roll [deg]", "XKF1[0].Roll [deg]", "XKF1[1].Roll [deg]", "nav.Roll [deg]", "truth.Roll [deg]"]));
    expect(g.map((x) => [x.leaf, x.members.map((m) => m.seg)])).toEqual([["XKF1[*].Roll", ["XKF1[0]", "XKF1[1]"]], ["*.Roll", ["nav", "truth"]]]);
  });
  it("a group gives every leaf under it that has partners", () => {
    const f = familiesOf(findFamilies(sigs(THREE)), ["r/nav.att.roll", "r/nav.att.pitch", "r/nav.att.yaw"]);
    expect(f.map((x) => x.leaf)).toEqual(["*.att.roll", "*.att.pitch", "*.att.yaw"]);
  });
  it("not a family: different leaves, unrelated owners; units must agree to subtract", () => {
    expect(findFamilies(sigs(["motor.rpm", "battery.rpm"]))).toEqual([]);
    expect(findFamilies(sigs(["a.x", "a.y"]))).toEqual([]);
    expect(findFamilies(sigs(["nav.alt [m]", "gps.alt [ft]"]))[0].unitsDiffer).toBe(true);
  });
  it("looser matches only when asked, and say how", () => {
    expect(findFamilies(sigs(["imu_a.gx", "imu_b.gx"]))).toEqual([]);
    expect(findFamilies(sigs(["imu_a.gx", "imu_b.gx"]), true)[0].how).toBe("edit");
    expect(findFamilies(sigs(["a.b.roll", "c.roll"]), true)[0]).toMatchObject({ how: "leaf", leaf: "*.roll" });
  });
  it("angle differences are wrapped by one rule", () => {
    expect([angleWrap("XKF1[0].Yaw [deg]"), angleWrap("ATTITUDE.yaw [rad]"), angleWrap("nav.att.yaw"), angleWrap("nav.alt [m]"), angleWrap("x.heading [m]")])
      .toEqual([360, "2pi", "ask", null, null]);
  });
  it("is fast on 5000 names", () => {
    const names = Array.from({ length: 5000 }, (_, i) => `sys${i % 50}.blk${Math.floor(i / 50) % 10}.sig${i % 7}_${i}`)
      .concat(Array.from({ length: 200 }, (_, i) => `nav${i % 4}.grp${Math.floor(i / 4)}.val`));
    const t0 = performance.now();
    const f = findFamilies(sigs(names));
    expect(performance.now() - t0).toBeLessThan(150);
    expect(f.filter((x) => x.leaf.startsWith("nav*"))).toHaveLength(50);
  });
});
