/* Q89: other signals in an expression of x - "sin(x) + Speed". A name is a signal of the SAME file
   as x (for a group: each signal's own file), so one expression fits every file. It is stored with
   braces - "sin(x) + {Speed}" - which the server reads in that file (as read, before any change)
   and which stays right when the change is copied or linked to another file. */
import type { RunInfo } from "./api";
import { FUNC_NAMES } from "./formulaHelp";
import { fuzzySort } from "./fuzzy";

// a quoted text (param("...")) | {any text} | a bare name (letters incl. Hebrew, digits, _ . [ ])
const TOKEN = /"[^"]*"|\{([^}]+)\}|([A-Za-z_\u0590-\u05FF][\w.\u0590-\u05FF[\]]*)/g;
const BASE = new Set(["x", "t", "pi", "e"]);

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
    if (!files.length) { error = lang("fxXNoFile", { name: want }); return whole; }
    // the exact name, or the one name that differs only in case - the same in every file
    const pick = (r: RunInfo) => r.signals.find((s) => s.name === want)?.name
      ?? (() => { const ci = r.signals.filter((s) => s.name.toLowerCase() === want.toLowerCase()); return ci.length === 1 ? ci[0].name : undefined; })();
    const found = files.map(pick);
    const name = found.find(Boolean);
    if (!name) {
      if (bare && FUNC_NAMES.includes(bare)) { error = lang("fxNeedsParen", { name: bare }); return whole; }
      const guess = fuzzySort([...files[0].signals.map((s) => s.name), ...FUNC_NAMES], (x) => x, want)[0];
      error = lang("fxXUnknown", { name: want, file: files[0].name }) + (guess ? " " + lang("fxDidYouMean", { name: guess }) : "");
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
      insert: /^[A-Za-z_\u0590-\u05FF][\w\u0590-\u05FF]*$/.test(s.name) && !BASE.has(s.name) ? s.name : `{${s.name}}` }));
}
