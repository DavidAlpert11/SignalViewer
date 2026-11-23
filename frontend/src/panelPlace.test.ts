// Owner, 2026-11-23: the workspaces are pages on the whole stage (components/rail.ts). The rule: the Report always;
// Messages by default; Investigate while What changed is shown; the ⤢ / ⤡ choice is remembered; something done that
// needs the plots puts them back beside the page for now only; a new answer forgets that.
import { beforeEach, describe, expect, test } from "vitest";
import { useApp } from "./store";
import { reset, run } from "./test/fixtures";
import { canFill, forgetPlotsBeside, isFull, setFull, showPlotsBeside } from "./components/rail";
import { setPref } from "./prefs";

const st = () => useApp.getState();
const full = (id: Parameters<typeof isFull>[0]) => isFull(id, st());

describe("where a panel is shown", () => {
  beforeEach(() => {
    reset([run("a", ["Speed"])]);
    for (const id of ["investigate", "messages"]) setPref(`sv3.full.${id}`, null);
    useApp.setState({ panelFull: {}, whatChanged: null, panel: "data" });
  });

  test("the tools beside the plots, the workspaces as pages", () => {
    expect(full("report")).toBe(true);
    expect(full("data")).toBe(false);
    expect(canFill("compare")).toBe(false);
    expect(full("messages")).toBe(true);
    expect(full("investigate")).toBe(false);                 // nothing to read yet: the cursors are placed on the plots
    useApp.setState({ whatChanged: { a: 1, b: 2 } });
    expect(full("investigate")).toBe(true);
  });

  test("the user's choice is remembered over the rule", () => {
    setFull("messages", false);
    useApp.setState({ panelFull: {} });                     // a new session: from the remembered choice
    expect(full("messages")).toBe(false);
    setFull("investigate", true);
    useApp.setState({ panelFull: {} });
    expect(full("investigate")).toBe(true);
  });

  test("the plots come back for now, a new answer forgets it", () => {
    useApp.setState({ panel: "messages" });
    showPlotsBeside();
    expect(full("messages")).toBe(false);
    forgetPlotsBeside("messages");
    expect(full("messages")).toBe(true);
    useApp.setState({ panel: "data" });
    showPlotsBeside();                                       // a tool beside the plots: nothing to move
    expect(st().panelFull).toEqual({});
  });
});
