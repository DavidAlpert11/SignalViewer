// N4: style a whole group of signals at once - which lines a scope hits, the one change, one Undo
import { beforeEach, expect, test } from "vitest";
import { actions, newPlot, newTab, TRACE_COLORS, useApp, type PlotSignal, type Workspace } from "./store";
import { reset, run } from "./test/fixtures";
import { applyLook, defaultScope, linesInScope, restyle } from "./styleLines";

const line = (sig: string, extra: Partial<PlotSignal> = {}): PlotSignal => ({ sig, color: "#000000", width: 1, scale: 1, offset: 0, ...extra });

/** Two tabs: the active one with two plots (the second active), another with one. */
function build(): Workspace {
  const a = newTab(1), b = newTab(2);
  const p2 = newPlot();
  a.plots[0].signals = [line("a/Roll"), line("a/Pitch"), line("a/Alt")];
  p2.signals = [line("a/Roll"), line("a/Yaw")];
  a.plots.push(p2); a.cols = 2; a.active = 1;
  b.plots[0].signals = [line("a/Pitch"), line("a/Roll")];
  return { tabs: [a, b], activeTab: a.id };
}

beforeEach(() => { reset([run("a", ["Roll", "Pitch", "Yaw", "Alt"])]); });

test("which lines a scope hits: this plot, this tab, every tab - in drawing order", () => {
  const ws = build();
  const g = ["a/Roll", "a/Pitch"];
  const [a, b] = ws.tabs;
  expect(linesInScope(ws, g, "plot")).toEqual([{ plotId: a.plots[1].id, sig: "a/Roll" }]);
  expect(linesInScope(ws, g, "tab")).toEqual([
    { plotId: a.plots[0].id, sig: "a/Roll" }, { plotId: a.plots[0].id, sig: "a/Pitch" }, { plotId: a.plots[1].id, sig: "a/Roll" }]);
  expect(linesInScope(ws, g, "all")).toHaveLength(5);
  expect(linesInScope(ws, g, "all").slice(3)).toEqual([{ plotId: b.plots[0].id, sig: "a/Pitch" }, { plotId: b.plots[0].id, sig: "a/Roll" }]);
  expect(linesInScope(ws, ["a/Nothing"], "all")).toEqual([]);
});

test("the dialog opens on the narrowest scope that reaches a line", () => {
  const ws = build();
  expect(defaultScope(ws, ["a/Roll"])).toBe("plot");
  expect(defaultScope(ws, ["a/Alt"])).toBe("tab");
  expect(defaultScope(ws, ["a/Nothing"])).toBe("all");
});

test("restyle: keep what is left out, palette in turn, styles written as the Inspector writes them", () => {
  const s = line("a/Roll", { dash: true, color: "#123456", width: 2 });
  expect(restyle(s, {}, 0)).toEqual(s);
  expect(restyle(s, { color: "palette" }, 1).color).toBe(TRACE_COLORS[1]);
  expect(restyle(s, { width: 99 }, 0).width).toBe(6);
  const dot = restyle(s, { lineStyle: "dot" }, 0);
  expect(dot.lineStyle).toBe("dot"); expect(dot.dash).toBeUndefined();
  expect(restyle(dot, { lineStyle: "dash" }, 0)).toMatchObject({ dash: true });
  expect(restyle(dot, { lineStyle: "dash" }, 0).lineStyle).toBeUndefined();
  const auto = restyle(s, { lineStyle: "auto" }, 0);
  expect(auto.dash).toBeUndefined(); expect(auto.lineStyle).toBeUndefined();
});

test("applyLook counts only the lines that change; other signals are untouched", () => {
  const ws = build();
  const t = linesInScope(ws, ["a/Roll"], "all");
  const r = applyLook(ws, t, { color: "#E69F00" });
  expect(r.changed).toBe(3);
  expect(r.ws.tabs[0].plots[0].signals[1].color).toBe("#000000");          // Pitch
  expect(applyLook(r.ws, t, { color: "#E69F00" }).changed).toBe(0);
});

test("styleLines is one Undo step; nothing to change makes none", () => {
  useApp.getState().commit(() => build());
  const ws = useApp.getState().ws;
  const past = useApp.getState().past.length;
  const t = linesInScope(ws, ["a/Roll", "a/Pitch"], "tab");
  expect(actions.styleLines(t, { color: "palette", width: 2.5, lineStyle: "dashdot" })).toBe(3);
  expect(useApp.getState().past.length).toBe(past + 1);
  const sigs = useApp.getState().ws.tabs[0].plots[0].signals;
  expect(sigs.map((s) => s.color)).toEqual([TRACE_COLORS[0], TRACE_COLORS[1], "#000000"]);
  expect(sigs[0]).toMatchObject({ width: 2.5, lineStyle: "dashdot" });
  expect(useApp.getState().ws.tabs[1].plots[0].signals[0].width).toBe(1);   // another tab: left alone
  expect(actions.styleLines(t, { width: 2.5 })).toBe(0);
  expect(useApp.getState().past.length).toBe(past + 1);
  useApp.getState().undo();
  expect(useApp.getState().ws.tabs[0].plots[0].signals[0].width).toBe(1);
});
