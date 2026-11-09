// T1: every workspace change goes through commit - one Undo step each; UI state is not recorded
import { beforeEach, describe, expect, test } from "vitest";
import { actions, activeTab, useApp } from "../store";
import { reset, run } from "../test/fixtures";

const signals = () => activeTab(useApp.getState().ws).plots[0].signals.map((s) => s.sig);

describe("commit / undo / redo", () => {
  beforeEach(() => reset([run("a", ["Speed", "RPM"])]));

  test("a change is one step; undo and redo walk it", () => {
    actions.addSignal("a/Speed");
    actions.addSignal("a/RPM");
    expect(signals()).toEqual(["a/Speed", "a/RPM"]);
    useApp.getState().undo();
    expect(signals()).toEqual(["a/Speed"]);
    useApp.getState().undo();
    expect(signals()).toEqual([]);
    useApp.getState().redo();
    expect(signals()).toEqual(["a/Speed"]);
  });

  test("a commit that changes nothing records nothing; a new change drops the redo steps", () => {
    actions.addSignal("a/Speed");
    useApp.getState().commit((ws) => ws);
    expect(useApp.getState().past.length).toBe(1);
    useApp.getState().undo();
    actions.addSignal("a/RPM");
    expect(useApp.getState().future).toEqual([]);
    expect(signals()).toEqual(["a/RPM"]);
  });

  test("the function gets a copy: the state before stays as it was (undo restores it)", () => {
    const before = useApp.getState().ws;
    useApp.getState().commit((ws) => { ws.tabs[0].name = "Renamed"; return ws; });
    expect(before.tabs[0].name).not.toBe("Renamed");
    useApp.getState().undo();
    expect(useApp.getState().ws).toBe(before);
  });

  test("UI state (panels, tolerances, the cursor) is not an undo step", () => {
    useApp.setState({ panel: "compare", compareTol: { default: { abs: 1 }, signals: {} } });
    expect(useApp.getState().past.length).toBe(0);
  });

  test("history keeps the last 100 changes", () => {
    for (let i = 0; i < 120; i++) useApp.getState().commit((ws) => { ws.tabs[0].name = `n${i}`; return ws; });
    expect(useApp.getState().past.length).toBe(100);
  });

  test("an undo removes the toasts whose action undid the last change", () => {
    actions.addSignal("a/Speed");
    useApp.setState({ toasts: [{ id: "x", kind: "info", text: "Removed", undoesWs: true } as never] });
    useApp.getState().undo();
    expect(useApp.getState().toasts).toEqual([]);
  });
});
