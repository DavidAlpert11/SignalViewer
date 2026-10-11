import type { RunInfo } from "./api";
import { fileLabel, useApp } from "./store";
import { fuzzySort } from "./fuzzy";

import { FUNC_NAMES } from "./formulaHelp";

/** Functions understood by the server (backend/svcore/formula.py), from the shared list. */
export const FORMULA_FUNCS = FUNC_NAMES;
const CONSTS = new Set(["t", "pi", "e"]);

// {any text}  or  a bare name (letters incl. Hebrew, digits, _ . [ ])
const TOKEN = /\{([^}]+)\}|([A-Za-z_\u0590-\u05FF][\w.\u0590-\u05FF[\]]*)/g;

export interface Resolved { expr: string; sources: string[]; error?: string }

/** Turn "2*Speed - {run_b.csv:RPM}/95" into "2*v0 - v1/95" + [id of Speed, id of RPM]. */
const PARAM = /param\(\s*"([^"]*)"\s*\)/g;

/** param("NAME") / param("file:NAME") -> the parameter's value from an open flight log (its value at
 *  the end of the log). prefer: files to look in first (e.g. the signals being transformed). */
export function substituteParams(text: string, runs: RunInfo[], lang: (k: string, v?: Record<string, string | number>) => string,
  prefer: string[] = []): { text: string; error?: string } {
  if (!text.includes("param(")) return { text };
  const logs = useApp.getState().logs;
  let error: string | undefined;
  const out = text.replace(PARAM, (whole, raw: string) => {
    if (error) return whole;
    let name = raw.trim(), files = runs.filter((r) => logs[r.id]);
    const i = name.lastIndexOf(":");
    if (i > 0) {
      const f = name.slice(0, i).trim();
      files = files.filter((r) => fileLabel(runs, r.id) === f || r.name === f);
      name = name.slice(i + 1).trim();
      if (!files.length) { error = lang("fxParamNoFile", { name: f }); return whole; }
    }
    if (!files.length) { error = lang("fxParamNoLog"); return whole; }
    const has = files.filter((r) => logs[r.id].params.some((p) => p.name === name));
    const pick = has.filter((r) => prefer.includes(r.id));
    const cands = pick.length ? pick : has;
    if (!cands.length) {
      const all = files.flatMap((r) => logs[r.id].params.map((p) => p.name));
      const guess = fuzzySort(Array.from(new Set(all)), (x) => x, name)[0];
      error = lang("fxParamUnknown", { name }) + (guess ? " " + lang("fxDidYouMean", { name: `param("${guess}")` }) : "");
      return whole;
    }
    const vals = cands.map((r) => logs[r.id].params.find((p) => p.name === name)!.value);
    if (new Set(vals).size > 1) {
      error = lang("fxParamAmbiguous", { name, example: `param("${fileLabel(runs, cands[1].id)}:${name}")` });
      return whole;
    }
    return `(${vals[0]})`;
  });
  return { text: out, error };
}

export function resolveFormula(textIn: string, runs: RunInfo[], lang: (k: string, v?: Record<string, string | number>) => string): Resolved {
  const sub = substituteParams(textIn, runs, lang);
  if (sub.error) return { expr: textIn, sources: [], error: sub.error };
  const text = sub.text;
  const sources: string[] = [];
  const all = runs.flatMap((r) => r.signals.map((s) => ({ s, r })));
  let error: string | undefined;
  const out = text.replace(TOKEN, (whole, braced: string | undefined, bare: string | undefined, offset: number) => {
    if (error) return whole;
    let name = (braced ?? bare ?? "").trim();
    if (bare) {
      const after = text.slice(offset + whole.length).trimStart();
      if (after.startsWith("(") && FORMULA_FUNCS.includes(bare)) return whole;     // a function call
      if (CONSTS.has(bare)) return whole;
    }
    let candidates = all;
    if (braced && name.includes(":")) {                     // {file:signal}
      const i = name.indexOf(":");
      const file = name.slice(0, i).trim(), sig = name.slice(i + 1).trim();
      const inFile = all.filter(({ r }) => r.format !== "derived" && (fileLabel(runs, r.id) === file || r.name === file));
      if (inFile.length) { candidates = inFile; name = sig; }
    }
    let hits = candidates.filter(({ s }) => s.name === name);
    if (!hits.length) hits = candidates.filter(({ s }) => s.name.toLowerCase() === name.toLowerCase());
    if (!hits.length) {
      const guess = fuzzySort(all, ({ s }) => s.name, name)[0];
      error = lang("fxUnknown", { name }) + (guess ? " " + lang("fxDidYouMean", { name: guess.s.name }) : "");
      return whole;
    }
    if (hits.length > 1) {
      const files = hits.map(({ r }) => (r.format === "derived" ? "ƒ" : fileLabel(runs, r.id)));
      error = lang("fxAmbiguous", { name, example: `{${files[1]}:${name}}`, files: files.join(", ") });
      return whole;
    }
    const id = hits[0].s.id;
    let k = sources.indexOf(id);
    if (k < 0) { sources.push(id); k = sources.length - 1; }
    return `v${k}`;
  });
  if (!error && !sources.length && text.trim()) error = lang("fxNoSignal");
  return { expr: out, sources, error };
}

/** Word being typed at the caret (for suggestions). */
export function wordAt(text: string, caret: number): { start: number; word: string } {
  let i = caret;
  while (i > 0 && /[\w.\u0590-\u05FF[\]{:]/.test(text[i - 1])) i--;
  return { start: i, word: text.slice(i, caret) };
}

/** How a signal is written in a formula: bare when that is unambiguous and simple, else {file:name}. */
export function refFor(runs: RunInfo[], id: string): string {
  const [rid, ...rest] = id.split("/");
  const name = rest.join("/");
  const same = runs.flatMap((r) => r.signals).filter((s) => s.name === name).length;
  const simple = /^[A-Za-z_\u0590-\u05FF][\w.\u0590-\u05FF[\]]*$/.test(name) && !FORMULA_FUNCS.includes(name) && !CONSTS.has(name);
  if (same <= 1) return simple ? name : `{${name}}`;
  const run = runs.find((r) => r.id === rid);
  return `{${run && run.format !== "derived" ? fileLabel(runs, rid) : "ƒ"}:${name}}`;
}
