/* RE4 (owner, 2026-11-23: "Ctrl+Z in the report's editing; a comment with Ctrl+/ and so on"): the report editor's own
   undo history and its line keys. The browser's undo in a textarea goes one letter at a time and forgets whatever the
   app put in (a plot from the library, bold, a paste of a picture) - so the editor keeps its own: a step per pause in
   typing or per change made at once, each with where the caret was. Pure functions, tested in editText.test.ts. */

export interface Snap { text: string; a: number; b: number }
export interface History { past: Snap[]; future: Snap[]; at: number; kind: string }

const MAX = 300;
const PAUSE = 800;            // ms of no typing that starts a new step

export const newHistory = (): History => ({ past: [], future: [], at: 0, kind: "" });

/** Before a change: keep the state it changes from - unless it continues the same run of typing. */
export function record(h: History, before: Snap, kind: "type" | "delete" | "put", now = Date.now()): History {
  const last = h.past[h.past.length - 1];
  const joins = kind !== "put" && kind === h.kind && now - h.at < PAUSE && !!last;
  if (joins) return { ...h, at: now, future: [] };
  if (last && last.text === before.text) return { ...h, at: now, kind, future: [] };
  return { past: [...h.past, before].slice(-MAX), future: [], at: now, kind };
}

export function undo(h: History, cur: Snap): [History, Snap] | null {
  const prev = h.past[h.past.length - 1];
  if (!prev) return null;
  return [{ past: h.past.slice(0, -1), future: [cur, ...h.future], at: 0, kind: "" }, prev];
}

export function redo(h: History, cur: Snap): [History, Snap] | null {
  const next = h.future[0];
  if (!next) return null;
  return [{ past: [...h.past, cur], future: h.future.slice(1), at: 0, kind: "" }, next];
}

/** The whole lines the selection touches: [start of the first, end of the last]. */
function lineSpan(text: string, a: number, b: number): [number, number] {
  const s = text.lastIndexOf("\n", a - 1) + 1;
  // a selection that ends at the start of a line does not take that line
  const bb = b > a && text[b - 1] === "\n" ? b - 1 : b;
  const e = text.indexOf("\n", bb);
  return [s, e < 0 ? text.length : e];
}

const MD_OPEN = "<!-- ", MD_CLOSE = " -->";
const mdIs = (l: string) => /^\s*<!--.*-->\s*$/.test(l);
const mdOff = (l: string) => l.replace(/^(\s*)<!--\s?/, "$1").replace(/\s?-->\s*$/, "");
const texIs = (l: string) => /^\s*%/.test(l);
const texOff = (l: string) => l.replace(/^(\s*)%\s?/, "$1");

/** Ctrl+/: the selected lines made comments (Markdown <!-- -->, LaTeX %) - or, when they all are, made text again.
 *  Empty lines stay as they are. The selection keeps covering the same lines. */
export function toggleComment(text: string, a: number, b: number, latex: boolean): Snap {
  const [s, e] = lineSpan(text, a, b);
  const lines = text.slice(s, e).split("\n");
  const full = lines.filter((l) => l.trim());
  const isC = latex ? texIs : mdIs;
  const off = full.length > 0 && full.every(isC);
  const out = lines.map((l) => {
    if (!l.trim()) return l;
    if (off) return latex ? texOff(l) : mdOff(l);
    const ind = /^\s*/.exec(l)![0];
    return latex ? `${ind}% ${l.slice(ind.length)}` : `${ind}${MD_OPEN}${l.slice(ind.length)}${MD_CLOSE}`;
  }).join("\n");
  const next = text.slice(0, s) + out + text.slice(e);
  if (a === b) {                 // a caret: it stays in its place in the line's text
    const shift = off ? -(text.slice(s, e).length - out.length) : (latex ? 2 : MD_OPEN.length);
    const p = Math.max(s, Math.min(s + out.length, a + (lines[0].trim() ? shift : 0)));
    return { text: next, a: p, b: p };
  }
  return { text: next, a: s, b: s + out.length };
}

/** Tab / Shift+Tab on several lines: indent them by two spaces, or take up to two away. */
export function indentLines(text: string, a: number, b: number, out: boolean): Snap {
  const [s, e] = lineSpan(text, a, b);
  const lines = text.slice(s, e).split("\n");
  const res = lines.map((l) => (out ? l.replace(/^ {1,2}|^\t/, "") : "  " + l)).join("\n");
  return { text: text.slice(0, s) + res + text.slice(e), a: s, b: s + res.length };
}

/** Alt+↑ / Alt+↓: the selected lines move up or down one line. */
export function moveLines(text: string, a: number, b: number, down: boolean): Snap | null {
  const [s, e] = lineSpan(text, a, b);
  if (down ? e >= text.length : s === 0) return null;
  const block = text.slice(s, e);
  if (down) {
    const ne = text.indexOf("\n", e + 1);
    const end = ne < 0 ? text.length : ne;
    const below = text.slice(e + 1, end);
    const next = text.slice(0, s) + below + "\n" + block + text.slice(end);
    const d = below.length + 1;
    return { text: next, a: a + d, b: b + d };
  }
  const ps = text.lastIndexOf("\n", s - 2) + 1;
  const above = text.slice(ps, s - 1);
  const next = text.slice(0, ps) + block + "\n" + above + text.slice(e);
  const d = above.length + 1;
  return { text: next, a: a - d, b: b - d };
}

/** Ctrl+Shift+D: the selected lines once more, under them. */
export function duplicateLines(text: string, a: number, b: number): Snap {
  const [s, e] = lineSpan(text, a, b);
  const block = text.slice(s, e);
  const d = block.length + 1;
  return { text: text.slice(0, e) + "\n" + block + text.slice(e), a: a + d, b: b + d };
}

/** Markdown comments (<!-- ... -->, one line or many) out of the text before it is read - not inside code. */
export function stripMdComments(text: string, inCode: (i: number) => boolean): string {
  // a comment on lines of its own takes its lines with it (a paragraph around it stays one paragraph)
  return text.replace(/^[ \t]*<!--[\s\S]*?-->[ \t]*(\n|$)|<!--[\s\S]*?-->/gm, (m, _nl, at: number) => (inCode(at) ? m : ""));
}
