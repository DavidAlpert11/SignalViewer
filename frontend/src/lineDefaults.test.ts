// N3: the defaults for new lines (Settings), the one place a PlotSignal is made, the style's precedence
import { beforeEach, expect, test } from "vitest";
import { actions, newPlotSignal, styledSignal, useApp } from "./store";
import { reset, run } from "./test/fixtures";
import { lineLook } from "./desired";

beforeEach(() => { reset([run("a", ["Roll", "DesRoll"])]); useApp.setState({ lineWidth: 1.5, lineStyle: "solid" }); });

test("a new line takes the Settings' width and style; solid adds no style", () => {
  expect(styledSignal("a/Roll", "#111111")).toEqual({ sig: "a/Roll", color: "#111111", width: 1.5, scale: 1, offset: 0 });
  useApp.setState({ lineWidth: 3, lineStyle: "dot" });
  expect(newPlotSignal("a/Roll", useApp.getState().ws)).toMatchObject({ width: 3, lineStyle: "dot" });
  expect(styledSignal("a/Roll", "#111111", { tOffset: 2 })).toMatchObject({ width: 3, lineStyle: "dot", tOffset: 2 });
});

test("lineStyle > the old dash > automatic (a setpoint beside its measured value)", () => {
  const sp = new Set(["a/ATT.DesRoll"]);
  const s = { sig: "a/ATT.DesRoll", color: "#000000", width: 1, scale: 1, offset: 0 };
  expect(lineLook(s, sp)).toEqual({ dashed: true, faded: true, style: "dash" });
  expect(lineLook({ ...s, dash: false }, sp)).toEqual({ dashed: false, faded: false, style: "solid" });
  expect(lineLook({ ...s, dash: false, lineStyle: "dashdot" }, sp)).toEqual({ dashed: true, faded: false, style: "dashdot" });
  expect(lineLook({ ...s, lineStyle: "solid" }, sp).dashed).toBe(false);
  expect(lineLook({ ...s, sig: "a/Roll" }, sp).style).toBe("solid");     // an old session: unchanged
});

test("Apply to all open plots: one Undo, state lanes left alone, nothing to do - no step", () => {
  useApp.getState().commit((ws) => {
    ws.tabs[0].plots[0].signals = [{ sig: "a/Roll", color: "#000000", width: 1, scale: 1, offset: 0, dash: true },
      { sig: "a/DesRoll", color: "#000000", width: 1, scale: 1, offset: 0, state: true }];
    return ws;
  });
  useApp.setState({ lineWidth: 2.5, lineStyle: "dot" });
  actions.applyLineDefaults();
  const sigs = () => useApp.getState().ws.tabs[0].plots[0].signals;
  expect(sigs()[0]).toMatchObject({ width: 2.5, lineStyle: "dot" });
  expect(sigs()[0].dash).toBeUndefined();
  expect(sigs()[1].width).toBe(1);
  const past = useApp.getState().past?.length;
  actions.applyLineDefaults();                                         // already so: no new undo step
  expect(useApp.getState().past?.length).toBe(past);
  useApp.getState().undo();
  expect(sigs()[0]).toMatchObject({ width: 1, dash: true });
});
