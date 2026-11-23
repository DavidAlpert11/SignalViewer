import { describe, expect, it } from "vitest";
import { duplicateLines, indentLines, moveLines, newHistory, record, redo, stripMdComments, toggleComment, undo } from "./editText";

const snap = (text: string, a = text.length, b = a) => ({ text, a, b });

describe("the report editor's undo", () => {
  it("joins a run of typing into one step, a pause or an inserted piece starts another", () => {
    let h = newHistory();
    h = record(h, snap(""), "type", 1000);
    h = record(h, snap("a"), "type", 1100);
    h = record(h, snap("ab"), "type", 1200);
    expect(h.past.map((s) => s.text)).toEqual([""]);
    h = record(h, snap("abc"), "type", 5000);               // after a pause
    h = record(h, snap("abc d"), "put", 5100);              // bold, a plot from the library...
    expect(h.past.map((s) => s.text)).toEqual(["", "abc", "abc d"]);
  });
  it("goes back and forward, and a new change drops what was undone", () => {
    let h = newHistory();
    h = record(h, snap("one"), "put", 0);
    h = record(h, snap("one two"), "put", 10);
    const u = undo(h, snap("one two three"))!;
    expect(u[1].text).toBe("one two");
    const r = redo(u[0], u[1])!;
    expect(r[1].text).toBe("one two three");
    const u2 = undo(r[0], r[1])!;
    const h3 = record(u2[0], u2[1], "put", 20);
    expect(h3.future).toEqual([]);
    expect(undo(newHistory(), snap("x"))).toBeNull();
  });
});

describe("line keys", () => {
  it("Ctrl+/ comments the selected lines and back, empty lines left alone", () => {
    const t = "# T\n\nfirst\n\nsecond\nend";
    const a = t.indexOf("first"), b = t.indexOf("second") + 3;
    const on = toggleComment(t, a, b, false);
    expect(on.text).toBe("# T\n\n<!-- first -->\n\n<!-- second -->\nend");
    const off = toggleComment(on.text, on.a, on.b, false);
    expect(off.text).toBe(t);
  });
  it("Ctrl+/ on a caret: its line; LaTeX with %", () => {
    const t = "a\n  \\section{X}\nb";
    const r = toggleComment(t, 5, 5, true);
    expect(r.text).toBe("a\n  % \\section{X}\nb");
    expect(toggleComment(r.text, r.a, r.a, true).text).toBe(t);
  });
  it("indents, moves and duplicates lines", () => {
    expect(indentLines("a\nb\nc", 0, 3, false).text).toBe("  a\n  b\nc");
    expect(indentLines("  a\n b", 0, 6, true).text).toBe("a\nb");
    expect(moveLines("a\nb\nc", 0, 0, true)!.text).toBe("b\na\nc");
    expect(moveLines("a\nb\nc", 4, 4, false)!.text).toBe("a\nc\nb");
    expect(moveLines("a\nb", 0, 0, false)).toBeNull();
    expect(duplicateLines("a\nb", 2, 2).text).toBe("a\nb\nb");
  });
  it("comments are left out of what is read, not inside code", () => {
    const t = "one\n<!-- [[Drive]] -->\ntwo <!-- x --> three\n`<!-- kept -->`";
    const code = (i: number) => i >= t.indexOf("`");
    expect(stripMdComments(t, code)).toBe("one\ntwo  three\n`<!-- kept -->`");
  });
});
