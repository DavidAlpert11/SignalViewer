// N2: plots change places in the grid - one Undo, the active plot follows, the cell sizes stay
import { beforeEach, expect, test } from "vitest";
import { actions, activeTab, newPlot, useApp, type MapObject } from "./store";
import { reset, run } from "./test/fixtures";

beforeEach(() => {
  reset([run("a", ["x"])]);
  actions.setLayout(2, 2);
  useApp.getState().commit((ws) => {
    const tab = ws.tabs[0];
    tab.plots.forEach((p, i) => { p.title = `P${i}`; });
    tab.colSizes = [2, 1];
    tab.active = 0;
    return ws;
  });
});
const titles = () => activeTab(useApp.getState().ws).plots.map((p) => p.title);

test("swap: the two plots change places, the active one moves with it, one Undo", () => {
  actions.swapPlots(0, 3);
  expect(titles()).toEqual(["P3", "P1", "P2", "P0"]);
  expect(activeTab(useApp.getState().ws).active).toBe(3);
  expect(activeTab(useApp.getState().ws).colSizes).toEqual([2, 1]);       // the cells keep their sizes
  useApp.getState().undo();
  expect(titles()).toEqual(["P0", "P1", "P2", "P3"]);
});

test("the neighbour by the grid; nothing past an edge", () => {
  expect(actions.moveActivePlot("right")).toBe(true);
  expect(titles()).toEqual(["P1", "P0", "P2", "P3"]);
  expect(actions.moveActivePlot("right")).toBe(false);                   // at the row's end
  expect(actions.moveActivePlot("down")).toBe(true);
  expect(titles()).toEqual(["P1", "P3", "P2", "P0"]);
  expect(actions.moveActivePlot("down")).toBe(false);
  expect(actions.moveActivePlot("up")).toBe(true);
  expect(titles()).toEqual(["P1", "P0", "P2", "P3"]);
  actions.swapPlots(1, 1);                                                // nothing to do: no undo step
  expect(titles()).toEqual(["P1", "P0", "P2", "P3"]);
});

/* ---- L10: a plot to another tab, or into another plot --------------------------------------------- */

const ws = () => useApp.getState().ws;
const sigP = (title: string, sigs: string[]) => ({ ...newPlot(), title, signals: sigs.map((s) => ({ sig: s, color: "#fff", width: 1.5, scale: 1, offset: 0 })) });
function twoTabs(second: { rows: number; cols: number; plots: ReturnType<typeof sigP>[] }) {
  useApp.getState().commit((w) => {
    w.tabs[0].plots[0] = sigP("A", ["a/x"]);
    w.tabs.push({ id: "t2", name: "Two", rows: second.rows, cols: second.cols, plots: second.plots, active: 0, linkX: true });
    return w;
  });
}

test("move to another tab: into its first empty cell; the source cell left empty; one Undo", () => {
  twoTabs({ rows: 1, cols: 2, plots: [sigP("B", ["a/x"]), newPlot()] });
  const id = ws().tabs[0].plots[0].id;
  expect(actions.movePlotToTab(id, "t2")).toBe(true);
  const t2 = ws().tabs[1];
  expect(t2.plots[1].id).toBe(id);                                        // the same plot (axes, cursors, objects go with it)
  expect(ws().tabs[0].plots[0].signals).toEqual([]);                       // the cell stays, empty
  expect(ws().tabs[0].plots).toHaveLength(4);                              // the grid did not reflow
  expect([ws().activeTab, t2.active]).toEqual(["t2", 1]);
  useApp.getState().undo();
  expect(ws().tabs[0].plots[0].id).toBe(id);
});

test("a full row grows the grid, keeping every plot's row and column; a full tab is refused", () => {
  twoTabs({ rows: 1, cols: 1, plots: [sigP("B", ["a/x"])] });
  const id = ws().tabs[0].plots[0].id;
  expect(actions.movePlotToTab(id, "t2")).toBe(true);
  expect([ws().tabs[1].rows, ws().tabs[1].cols, ws().tabs[1].plots.map((p) => p.title)]).toEqual([1, 2, ["B", "A"]]);
  useApp.getState().undo();
  useApp.getState().commit((w) => { const t = w.tabs[1]; t.rows = 3; t.cols = 3; t.plots = Array.from({ length: 9 }, (_, k) => sigP(`F${k}`, ["a/x"])); return w; });
  const n = useApp.getState().toasts?.length ?? 0;
  expect(actions.movePlotToTab(id, "t2")).toBe(false);
  expect(ws().tabs[0].plots[0].id).toBe(id);
  expect((useApp.getState().toasts ?? []).length).toBeGreaterThan(n);
});

test("a new tab named after the plot; a map keeps its objects and its pair", () => {
  const objs = [{ id: "o1", name: "nav", lat: "a/lat", lon: "a/lon" }, { id: "o2", name: "gps", lat: "a/glat", lon: "a/glon" }] as MapObject[];
  useApp.getState().commit((w) => { w.tabs[0].plots[0] = { ...newPlot(), title: "Map", mode: "geo", objects: objs, primaryObject: "o2", relatedObjects: ["o1"] }; return w; });
  const id = ws().tabs[0].plots[0].id;
  actions.movePlotToTab(id, "new");
  const t = ws().tabs[ws().tabs.length - 1];
  expect([t.name, t.plots[0].id, t.plots[0].objects?.length, t.plots[0].primaryObject, t.plots[0].relatedObjects]).toEqual(["Map", id, 2, "o2", ["o1"]]);
  expect(ws().activeTab).toBe(t.id);
});

test("merge: lines join a plot of the same kind, no duplicates, the source emptied; other kinds refused", () => {
  useApp.getState().commit((w) => {
    w.tabs[0].plots[0] = sigP("A", ["a/x", "a/y"]);
    w.tabs[0].plots[1] = { ...sigP("B", ["a/y"]) };
    w.tabs[0].plots[1].signals[0].axis = "right";
    w.tabs[0].plots[2] = { ...newPlot(), title: "Map", mode: "geo", objects: [{ id: "o", name: "o", lat: "a/lat", lon: "a/lon" } as MapObject] };
    return w;
  });
  const [A, B, M] = ws().tabs[0].plots.map((p) => p.id);
  expect(actions.mergePlotInto(A, B)).toBe(true);
  const b = ws().tabs[0].plots[1];
  expect(b.signals.map((s) => [s.sig, s.axis ?? "left"])).toEqual([["a/y", "right"], ["a/x", "left"]]);
  expect(ws().tabs[0].plots[0].signals).toEqual([]);
  useApp.getState().undo();
  expect(ws().tabs[0].plots[0].signals).toHaveLength(2);
  expect(actions.mergePlotInto(A, M)).toBe(false);                        // time lines into a map: refused
  expect(actions.mergePlotInto(A, B, true)).toBe(true);                    // Copy into: the source kept
  expect(ws().tabs[0].plots[0].signals).toHaveLength(2);
});
