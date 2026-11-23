import { beforeEach, describe, expect, it } from "vitest";
import { useApp, type Workspace } from "./store";
import { reset, run } from "./test/fixtures";
import { addToReport, appendToDoc, defaultDocText, docText, plotRef, prepareDoc, resolveRef, resolveValue, tabRef } from "./reportDoc";

const line = (sig: string) => ({ sig, color: "#3D8BFD", width: 1.5, scale: 1, offset: 0 });
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const R = (x: unknown) => x as any;
function setup(): Workspace {
  reset([run("r1", ["Roll", "RollDes", "Mode"]), run("r2", ["Speed", "Roll"])]);
  useApp.getState().commit((w) => {
    w.tabs[0].name = "Attitude";
    w.tabs[0].plots = [{ id: "p1", title: "Roll", signals: [line("r1/Roll")] }, { id: "p2", title: "", signals: [line("r1/RollDes")] }];
    w.tabs.push({ id: "t2", name: "Nav.Speed", rows: 1, cols: 1, active: 0, plots: [{ id: "p3", title: "Speed", signals: [line("r2/Speed")] }] } as Workspace["tabs"][0]);
    w.conditions = [{ id: "c1", name: "Auto", color: "#000", visible: true, text: "{Mode} > 0.5" }];
    return w;
  });
  return useApp.getState().ws;
}

describe("RE1: references in the written report", () => {
  beforeEach(() => { setup(); });

  it("[[tab]] and [[tab.plot]] by name or by position; a tab name with a dot is written tab<n>", () => {
    const ws = useApp.getState().ws;
    expect(tabRef(ws, ws.tabs[0])).toBe("Attitude");
    expect(tabRef(ws, ws.tabs[1])).toBe("tab2");                       // "Nav.Speed" would read as tab.plot
    expect(plotRef(ws, ws.tabs[0], 0)).toBe("Attitude.Roll");
    expect(plotRef(ws, ws.tabs[0], 1)).toBe("Attitude.plot2");
    const one = R(resolveRef(ws, "Attitude.Roll", "en"));
    expect(one.kind).toBe("plots"); expect(one.plots.map((p: { title: string }) => p.title)).toEqual(["Roll"]);
    expect(R(resolveRef(ws, "tab1", "en")).plots).toHaveLength(2);
    expect(R(resolveRef(ws, "Nav.Speed", "en")).plots).toHaveLength(1);   // the whole name is a tab first
    expect(R(resolveRef(ws, "tab1.plot2 | 10..60, no table", "en")))
      .toMatchObject({ table: "none", plots: [{ range: [10, 60] }] });
  });

  it("what cannot be found says so", () => {
    const ws = useApp.getState().ws;
    expect(resolveRef(ws, "Nope", "en")).toMatchObject({ kind: "error" });
    expect(R(resolveRef(ws, "Attitude.Pitch", "en")).error).toContain("Pitch");
    expect(R(resolveRef(ws, "Attitude | weird", "en")).error).toContain("weird");
  });

  it("{{ }} values: names to ids, quoted condition names and variables left alone, a format at the end", () => {
    const ws = useApp.getState().ws;
    const v = resolveValue(ws, ' rms({r1.csv:Roll} - RollDes, when="Auto") :.2f ', [], "en") as Record<string, unknown>;
    expect(v).toMatchObject({ expr: 'rms(v0 - v1, when="Auto")', sources: ["r1/Roll", "r1/RollDes"], fmt: ".2f" });
    const amb = resolveValue(ws, "max(Speed)", [], "en") as Record<string, unknown>;
    expect(amb).toMatchObject({ expr: "max(v0)", sources: ["r2/Speed"], fmt: "" });
    const a = resolveValue(ws, "peak = max({r1.csv:Roll}, 1, 2)", [], "en") as Record<string, unknown>;
    expect(a).toMatchObject({ assign: "peak", expr: "max(v0, 1, 2)", sources: ["r1/Roll"] });
    expect(resolveValue(ws, "peak * 2", ["peak"], "en")).toMatchObject({ expr: "peak * 2", sources: [] });
    const c = resolveValue(ws, 'holds("Auto", {r1.csv:Mode})', [], "en") as Record<string, unknown>;
    expect(c.expr).toBe('holds("Auto", v0)'); expect(c.conds).toEqual({ Auto: { text: "{Mode} > 0.5", exit: "", minDur: 0, mergeGap: 0 } });
  });

  it("a name in two files asks for the file, as formulas do", () => {
    const v = resolveValue(useApp.getState().ws, "max(Roll)", [], "en") as Record<string, unknown>;
    expect(String(v.error)).toContain("{");
  });

  it("prepareDoc: markers in order, code left as written, problems listed", async () => {
    const ws = useApp.getState().ws;
    const p = await prepareDoc(ws, "A {{ max(Speed) }} `{{ max(x) }}`\n\n[[Attitude.Roll]]\n\n```\n[[nope]]\n```\n[[Missing]]\n[[notes]]", "en");
    expect(p.text).toBe("A ⟦0⟧ `{{ max(x) }}`\n\n⟦1⟧\n\n```\n[[nope]]\n```\n⟦2⟧\n⟦3⟧");
    expect(p.items.map((x) => x.kind)).toEqual(["value", "plots", "error", "notes"]);
    expect(p.problems).toHaveLength(1); expect(p.plots).toBe(1);
  });

  it("RE4: a Markdown comment is left out, its references too - not inside code", async () => {
    const ws = useApp.getState().ws;
    const p = await prepareDoc(ws, "one\n<!-- [[Missing]] -->\n<!-- [[Attitude.Roll]]\n{{ max(Speed) }} -->\ntwo\n`<!-- [[x]] -->`", "en");
    expect(p.items).toHaveLength(0);
    expect(p.problems).toEqual([]);
    expect(p.text).toBe("one\ntwo\n`<!-- [[x]] -->`");
  });

  it("an old session's report opens as the document its form made; Add to report appends", () => {
    useApp.getState().commit((w) => { w.report = { title: "Flight 12", intro: "Why", summary: "", lang: "en", theme: "light", scope: "all" }; return w; });
    const ws = useApp.getState().ws;
    const d = defaultDocText(ws, "en");
    expect(d.startsWith("# Flight 12\n\nWhy\n\n[[process]]")).toBe(true);
    expect(d).toContain("[[Attitude]]"); expect(d).toContain("[[tab2]]");
    expect(ws.report?.doc).toBeUndefined();                             // not written until the user changes it
    addToReport(ws.tabs[0], 0);
    const after = useApp.getState().ws;
    expect(docText(after, "en").trimEnd().endsWith("[[Attitude.Roll]]")).toBe(true);
    useApp.getState().undo();
    expect(useApp.getState().ws.report?.doc).toBeUndefined();          // one undo step
    expect(appendToDoc(structuredClone(after), "en", "x").report?.doc?.text.endsWith("x\n")).toBe(true);
  });
});

describe("RE2: ready-made parts and plots written in the text", () => {
  beforeEach(() => { setup(); });
  it("a part is sent to the server with its words, its options in their case and the open files", () => {
    const ws = useApp.getState().ws;
    const p = R(resolveRef(ws, "tracking roll | tol 2, ref GPS", "en"));
    expect(p).toMatchObject({ kind: "part", part: "tracking", arg: "roll", opts: ["tol 2", "ref GPS"], runs: ["r1", "r2"] });
    expect(R(resolveRef(ws, "summary", "en")).part).toBe("summary");
  });
  it("[[plot …]]: a name in two files is drawn from each, a window and an unknown name said", () => {
    const ws = useApp.getState().ws;
    const p = R(resolveRef(ws, "plot Roll, RollDes | 10..60", "en"));
    expect(p.kind).toBe("plots");
    expect(p.plots[0].signals.map((s: { id: string }) => s.id)).toEqual(["r1/Roll", "r2/Roll", "r1/RollDes"]);
    expect(p.plots[0].range).toEqual([10, 60]);
    expect(R(resolveRef(ws, "plot {r2.csv:Roll}", "en")).plots[0].signals.map((s: { id: string }) => s.id)).toEqual(["r2/Roll"]);
    expect(R(resolveRef(ws, "plot xy Speed, Roll", "en")).plots[0]).toMatchObject({ mode: "xy", xSignal: "r2/Speed" });
    expect(R(resolveRef(ws, "plot Nope", "en")).error).toMatch(/Nope/);
  });
  it("a tab named like a part keeps its name: it is written tab<n>", () => {
    useApp.getState().commit((w) => { w.tabs[0].name = "tracking"; return w; });
    const ws = useApp.getState().ws;
    expect(tabRef(ws, ws.tabs[0])).toBe("tab1");
    expect(R(resolveRef(ws, "tracking", "en")).kind).toBe("plots");        // an old reference to that tab still finds it
  });
});
