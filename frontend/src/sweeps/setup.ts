/* C6: a study's Set up (plan §4.3) - what varies (parameters: range, step, scale, how many in the start
   grid; constraints between them), the scenarios (per system: columns and their values), the outputs and the
   goal, and how one run is started (this PC / a farm launcher). It is the study file's own blocks - `shared`,
   `search`, `start`, a table's roles / objective, `launcher` - edited in place, so the engine (the loop, the
   next runs) reads exactly what is shown. Pure functions on a Study: Vitest checks them. */
import type { SearchParam, Study, StudyTable } from "./studyTypes";

export type Scale = "linear" | "log" | "values";
export interface ParamRow { name: string; min: number | null; max: number | null; step: number | null; scale: Scale; values: number[]; count: number }
export interface ScenarioRow { name: string; values: (number | string)[] }

export const DEFAULT_COUNT = 4;
const RESULTS = "results/{{table}}/{{run_id}}.csv";
const PARAMS_NAME = "params/{{table}}/{{run_id}}.json";

/** A new study of one system, nothing run yet (*Start from nothing*). */
export function newSetupStudy(name = ""): Study {
  return {
    version: 1, name, tables: [{ id: "T1", name: "", paths: ["next/round_*/collected_T1.csv"], roles: {}, constraints: [], objective: { expr: "", sense: "min" }, aggregate: "worst" }],
    shared: [], combine: { mode: "auto" }, search: { params: {}, constraints: [] }, next: { batch: 20 },
    start: { grid: {}, scenarios: { T1: {} } },
    launcher: { params_name: PARAMS_NAME, submit: [], submit_mode: "run", local_workers: 2, results: { glob: RESULTS, format: "csv_row" } },
  };
}

/** The parameters the study varies: its shared ones, else its search space's (one system). */
export const paramNames = (s: Study): string[] => (s.shared?.length ? s.shared.map((p) => p.name) : Object.keys(s.search?.params ?? {}));

const countOf = (s: Study, name: string): number => {
  const g = s.start?.grid;
  const n = typeof g === "number" ? g : g?.[name];
  return Math.max(1, Math.round(n ?? DEFAULT_COUNT));
};

export function params(s: Study): ParamRow[] {
  return paramNames(s).map((name) => {
    const p: SearchParam = s.search?.params?.[name] ?? {};
    const values = p.values ?? [];
    return { name, min: p.min ?? null, max: p.max ?? null, step: p.step ?? null, scale: values.length ? "values" : p.log ? "log" : "linear",
      values, count: values.length ? Math.min(countOf(s, name), values.length) : countOf(s, name) };
  });
}

function setGrid(s: Study, name: string, count: number | null): void {
  const g = s.start?.grid;
  const grid: Record<string, number> = typeof g === "number" ? Object.fromEntries(paramNames(s).map((n) => [n, g])) : { ...(g ?? {}) };
  if (count === null) delete grid[name]; else grid[name] = count;
  s.start = { ...(s.start ?? {}), grid };
}

/** A parameter written (`old`: its name before; "" for a new one). The study's own Set up: shared, search, start grid. */
export function setParam(s: Study, old: string, r: ParamRow): Study {
  const name = r.name.trim();
  if (!name) return s;
  const sp: SearchParam = { ...(s.search?.params?.[old] ?? {}) };
  if (r.scale === "values") { sp.values = r.values; delete sp.min; delete sp.max; delete sp.step; sp.log = false; }
  else { sp.min = r.min; sp.max = r.max; sp.step = r.step; sp.log = r.scale === "log"; delete sp.values; }
  const search = { ...(s.search ?? { params: {} }), params: { ...(s.search?.params ?? {}) } };
  const names = paramNames(s);
  if (old && old !== name) {
    delete search.params[old];
    setGrid(s, old, null);
  }
  search.params[name] = sp;
  s.search = search;
  const list = old && names.includes(old) ? names.map((n) => (n === old ? name : n)) : names.includes(name) ? names : [...names, name];
  s.shared = list.map((n) => ({ ...(s.shared?.find((p) => p.name === n) ?? {}), name: n }));
  setGrid(s, name, r.count);
  return withTemplate(s);
}

export function removeParam(s: Study, name: string): Study {
  const search = { ...(s.search ?? { params: {} }), params: { ...(s.search?.params ?? {}) } };
  delete search.params[name];
  s.search = search;
  s.shared = (s.shared ?? []).filter((p) => p.name !== name);
  setGrid(s, name, null);
  return withTemplate(s);
}

/** The table the Set up's scenarios and goal belong to (the study's first system). */
export const firstTable = (s: Study): StudyTable | undefined => s.tables[0];

export function scenarios(s: Study, table = firstTable(s)?.id ?? ""): ScenarioRow[] {
  // the demo keeps its start scenarios in its own block (the engine reads start's first, then the demo's)
  const sc = s.start?.scenarios?.[table] ?? s.demo?.scenarios?.[table] ?? {};
  return Object.entries(sc).map(([name, values]) => ({ name, values }));
}

const isNum = (x: string) => x.trim() !== "" && Number.isFinite(+x);

/** "0, 5, 10" -> [0, 5, 10]; text stays text. MATLAB-style ranges (owner, 2026-11-16): "1, 2, 8:0.5:10" ->
 *  1, 2, 8, 8.5 … 10 (start:step:end; start:end = step 1) - the same as the sweep wrapper's grid files. */
export function parseValues(text: string): (number | string)[] {
  const out: (number | string)[] = [];
  for (const x of text.split(/[,;]/).map((v) => v.trim()).filter(Boolean)) {
    const r = x.split(":");
    if ((r.length === 2 || r.length === 3) && r.every(isNum)) {
      const [a, st, b] = r.length === 2 ? [+r[0], 1, +r[1]] : [+r[0], +r[1], +r[2]];
      if (st === 0 || (b - a) / st < 0) { out.push(x); continue; }        // shown back as it was: the user sees it is wrong
      const n = Math.floor((b - a) / st + 1e-9) + 1;
      for (let k = 0; k < Math.min(n, 10000); k++) out.push(+(a + k * st).toPrecision(12));
    } else out.push(isNum(x) ? +x : x);
  }
  return out;
}

// ------------------------------------------------------------------ the inputs as text ("name: values" lines)

/** A parameter as one text line: a list of values, or its range (start:step:end; log a:b; start:end = no step). */
export function paramLine(p: ParamRow): string {
  const v = p.scale === "values" ? p.values.join(", ")
    : p.min === null || p.max === null ? "" : p.scale === "log" ? `log ${p.min}:${p.max}`
    : p.step ? `${p.min}:${p.step}:${p.max}` : `${p.min}:${p.max}`;
  return `${p.name}: ${v}`;
}
export const paramsText = (s: Study): string => params(s).map(paramLine).join("\n");
export const scenariosText = (s: Study): string => scenarios(s).map((x) => `${x.name}: ${x.values.join(", ")}`).join("\n");

function lines(text: string): [string, string][] {
  return text.split("\n").map((l) => l.split("#")[0].trim()).filter(Boolean).map((l) => {
    const i = l.indexOf(":");
    return (i > 0 ? [l.slice(0, i).trim(), l.slice(i + 1).trim()] : [l, ""]) as [string, string];
  }).filter(([n]) => !!n);
}

/** The parameters from "name: values" lines: a line not changed keeps its row (its start count, its scale); a range
 *  alone is the search range (with its step when it has one), anything else the list of values. Names gone are removed. */
export function applyParamsText(s: Study, text: string): Study {
  const was = new Map(params(s).map((p) => [p.name, p]));
  const keep = new Set<string>();
  for (const [name, vals] of lines(text)) {
    keep.add(name);
    const old = was.get(name);
    if (old && paramLine(old) === `${name}: ${vals}`) continue;
    const count = old?.count ?? DEFAULT_COUNT;
    const log = /^log\s+/i.test(vals);
    const r = vals.replace(/^log\s+/i, "").split(":");
    let row: ParamRow;
    if (!vals.includes(",") && (r.length === 2 || r.length === 3) && r.every(isNum))
      row = { name, min: +r[0], max: +r[r.length - 1], step: r.length === 3 && !log ? +r[1] : null, scale: log ? "log" : "linear", values: [], count };
    else row = { name, min: null, max: null, step: null, scale: "values", values: parseValues(vals).filter((x): x is number => typeof x === "number"), count };
    s = setParam(s, old ? name : "", row);
  }
  for (const n of was.keys()) if (!keep.has(n)) s = removeParam(s, n);
  return s;
}

/** The scenarios from "name: values" lines (text values too); names gone are removed. */
export function applyScenariosText(s: Study, text: string): Study {
  const was = new Set(scenarios(s).map((x) => x.name));
  const keep = new Set<string>();
  for (const [name, vals] of lines(text)) { keep.add(name); s = setScenario(s, was.has(name) ? name : "", { name, values: parseValues(vals) }); }
  for (const n of was) if (!keep.has(n)) s = removeScenario(s, n);
  return s;
}

export function setScenario(s: Study, old: string, r: ScenarioRow, table = firstTable(s)?.id ?? ""): Study {
  const name = r.name.trim();
  if (!name || !table) return s;
  const all = { ...(s.start?.scenarios ?? {}) };
  const was = Object.entries(all[table] ?? s.demo?.scenarios?.[table] ?? {});
  const key = old && was.some(([k]) => k === old) ? old : name;
  const sc = was.some(([k]) => k === key) ? was.filter(([k]) => k === key || k !== name).map(([k, v]): [string, (number | string)[]] => (k === key ? [name, r.values] : [k, v]))
    : [...was, [name, r.values] as [string, (number | string)[]]];
  all[table] = Object.fromEntries(sc);
  s.start = { ...(s.start ?? {}), scenarios: all };
  s.tables = s.tables.map((t) => {
    if (t.id !== table) return t;
    const roles = { ...(t.roles ?? {}) };
    if (old && old !== name) delete roles[old];
    roles[name] = "scenario";
    return { ...t, roles };
  });
  return withTemplate(s);
}

export function removeScenario(s: Study, name: string, table = firstTable(s)?.id ?? ""): Study {
  const all = { ...(s.start?.scenarios ?? {}) };
  all[table] = Object.fromEntries(Object.entries(all[table] ?? {}).filter(([k]) => k !== name));
  s.start = { ...(s.start ?? {}), scenarios: all };
  s.tables = s.tables.map((t) => (t.id === table ? { ...t, roles: Object.fromEntries(Object.entries(t.roles ?? {}).filter(([k]) => k !== name)) } : t));
  return withTemplate(s);
}

/** The outputs of the first system (what the program writes) and what ranks the sets. */
export const outputs = (s: Study): string[] => Object.entries(firstTable(s)?.roles ?? {}).filter(([, r]) => r === "output").map(([c]) => c);

export function setOutputs(s: Study, names: string[]): Study {
  const t = firstTable(s);
  if (!t) return s;
  const roles = Object.fromEntries(Object.entries(t.roles ?? {}).filter(([, r]) => r !== "output"));
  for (const n of names) roles[n] = "output";
  s.tables = [{ ...t, roles }, ...s.tables.slice(1)];
  return s;
}

export function setGoal(s: Study, expr: string, sense: "min" | "max", constraints: string[]): Study {
  const t = firstTable(s);
  if (!t) return s;
  s.tables = [{ ...t, objective: { expr, sense }, constraints }, ...s.tables.slice(1)];
  return s;
}

// ------------------------------------------------------------------ how to run

/** A command line as its arguments (no shell): spaces split, quotes keep a part whole. */
export function splitCommand(text: string): string[] {
  const out: string[] = [];
  for (const m of text.matchAll(/"([^"]*)"|'([^']*)'|(\S+)/g)) out.push(m[1] ?? m[2] ?? m[3]);
  return out;
}
export const joinCommand = (args: string[]): string => args.map((a) => (/\s/.test(a) ? `"${a}"` : a)).join(" ");

/** pc: a pool here runs the command per run; wrapper: the command is a sweep wrapper here that runs the round's
 *  runs itself (`run_as`); farm: the farm's launcher gets the round. */
export type RunWhere = "pc" | "wrapper" | "farm";
export const runWhere = (s: Study): RunWhere => (s.launcher?.local_workers ? "pc" : s.launcher?.run_as === "wrapper" ? "wrapper" : "farm");
/** The wrapper's command when the user has none yet: the sweep wrapper beside the study, run by this program. */
export const WRAPPER_COMMAND = "{{study_cli}} wrap {{study_dir}}/sweep_wrapper.py --list {{params_files}} --workers 2";

export function setRun(s: Study, p: { where?: RunWhere; command?: string; workers?: number }): Study {
  const l = { params_name: PARAMS_NAME, results: { glob: RESULTS, format: "csv_row" as const }, ...(s.launcher ?? {}) };
  if (p.command !== undefined) l.submit = splitCommand(p.command);
  const where = p.where ?? runWhere(s);
  if (where === "pc") {
    if (p.command === undefined && l.run_as === "wrapper") l.submit = [];   // the wrapper's command runs a round, not one run
    l.local_workers = p.workers ?? l.local_workers ?? 2; l.submit_mode = "run"; delete l.run_as;
  }
  else if (where === "wrapper") {
    if (!l.submit?.some((a) => a.includes("{{params_files}}"))) l.submit = splitCommand(WRAPPER_COMMAND);
    l.local_workers = null; l.submit_mode = "round"; l.run_as = "wrapper";
  } else { l.local_workers = null; delete l.run_as; l.submit_mode = l.submit?.some((a) => a.includes("{{params_files}}")) ? "round" : "run"; }
  s.launcher = l;
  return withTemplate(s);
}

/** The parameters file one run gets (JSON), made from the Set up while the user has not given their own: every
 *  parameter and scenario, the run's id and where to write its result row. */
export function autoTemplate(s: Study): string {
  const t = firstTable(s)?.id ?? "";
  const scen = s.start?.scenarios?.[t] ?? {};
  const fields = [`"run_id": "{{run_id}}"`, `"table": "{{table}}"`,
    ...paramNames(s).map((n) => `"${n}": {{${n}}}`),
    ...Object.entries(scen).map(([n, vs]) => (vs.every((v) => typeof v === "number") ? `"${n}": {{${n}}}` : `"${n}": "{{${n}}}"`)),
    `"out": "{{study_dir}}/${RESULTS}"`];
  return `{${fields.join(", ")}}\n`;
}

/** The generated template follows the Set up (`template_auto`); one the user wrote is left alone. */
export function withTemplate(s: Study): Study {
  const l = s.launcher;
  if (!l) return s;
  const auto = l.template_auto === true || (!l.params_template && !l.params_template_file);
  if (auto) s.launcher = { ...l, params_template: autoTemplate(s), template_auto: true };
  return s;
}

// ------------------------------------------------------------------ round 1: what it will run, what is missing

export type Missing = "params" | "range" | "output" | "goal" | "command";
export interface Readiness {
  /** values per parameter in the start grid, and their product */
  counts: number[]; sets: number;
  /** scenario combinations, and runs = sets x combinations */
  combos: number; runs: number;
  /** the full fine grid (values per parameter from range / step or the list), null when a range has no step */
  full: number[] | null; fullRuns: number | null;
  missing: Missing[];
}

const fineCount = (p: ParamRow): number | null =>
  p.scale === "values" ? p.values.length : p.min !== null && p.max !== null && p.step ? Math.floor((p.max - p.min) / p.step + 1e-9) + 1 : null;

export function readiness(s: Study): Readiness {
  const ps = params(s);
  const counts = ps.map((p) => p.count);
  const sets = ps.length ? counts.reduce((a, b) => a * b, 1) : 0;
  const combos = s.tables.reduce((acc, t) => acc + Object.values(s.start?.scenarios?.[t.id] ?? {}).reduce((a, v) => a * Math.max(1, v.length), 1), 0) || 1;
  const fine = ps.map(fineCount);
  const full = fine.every((x): x is number => x !== null) && ps.length ? fine : null;
  const missing: Missing[] = [];
  if (!ps.length) missing.push("params");
  else if (ps.some((p) => p.scale !== "values" && (p.min === null || p.max === null || !(p.max > p.min)))) missing.push("range");
  if (!outputs(s).length) missing.push("output");
  if (!s.tables.some((t) => t.objective?.expr)) missing.push("goal");
  if (!s.launcher?.submit?.length) missing.push("command");
  return { counts, sets, combos, runs: sets * combos, full, fullRuns: full ? full.reduce((a, b) => a * b, 1) * combos : null, missing };
}

/** Which of Set up's four parts are filled (what varies, the scenarios, outputs and goal, how to run) - SetupView's
 *  ✓ and the navigator's count (C7). `fromTable`: the scenarios are an open table's columns (I have results). */
export function setupDone(s: Study, fromTable: boolean): boolean[] {
  const r = readiness(s);
  return [params(s).length > 0 && !r.missing.includes("range"), scenarios(s).length > 0 || fromTable,
    !r.missing.includes("output") && !r.missing.includes("goal"), !r.missing.includes("command")];
}

// ------------------------------------------------------------------ I have results: the set-up from a table

/** What /api/sweeps/setup/from-table guessed from a table (C2). */
export interface FromTable {
  rows: number;
  params: { name: string; kind: "number" | "text"; distinct: number; values: (number | string)[] | null; min?: number; max?: number; integer?: boolean; log?: boolean }[];
  scenarios: { name: string; kind: "number" | "text"; distinct: number; values: (number | string)[] | null }[];
  outputs: string[]; other: string[];
  shared: { name: string }[]; search: { params: Record<string, SearchParam> }; roles: Record<string, "shared" | "scenario" | "output" | "ignore">;
}

/** A study of one table that is there already: its parameters' ranges, its scenario columns and outputs from the
 *  columns; the goal as the table's Goal step holds it (`goal`, C3). No start grid and no command yet: the study
 *  keeps being saved as the table's own `.svsweep` until something like that is added. */
export function setupFromResults(g: FromTable, path: string, name: string, goal: Pick<StudyTable, "constraints" | "objective" | "aggregate">): Study {
  const s = newSetupStudy(name);
  delete s.start;
  s.tables = [{ id: "T1", name, paths: [path], roles: { ...g.roles }, ...goal }];
  s.shared = g.shared;
  s.search = { params: structuredClone(g.search.params), constraints: [] };
  s.launcher = { ...s.launcher, submit: [], template_auto: true, params_template: "" };
  return s;
}
