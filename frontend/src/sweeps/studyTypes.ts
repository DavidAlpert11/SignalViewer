/* W0 contract: the study file (.svstudy.json, docs/dev/study.schema.json, svcore/study.py) and the
   /api/sweeps/* response shapes (tests/fixtures/sweeps/*.json). Types only - the panel and
   its calls build on these. Unknown keys of a study are kept: a study is edited as a whole object and
   saved back, so fields this version does not know survive. */

export type Role = "shared" | "scenario" | "local" | "output" | "ignore";
export type Reason = "refine" | "boundary" | "gap" | "start";
export type RunState = "pending" | "submitted" | "done" | "failed" | "partly done";
type Extra = { [k: string]: unknown };
type Values = Record<string, number | string>;

export interface StudyTable extends Extra {
  id: string; name?: string; paths: string[];
  rename?: Record<string, string>; roles?: Record<string, Role>; drop?: Record<string, (number | string)[]>;
  constraints?: string[]; objective?: { expr: string; sense: "min" | "max" }; aggregate?: "worst" | "mean";
  sim_exe?: string; params_template?: string; params_template_file?: string;
}
export interface SearchParam extends Extra { min?: number | null; max?: number | null; step?: number | null; values?: number[] | null; integer?: boolean; log?: boolean }
export interface LauncherBlock extends Extra {
  params_template?: string; params_template_file?: string; params_name?: string;
  submit?: string[]; submit_mode?: "round" | "run"; sim_exe?: string;
  results?: { glob?: string; format?: "csv_row" | "csv_series" | "json" | "loader"; reduce?: Record<string, string>; json_keys?: Record<string, string>; converter?: string[] };
  status?: { failed_glob?: string; timeout_s?: number | null };
  local_workers?: number | null;
  /** "wrapper": the round's command is a sweep wrapper run on this PC in the background (sweep_wrapper.py) */
  run_as?: "wrapper";
}
export interface DemoBlock extends Extra { sleep_ms?: number; noise?: number; seed?: number; tolerance_pct?: number; max_rounds?: number; reference?: string; start_grid?: number; scenarios?: Record<string, Record<string, (number | string)[]>> }
export interface StudyProposal extends Extra { run_id: string; table: string; values: Values; reason: Reason; state: RunState }
export interface StudyRound extends Extra { round: number; date: string; folder: string; proposals: StudyProposal[] }
export interface Study extends Extra {
  version: 1; name?: string;
  tables: StudyTable[];
  shared?: { name: string; tolerance?: number }[];
  combine?: { mode: "auto" | "minworst" | "pareto"; weights?: Record<string, number> };
  search?: { params: Record<string, SearchParam>; constraints?: string[] };
  next?: { batch?: number; mix?: { refine: number; boundary: number; gap: number }; folder?: string; columns?: string[] | null; format?: "csv" | "xlsx" };
  launcher?: LauncherBlock; demo?: DemoBlock | null; history?: StudyRound[];
  /** C1: round 1 of a study with no runs yet - values per parameter (one count or per parameter) x each table's scenarios */
  start?: StartBlock | null;
  /** C5: what only the Sweeps area needs (each table as shown, the place last shown); the engine never reads it */
  workspace?: WorkspaceBlock | null;
}
export interface StartBlock extends Extra { grid?: number | Record<string, number>; scenarios?: Record<string, Record<string, (number | string)[]>> }
export interface WorkspaceBlock extends Extra {
  version: 1;
  /** each table of the area as its single-table file holds it (.svsweep's document) */
  sweeps: import("./state").SavedStudy[];
  active?: number;
  place?: { part: "setup" | "table" | "together"; table?: number };
}

/** The request of every /api/sweeps/* POST: a saved study, or the panel's study as it is now. */
export interface StudyReq { study_path?: string; study?: Study; folder?: string; write?: boolean }

// ------------------------------------------------------------------ W14 /api/sweeps/common
export interface TableResult {
  table: string; status: "pass" | "fail" | "not_run"; score: number | null;
  local: Values | null; worst: Values | null;
  failed: { scenario: Values | null; constraint: string; by: number | null } | null;
  runs: number[];                         // row indices in that table (to open the runs)
}
export interface CommonRow { values: Values; feasible: boolean; rank: number | null; pareto: boolean; score: number | null; tables: TableResult[] }
export interface CommonResult {
  study: string; mode: "minworst" | "pareto"; shared: string[];
  tables: { id: string; name: string; files: string[]; rows: number; objective: string; sense: "min" | "max" }[];
  mapping: { table: string; column: string; name: string; score: number; confirmed: boolean }[];
  rows: CommonRow[]; counts: { values: number; feasible: number }; seconds: number;
}

// ------------------------------------------------------------------ W15 /api/sweeps/next-runs
export interface NextRun { run_id: string; table: string; round: number; reason: Reason; values: Values }
export interface NextRunsResult {
  study: string; round: number; written: boolean; folder: string; files: string[];
  candidates: { values: Values; reason: Reason; note: string }[];
  runs: NextRun[];
  counts: { candidates: number; runs: number; refine: number; boundary: number; gap: number };
  pending: number; exhausted: boolean;
}

// ------------------------------------------------------------------ W17 launcher
export interface LauncherSubmitResult {
  study: string; round: number; mode: "round" | "run"; command: string[]; cwd: string; params_files: string[];
  submitted: number; log: string; exit_code: number | null; needs_confirm: boolean;
}
export interface LauncherStatusResult {
  study: string; round: number;
  counts: { submitted: number; done: number; failed: number; missing: number };
  runs: { run_id: string; table: string; state: "submitted" | "done" | "failed" | "missing"; result: string | null }[];
  duplicates: number; timed_out: boolean; finished: boolean;
}

// ------------------------------------------------------------------ W18 demo
/** The loop of any study (svcore/loop.py progress()): rounds so far, the runs now, the best, every value tried. */
export interface LoopProgress {
  study: string; round: number; running: boolean; converged: boolean; exhausted: boolean;
  state: "" | "running" | "converged" | "exhausted" | "stopped" | "error"; error: string;
  runs: { done: number; running: number; failed: number };
  points: { round: number; runs: number; best: number | null; gap_pct: number | null }[];
  best: { values: Values; score: number } | null;
  tried: { values: Values; round: number; feasible: boolean; state?: RunState }[];
  axes: string[];
  launcher: { command: string[]; mode: "run" | "round"; local_workers: number | null; run_as?: string | null; results: string };
}
/** The demo: the loop's progress plus the full grid's reference. */
export interface DemoProgress extends LoopProgress {
  optimum: { values: Values; score: number };
  full_grid: { values: number; runs: number };
  saving: number | null; tolerance_pct: number; seconds: number;
}
