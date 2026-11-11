import { describe, expect, it } from "vitest";
import { replayEvents, replayFileName, replayMoment } from "./replay";
import type { LogInfo } from "./api";

const log = (events: LogInfo["events"], timeOffset = 0): { info: LogInfo } =>
  ({ info: { vehicle: null, firmware: null, hasDefaults: false, timeOffset, params: [], events } });

describe("replayMoment", () => {
  it("opens on the cursor when it is on", () => {
    expect(replayMoment({ on: true, t1: 42.5 }, [0, 100])).toBe(42.5);
  });
  it("else the middle of what is shown, else the start (null)", () => {
    expect(replayMoment({ on: false, t1: 42.5 }, [10, 30])).toBe(20);
    expect(replayMoment({ on: false, t1: null }, null)).toBeNull();
    expect(replayMoment({ on: true, t1: null }, null)).toBeNull();
  });
});

describe("replayEvents", () => {
  it("marks what the app's timeline marks: errors and warnings (not modes or info), findings, notes - in time order", () => {
    const ev = replayEvents(
      [log([
        { t: 30, kind: "mode", text: "AUTO", level: "info" },
        { t: 20, kind: "msg", text: "EKF variance", level: "warning" },
        { t: 5, kind: "msg", text: "Armed", level: "info" },
        { t: 60, kind: "error", text: "GPS lost", level: "error" },
      ], 100)],
      [{ t: 140, text: "Vibration high", level: "warning" }, { t: 150, text: "All good", level: "ok" }],
      [{ t: 10, text: "look here" }],
    );
    expect(ev.map((e) => [e.t, e.level, e.text])).toEqual([
      [10, "note", "look here"], [120, "warning", "EKF variance"], [140, "finding", "Vibration high"], [160, "error", "GPS lost"]]);
  });
  it("drops marks with no time and keeps at most 500", () => {
    const many = Array.from({ length: 700 }, (_, i) => ({ t: i, text: "n" }));
    expect(replayEvents([], [{ t: NaN, text: "x", level: "error" }], many)).toHaveLength(500);
  });
});

describe("replayFileName", () => {
  it("names the page after the first file, else the tab", () => {
    expect(replayFileName("Attitude", "copter_flight.bin")).toBe("copter_flight-replay.html");
    expect(replayFileName("My tab", undefined)).toBe("My_tab-replay.html");
    expect(replayFileName("", "")).toBe("signalviewer-replay.html");
    expect(replayFileName("t", "a:b?c.csv")).toBe("a_b_c-replay.html");
  });
});
