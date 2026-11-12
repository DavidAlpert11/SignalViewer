// W10: the workspace revision - commit bumps it, undo / redo bring back the revision they restore, a save
// marks it, UI-only state does not touch it; the close prompt asks only when it differs from the saved one
import { beforeEach, describe, expect, test } from "vitest";
import { actions, useApp } from "./store";
import { reset, run } from "./test/fixtures";
import { isDirty } from "./unsaved";

const st = () => useApp.getState();

describe("the workspace revision", () => {
  beforeEach(() => { reset([run("a", ["Speed", "RPM"])]); st().markSaved(); useApp.setState({ askBeforeClose: true }); });

  test("commit bumps it; nothing saved = unsaved", () => {
    const r0 = st().wsRev;
    expect(isDirty()).toBe(false);
    actions.addSignal("a/Speed");
    expect(st().wsRev).toBeGreaterThan(r0);
    expect(isDirty()).toBe(true);
  });

  test("undo back to the saved workspace is saved again; redo is not", () => {
    actions.addSignal("a/Speed");
    st().markSaved();
    actions.addSignal("a/RPM");
    expect(isDirty()).toBe(true);
    st().undo();
    expect(isDirty()).toBe(false);
    st().redo();
    expect(isDirty()).toBe(true);
    st().undo(); st().undo();
    expect(isDirty()).toBe(true);                    // before the save: unsaved too
  });

  test("a save resets it", () => {
    actions.addSignal("a/Speed");
    st().markSaved();
    expect(isDirty()).toBe(false);
    expect(st().savedRev).toBe(st().wsRev);
  });

  test("UI-only state does not bump it", () => {
    const r0 = st().wsRev;
    useApp.setState({ theme: st().theme === "dark" ? "light" : "dark", paletteOpen: true });
    actions.toggleCursor();
    expect(st().wsRev).toBe(r0);
    expect(isDirty()).toBe(false);
  });

  test("a commit that changes nothing does not bump it", () => {
    const r0 = st().wsRev;
    st().commit((ws) => ws);
    expect(st().wsRev).toBe(r0);
  });

  test("the setting off: never asks", () => {
    actions.addSignal("a/Speed");
    useApp.setState({ askBeforeClose: false });
    expect(isDirty()).toBe(false);
  });
});
