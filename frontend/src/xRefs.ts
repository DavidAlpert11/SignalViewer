/* Q89: other signals in an expression of x - "sin(x) + Speed". A name is a signal of the SAME file
   as x (for a group: each signal's own file), so one expression fits every file. It is stored with
   braces - "sin(x) + {Speed}" - which the server reads in that file (as read, before any change)
   and which stays right when the change is copied or linked to another file.
   Q90: {file:Name} - that one file's signal, for every signal changed (the file's name as the file
   list shows it, or its file name). Stored by the file's id - {@<id>:Name}, which a saved session
   and Replace the input files keep - and shown again by its name (displayX). */
import type { RunInfo } from "./api";
import { fileLabel } from "./store";
import { FUNC_NAMES } from "./formulaHelp";
import { fuzzySort } from "./fuzzy";

// a quoted text (param("...")) | {any text} | a bare name (letters incl. Hebrew, digits, _ . [ ])
const TOKEN = /"[^"]*"|\{([^}]+)\}|([A-Za-z_\u0590-\u05FF][\w.\u0590-\u05FF[\]]*)/g;
const BASE = new Set(["x", "t", "pi", "e"]);
const BARE = /^[A-Za-z_\u0590-\u05FF][\w\u0590-\u05FF]*$/;      // a name that needs no braces

export interface XRefs { text: string; names: string[]; error?: string }
type Lang = (k: string, v?: Record<string, string | number>) => string;

/** Check `textIn` for the files `homes` (each target's own file) and write its signal names as
 *  {Name}. `names`: the other signals it reads (empty: an expression of x alone). */
export function canonX(textIn: string, homes: string[], runs: RunInfo[], lang: Lang): XRefs {
  const files = homes.map((h) => runs.find((r) => r.id === h)).filter((r): r is RunInfo => !!r);
  const names: string[] = [];
  let error: string | undefined;
  const text = textIn.replace(TOKEN, (whole, braced: string | undefined, bare: string | undefined, offset: number) => {
    if (error || whole.startsWith('"')) return whole;
    if (bare) {
      if (/[\d.]/.test(textIn[offset - 1] ?? "")) return whole;                 // 1e5, 2.5e-3
      const after = textIn.slice(offset + whole.length).trimStart();
      if (after.startsWith("(") && (FUNC_NAMES.includes(bare) || bare === "param")) return whole;
      if (BASE.has(bare)) return whole;
    }
    const want = (braced ?? bare ?? "").trim();
    // {file:Name} - that one file (unless the whole text is itself a name of the targets' files)
    if (braced && want.includes(":") && !files.some((r) => r.signals.some((x) => x.name === want))) {
      const i = want.indexOf(":");
      const label = want.slice(0, i).trim(), sname = want.slice(i + 1).trim();
      const file = label.startsWith("@") ? runs.find((r) => r.id === label.slice(1))
        : runs.find((r) => r.format !== "derived" && (fileLabel(runs, r.id) === label || r.name === label));
      if (!file) { error = lang("fxXNoSuchFile", { name: label }); return whole; }
      const hit = file.signals.find((x) => x.name === sname) ?? file.signals.find((x) => x.name.toLowerCase() === sname.toLowerCase());
      if (!hit) { error = lang("fxXUnknown", { name: sname, file: file.name }); return whole; }
      const tok = `@${file.id}:${hit.name}`;
      if (!names.includes(tok)) names.push(tok);
      return `{${tok}}`;
    }
    if (!files.length) { error = lang("fxXNoFile", { name: want }); return whole; }
    // the exact name, or the one name that differs only in case - the same in every file
    const pick = (r: RunInfo) => r.signals.find((s) => s.name === want)?.name
      ?? (() => { const ci = r.signals.filter((s) => s.name.toLowerCase() === want.toLowerCase()); return ci.length === 1 ? ci[0].name : undefined; })();
    const found = files.map(pick);
    const name = found.find(Boolean);
    if (!name) {
      if (bare && FUNC_NAMES.includes(bare)) { error = lang("fxNeedsParen", { name: bare }); return whole; }
      const guess = fuzzySort([...files[0].signals.map((s) => s.name), ...FUNC_NAMES], (x) => x, want)[0];
      // a name with spaces or brackets is only read whole in braces: say so with the fix itself
      const fix = guess && !FUNC_NAMES.includes(guess) && !BARE.test(guess) ? `{${guess}}` : guess;
      error = lang("fxXUnknown", { name: want, file: files[0].name }) + (fix ? " " + lang("fxDidYouMean", { name: fix }) : "");
      return whole;
    }
    const lacking = files.filter((_r, i) => found[i] !== name);
    if (lacking.length) { error = lang("fxXMissingIn", { name, files: lacking.map((r) => r.name).join(", ") }); return whole; }
    if (!names.includes(name)) names.push(name);
    return `{${name}}`;
  });
  return { text, names, error };
}

/** For the expression box: the signals the targets' files have in common, to suggest while typing. */
export function sharedSignalOptions(homes: string[], runs: RunInfo[]) {
  const files = homes.map((h) => runs.find((r) => r.id === h)).filter((r): r is RunInfo => !!r);
  if (!files.length) return [];
  const others = files.slice(1).map((r) => new Set(r.signals.map((s) => s.name)));
  return files[0].signals.filter((s) => others.every((o) => o.has(s.name)))
    .map((s) => ({ label: s.name, sub: files.length > 1 ? `${files.length} files` : files[0].name,
      insert: BARE.test(s.name) && !BASE.has(s.name) ? s.name : `{${s.name}}` }))
    // Q90: and every open file's signals by file - {fb.csv:Speed}, that file's for all of them
    .concat(runs.filter((r) => r.format !== "derived" && runs.filter((x) => x.format !== "derived").length > 1)
      .flatMap((r) => r.signals.map((s) => ({ label: `${fileLabel(runs, r.id)}:${s.name}`, sub: r.name, insert: `{${fileLabel(runs, r.id)}:${s.name}}` }))));
}

/** Q90: an expression as stored -> as shown: {@<id>:Name} becomes {file:Name}. */
export function displayX(expr: string, runs: RunInfo[]): string {
  return expr.replace(/\{@([^:{}]+):([^{}]+)\}/g, (whole, id: string, name: string) =>
    (runs.some((r) => r.id === id) ? `{${fileLabel(runs, id)}:${name}}` : whole));
}
