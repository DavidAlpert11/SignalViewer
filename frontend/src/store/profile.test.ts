// L5 D14: profiles - the at-a-glance numbers and pinned searches in the session (Undo), merged from templates
import { beforeEach, describe, expect, test } from "vitest";
import { actions, useApp } from "../store";
import { GLANCE_MAX, mergeProfile, profileOf } from "./actions/profile";
import { glanceLabel, templateFromTabs } from "../templates";
import { reset, run } from "../test/fixtures";
import { en } from "../i18n/templates";
import builtins from "../../../backend/svcore/builtin_templates.json";

const ws = () => useApp.getState().ws;

describe("profiles", () => {
  beforeEach(() => reset([run("a", ["Engine.Temp", "Speed"])]));

  test("pin / unpin a number and a search: one Undo step each, no duplicates, four at most", () => {
    expect(actions.pinGlance("Engine.Temp", "max")).toBe(true);
    expect(actions.pinGlance("Engine.Temp", "max")).toBe(false);
    expect(ws().glance).toEqual([{ name: "Engine.Temp", stat: "max" }]);
    useApp.getState().undo();
    expect(ws().glance).toBeUndefined();
    ["min", "max", "mean", "final"].forEach((s) => actions.pinGlance("Speed", s as "max"));
    expect(ws().glance).toHaveLength(GLANCE_MAX);
    expect(actions.pinGlance("Speed", "range")).toBe(false);
    actions.unpinGlance(0);
    expect(ws().glance!.map((g) => g.stat)).toEqual(["max", "mean", "final"]);
    expect(actions.pinSearch("  Engine_ ")).toBe(true);
    expect(actions.pinSearch("Engine_")).toBe(false);
    expect(ws().searches).toEqual([{ q: "Engine_" }]);
    actions.unpinSearch("Engine_");
    expect(ws().searches).toBeUndefined();
  });

  test("a template's profile merges by key (its own first, then its parts) and never past four numbers", () => {
    const w = { tabs: [], activeTab: "", glance: [{ name: "Speed", stat: "max" as const }] };
    const added = mergeProfile(w, [
      { glance: [{ name: "Speed", stat: "max" }, { name: "A", stat: "min", label: "@glMinVolt" }], searches: [{ q: "BAT" }] },
      { glance: [{ name: "B", stat: "final" }, { name: "C", stat: "mean" }, { name: "D", stat: "max" }], searches: [{ q: "BAT" }, { q: "GPS" }] },
    ]);
    expect(added).toEqual({ glance: 3, searches: 2 });
    expect(w.glance.map((g) => g.name)).toEqual(["Speed", "A", "B", "C"]);
    expect((w as { searches?: unknown }).searches).toEqual([{ q: "BAT" }, { q: "GPS" }]);
  });

  test("saved with a template; an empty profile adds no fields (older templates stay the same)", () => {
    expect(profileOf(ws())).toEqual({});
    expect(templateFromTabs(ws().tabs, "T").template).not.toHaveProperty("glance");
    actions.pinGlance("Engine.Temp", "max");
    actions.pinSearch("Engine");
    const t = templateFromTabs(ws().tabs, "T").template;
    expect(t.glance).toEqual([{ name: "Engine.Temp", stat: "max" }]);
    expect(t.searches).toEqual([{ q: "Engine" }]);
  });

  test("labels: a profile's key translated, else the statistic and the first name", () => {
    expect(glanceLabel({ name: "BAT.Volt|BATT.Volt", stat: "min", label: "@glMinVolt" }, "en")).toBe("Lowest voltage");
    expect(glanceLabel({ name: "BAT.Volt|BATT.Volt", stat: "min" }, "en")).toBe("min BAT.Volt");
    expect(glanceLabel({ name: "X", stat: "final" }, "he")).toBe("אחרון X");
  });

  test("every built-in profile label has its words", () => {
    const labels = (builtins as { glance?: { label?: string }[] }[]).flatMap((t) => t.glance ?? []).map((g) => g.label).filter(Boolean) as string[];
    expect(labels.length).toBeGreaterThan(10);
    for (const l of labels) expect(en).toHaveProperty(l.slice(1));
  });
});
