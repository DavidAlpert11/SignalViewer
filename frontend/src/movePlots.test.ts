// N2: plots change places in the grid - one Undo, the active plot follows, the cell sizes stay
import { beforeEach, expect, test } from "vitest";
import { actions, activeTab, useApp } from "./store";
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
