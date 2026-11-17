import { beforeEach, describe, expect, it, vi } from "vitest";

// the backend is never reached here: every call waits forever (the store's own calls are not what is tested)
vi.mock("../api", () => ({ call: () => new Promise(() => { /* never */ }) }));

const { emptyQuestion, emptyView } = await import("./model");
const { useSweeps } = await import("./state");
const { acrossFilters, modeKeep, ownFilters, runsTabAsk, setKeep } = await import("./tabs");
const { runSelection } = await import("./selection");
const { tableRows } = await import("./view");
type Study = import("./state").Study;
type Col = import("./model").Col;

const num = (name: string, v: number[], group: Col["group"]): Col => ({ name, kind: "num", values: Float32Array.from(v), group });

/* 3 parameter sets (kp = 1, 2, 3), 2 runs each (wind 0 / 5): err per run, and its mean per set */
const ERR = [1, 9, 2, 4, 8, 8];
function study(): Study {
  const columns = [
    { name: "kp", kind: "number", role: "param", scale: "linear", guessRole: "param", guessScale: "linear", distinct: 3, missing: 0 },
    { name: "wind", kind: "number", role: "hold", scale: "linear", guessRole: "hold", guessScale: "linear", distinct: 2, missing: 0 },
    { name: "err", kind: "number", role: "output", scale: "linear", guessRole: "output", guessScale: "linear", distinct: 6, missing: 0 },
  ];
  const answer = {
    counts: { sets: 3, holding: 3, complete: 3, combos: 2, rows: 6 }, conditions: [], seconds: 0,
    sets: [num("kp", [1, 2, 3], "param"), num("err", [5, 3, 8], "output"), num("#holds", [1, 1, 1], "result"), num("#rank", [NaN, NaN, NaN], "result")],
    runs: { sampled: false, total: 6, n: 6, columns: [num("kp", [1, 1, 2, 2, 3, 3], "run"), num("wind", [0, 5, 0, 5, 0, 5], "run"),
      num("err", ERR, "run"), num("#set", [0, 0, 1, 1, 2, 2], "run"), num("#holds", [1, 1, 1, 1, 1, 1], "run")] },
  };
  return {
    tableId: "T", path: "/x/T.csv", name: "T", rows: 6, seconds: 0, columns, head: [], summary: {} as never,
    question: emptyQuestion(), view: { ...emptyView(), show: "all" }, answer, evaluating: false, evalError: "", changed: false, offer: null,
    sources: [], merged: [], history: { past: [], future: [], kind: "", at: 0 }, log: [], iterations: [],
    tables: [], use: 0, shown: 0, picked: [],
  } as unknown as Study;
}

const now = () => useSweeps.getState().studies[0];
const keepOf = (s: Study) => {
  const cols = new Map((s.view.mode === "runs" ? s.answer!.runs!.columns : s.answer!.sets).map((c) => [c.name, c]));
  return Array.from(modeKeep(s, cols, s.view.mode === "runs" ? 6 : 3, null));
};

beforeEach(() => useSweeps.setState({ studies: [study()], active: 0, undoOrder: [], redoOrder: [] }));

describe("a filter remembers the tab it was made in (FT9)", () => {
  it("a filter on an output's mean made in Parameter sets keeps every run of those sets in All runs", () => {
    useSweeps.getState().setFilter("err", { kind: "ranges", ranges: [[2.5, 5.5]] });      // means 5 and 3: sets 0 and 1
    expect(now().view.filterTab).toEqual({ err: "sets" });
    expect(keepOf(now())).toEqual([1, 1, 0]);
    useSweeps.getState().setView({ mode: "runs" });
    const s = now();
    // every run of sets 0 and 1 - not the runs whose own err is in 2.5..5.5 (only one, 4)
    expect(keepOf(s)).toEqual([1, 1, 1, 1, 0, 0]);
    expect(ownFilters(s)).toEqual({});                       // not drawn on the runs' err axis
    expect(Object.keys(acrossFilters(s))).toEqual(["err"]);  // the chip says it
    expect(runSelection(s)).toEqual({ filters: {}, sets: [0, 1] });      // what the server resolves: every run of them
    expect(tableRows(s).sort()).toEqual([0, 1]);
    // back again: the same sets
    useSweeps.getState().setView({ mode: "sets" });
    expect(keepOf(now())).toEqual([1, 1, 0]);
  });

  it("a filter made in All runs keeps runs; in Parameter sets, the sets with a run that passes (the server's answer)", () => {
    useSweeps.getState().setView({ mode: "runs" });
    useSweeps.getState().setFilter("err", { kind: "ranges", ranges: [[7, 10]] });          // runs 1 (set 0), 4, 5 (set 2)
    expect(now().view.filterTab).toEqual({ err: "runs" });
    expect(keepOf(now())).toEqual([0, 1, 0, 0, 1, 1]);
    expect(runSelection(now()).filters).toEqual({ err: { kind: "ranges", ranges: [[7, 10]] } });
    useSweeps.getState().setView({ mode: "sets" });
    const s = now(), ask = runsTabAsk(s)!;
    expect(ask.select).toEqual({ filters: { err: { kind: "ranges", ranges: [[7, 10]] } }, sets: null });
    expect(setKeep(s).pending).toBe(true);
    expect(Object.keys(acrossFilters(s))).toEqual(["err"]);
    // the server's answer: sets 0 and 2 have such a run (set 0's mean, 5, is outside 7..10 - it is kept all the same)
    useSweeps.setState({ studies: [{ ...s, runsTab: { key: ask.key, sets: [0, 2], runs: 3 } }] });
    expect(keepOf(now())).toEqual([1, 0, 1]);
    expect(setKeep(now()).pending).toBe(false);
  });

  it("a filter on a parameter is the same in both tabs; an older study's filters were made in Parameter sets", () => {
    useSweeps.getState().setView({ mode: "runs" });
    useSweeps.getState().setFilter("kp", { kind: "ranges", ranges: [[1.5, 3]] });
    expect(keepOf(now())).toEqual([0, 0, 1, 1, 1, 1]);
    useSweeps.getState().setView({ mode: "sets" });
    expect(keepOf(now())).toEqual([0, 1, 1]);
    expect(acrossFilters(now())).toEqual({});
    const old = study();
    old.view = { ...old.view, filters: { err: { kind: "ranges", ranges: [[7, 9]] } } };     // no filterTab (before FT9)
    useSweeps.setState({ studies: [{ ...old, view: { ...old.view, mode: "runs" } }] });
    expect(keepOf(now())).toEqual([0, 0, 0, 0, 1, 1]);      // set 2 (mean 8): both its runs
  });
});

describe("the holds axis (FT9)", () => {
  it("reads ✓ / ✗", async () => {
    const { makeScale } = await import("./scales");
    expect(makeScale(num("#holds", [1, 0, 1], "result"), "category").ticks.map((x) => x.label)).toEqual(["✗", "✓"]);
  });
});
