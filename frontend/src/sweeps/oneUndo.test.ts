import { beforeEach, describe, expect, it, vi } from "vitest";

// the backend is never reached here: every call waits forever (the answers are not what is tested)
vi.mock("../api", () => ({ call: () => new Promise(() => { /* never */ }) }));

const { emptyQuestion, emptyView } = await import("./model");
const { emptyCommon, useSweeps } = await import("./state");
const { editStudy, redoStudy, undoStudy, useStudyPanel } = await import("./studyStore");
type TableStudy = import("./state").Study;

function table(id: string): TableStudy {
  const columns = [
    { name: "kp", kind: "number", role: "param", scale: "linear", guessRole: "param", guessScale: "linear", distinct: 4, missing: 0 },
    { name: "err", kind: "number", role: "output", scale: "linear", guessRole: "output", guessScale: "linear", distinct: 40, missing: 0 },
  ];
  return {
    tableId: id, path: `/x/${id}.csv`, name: id, rows: 40, seconds: 0, columns, head: [], summary: {} as never,
    question: emptyQuestion(), view: emptyView(), answer: null, evaluating: false, evalError: "", changed: false, offer: null,
    sources: [], merged: [], history: { past: [], future: [], kind: "", at: 0 }, log: [], iterations: [],
    tables: [], use: 0, shown: 0, picked: [],
  } as unknown as TableStudy;
}

const goal = () => useSweeps.getState().studies[useSweeps.getState().active].question.goal;
const setupName = () => useStudyPanel.getState().study?.name;

beforeEach(() => {
  useSweeps.setState({ studies: [table("A"), table("B")], active: 0, undoOrder: [], redoOrder: [],
    common: { ...emptyCommon(), open: true, study: { version: 1, name: "s0", tables: [] } } });
});

describe("one Undo for the area (C4)", () => {
  it("undoes a set-up edit and a goal edit in the order they were made, and redoes them", () => {
    editStudy((s) => ({ ...s, name: "s1" }));                                         // the study file (Set up)
    useSweeps.getState().updateGoal({ optimize: [{ column: "err", direction: "min", weight: 1 }] });   // a table's goal
    expect(setupName()).toBe("s1");
    expect(goal()).toEqual({ column: "err", direction: "min" });
    expect(useSweeps.getState().undoOrder).toEqual(["setup", "t:A"]);

    undoStudy();
    expect(goal()).toBeNull();
    expect(setupName()).toBe("s1");
    undoStudy();
    expect(setupName()).toBe("s0");
    redoStudy();
    expect(setupName()).toBe("s1");
    expect(goal()).toBeNull();
    redoStudy();
    expect(goal()).toEqual({ column: "err", direction: "min" });
  });

  it("a table's edits made around a set-up edit are two steps, not one (no merging across it)", () => {
    const st = useSweeps.getState();
    st.updateGoal({ optimize: [{ column: "err", direction: "min", weight: 1 }] });
    editStudy((s) => ({ ...s, name: "s1" }));
    useSweeps.getState().updateGoal({ optimize: [{ column: "err", direction: "max", weight: 1 }] });   // within the merge time
    expect(useSweeps.getState().undoOrder).toEqual(["t:A", "setup", "t:A"]);
    undoStudy();
    expect(goal()).toEqual({ column: "err", direction: "min" });
    undoStudy();
    expect(setupName()).toBe("s0");
    undoStudy();
    expect(goal()).toBeNull();
  });

  it("the step of another table shows that table, and a new edit clears Redo", () => {
    useSweeps.getState().updateGoal({ optimize: [{ column: "err", direction: "min", weight: 1 }] });
    useSweeps.setState({ active: 1 });
    editStudy((s) => ({ ...s, name: "s1" }));
    undoStudy();
    undoStudy();
    expect(useSweeps.getState().active).toBe(0);
    expect(goal()).toBeNull();
    expect(useSweeps.getState().redoOrder).toEqual(["setup", "t:A"]);
    editStudy((s) => ({ ...s, name: "s2" }));
    expect(useSweeps.getState().redoOrder).toEqual([]);
    redoStudy();
    expect(goal()).toBeNull();
  });

  it("the study file's state is a view on the one store (old tests read __svStudy)", () => {
    editStudy((s) => ({ ...s, name: "s1" }));
    expect(useSweeps.getState().common.study?.name).toBe("s1");
    useStudyPanel.setState({ pinned: 3 });
    expect(useSweeps.getState().common.pinned).toBe(3);
    const view = (window as unknown as { __svStudy: { state: () => { pinned: number } } }).__svStudy;
    expect(view.state().pinned).toBe(3);
  });
});
