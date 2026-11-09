// T1: sessions - old files keep opening (names of 1.20 logs, missing files, optional fields)
import { beforeEach, describe, expect, test, vi } from "vitest";
import { initialWorkspace, useApp } from "./store";
import { reset, run } from "./test/fixtures";

const restored = run("r1", ["ATT.Yaw [deg]", "BARO.Alt"], { format: "bin" });
vi.mock("./api", async (orig) => {
  const real = await orig<typeof import("./api")>();
  return { ...real, api: { ...real.api,
    restore: vi.fn(async () => ({ restored: [restored], missing: [{ id: "gone", path: "/old/gone.csv", name: "gone.csv" }] })),
    restoreDerived: vi.fn(async () => ({ failed: [] })),
    setTransformSpecs: vi.fn(async () => ({})),
    listRuns: vi.fn(async () => [restored]),
  } };
});
const { applyState, currentState, legacyUnitNames } = await import("./files");

describe("legacyUnitNames (sessions of 1.20 and before)", () => {
  const runs = [{ id: "r1", format: "bin", signals: [{ name: "ATT.Yaw [deg]" }, { name: "MSG.Message" }] }];
  test("[degheading] / [UNKNOWN] become the names the log has now, keys too", () => {
    const st = { ws: { sig: "r1/ATT.Yaw [degheading]", other: "r1/MSG.Message [UNKNOWN]" }, transforms: { "r1/ATT.Yaw [degheading]": 1 } };
    expect(legacyUnitNames(st, runs)).toEqual({ ws: { sig: "r1/ATT.Yaw [deg]", other: "r1/MSG.Message" }, transforms: { "r1/ATT.Yaw [deg]": 1 } });
  });
  test("a name still there, another file, or not a .bin: unchanged", () => {
    expect(legacyUnitNames({ a: "r1/ATT.Yaw [deg]", b: "r2/X [UNKNOWN]" }, runs)).toEqual({ a: "r1/ATT.Yaw [deg]", b: "r2/X [UNKNOWN]" });
    expect(legacyUnitNames({ a: "r1/ATT.Yaw [degheading]" }, [{ ...runs[0], format: "csv" }])).toEqual({ a: "r1/ATT.Yaw [degheading]" });
  });
});

describe("applyState", () => {
  beforeEach(() => reset());
  test("an old session: its references mapped, a missing file's signals dropped, no new fields needed", async () => {
    const ws = initialWorkspace();
    ws.tabs[0].plots[0].signals = [
      { sig: "r1/ATT.Yaw [degheading]", color: "#000000", width: 1.5, scale: 1, offset: 0 },
      { sig: "gone/Speed", color: "#000000", width: 1.5, scale: 1, offset: 0 },
    ];
    ws.tabs[0].plots[0].xSignal = "gone/Time";
    await applyState({ ws, runs: [{ id: "r1", path: "/x.bin" }, { id: "gone", path: "/old/gone.csv" }] }, { announce: false });
    const p = useApp.getState().ws.tabs[0].plots[0];
    expect(p.signals.map((s) => s.sig)).toEqual(["r1/ATT.Yaw [deg]"]);
    expect(p.xSignal).toBeNull();
    expect(useApp.getState().past).toEqual([]);                       // opening a session is not an undo step
    expect(useApp.getState().toasts.some((t) => t.kind === "error")).toBe(true);    // "1 file not found" + Locate
    expect(useApp.getState().ws.report).toBeUndefined();               // 26.U4's verdict: optional
  });
  test("what is saved is what applyState reads back", async () => {
    useApp.setState({ runs: [restored] });
    const s = currentState();
    expect(Object.keys(s).sort()).toEqual(["derived", "journal", "runs", "transforms", "ui", "ws"]);
    expect(s.runs[0]).toMatchObject({ id: "r1", path: restored.path });
  });
});
