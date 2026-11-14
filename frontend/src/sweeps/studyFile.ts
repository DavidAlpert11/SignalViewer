/* C5: one study file (plan §4.5). `.svstudy.json` is the study (the engine's contract) with an optional
   `workspace` block for what only this area needs: each table as its `.svsweep` document (roles as set, the
   whole question, the view, merged tables' recipes) and the place last shown. A study that is one table without
   Set up (no command, no start grid, no second system, no rounds) keeps being saved as `.svsweep` -
   a results-only user sees no change; anything more is saved as `.svstudy.json` (*Save as study...*). Pure
   functions: Vitest round-trips every example and its 1.27 copy. */
import type { SavedStudy } from "./state";
import { goalToStudy, studyRoles } from "./studyRoles";
import { upgradeQuestion } from "./model";
import type { Study, StudyTable, WorkspaceBlock } from "./studyTypes";

export const SWEEP_EXT = ".svsweep";
/** The results tables the area opens. */
export const TABLE_EXTS = [".csv", ".tsv", ".txt", ".parquet", ".pq", ".xlsx", ".xls"];
export const STUDY_EXT = ".svstudy.json";

/** The study has a part a `.svsweep` cannot hold. */
export function hasSetup(s: Study | null | undefined): boolean {
  if (!s) return false;
  // the parameters' ranges alone do not count: *I have results* fills them from the columns
  return !!s.launcher?.submit?.length || !!s.start || (s.tables?.length ?? 0) >= 2 || (s.history?.length ?? 0) > 0 || !!s.demo;
}

/** Which file Save writes: the single-table file while the study is one table without Set up. */
export function fileKind(setup: Study | null | undefined, tables: number): "svsweep" | "svstudy" {
  return tables <= 1 && !hasSetup(setup) ? "svsweep" : "svstudy";
}

/** A table's files as the study lists them (a merged table has none of its own: its recipe is in the workspace). */
function docPaths(d: SavedStudy, i: number): string[] {
  const t = d.tables?.[d.use ?? 0] ?? (i === 0 && d.path ? { recipe: { path: d.path, merged: d.merged } } : undefined);
  const r = t?.recipe as { path?: string; merged?: { path: string }[] } | undefined;
  return r?.path ? [r.path, ...(r.merged ?? []).map((m) => m.path)] : d.path ? [d.path] : [];
}

/** A study table from the area's table: its files, roles in the study's words, and its goal as the study holds it. */
export function tableOfDoc(d: SavedStudy, i: number, id = `T${i + 1}`): StudyTable {
  const area = Object.fromEntries(d.columns.map((c) => [c.name, c.role]));
  const name = (d.path || d.tables?.[d.use ?? 0]?.name || id).replace(/\\/g, "/").split("/").pop()!.replace(/\.[^.]+$/, "");
  const { patch } = goalToStudy(upgradeQuestion(d.question));
  return { id, name, paths: docPaths(d, i), roles: studyRoles(area), ...patch };
}

/** The study file to save: the study's own parts (Set up, Together, the loop) as they are, its tables from the
 *  area's tables when it has none of its own, and the area's tables in `workspace`. */
export function toStudyFile(setup: Study | null | undefined, docs: SavedStudy[], active = 0,
  place?: WorkspaceBlock["place"]): Study {
  const base: Study = setup ? structuredClone(setup) : { version: 1, name: "", tables: [] };
  if (!base.tables?.length) base.tables = docs.map((d, i) => tableOfDoc(d, i));
  const out: Study = { ...base, version: 1 };
  if (docs.length) out.workspace = { version: 1, sweeps: structuredClone(docs), active, ...(place ? { place } : {}) };
  else delete out.workspace;
  return out;
}

/** A study file as the area opens it: the study (without its workspace) and the area's tables in it. */
export function fromStudyFile(file: Study): { setup: Study; docs: SavedStudy[]; active: number; place?: WorkspaceBlock["place"] } {
  const { workspace, ...setup } = structuredClone(file);
  const docs = (workspace?.sweeps ?? []).filter((d) => d && d.kind === "signalviewer-sweep");
  return { setup: setup as Study, docs, active: Math.min(Math.max(0, workspace?.active ?? 0), Math.max(0, docs.length - 1)), place: workspace?.place };
}

/** A file's kind by its name. */
export const kindOfPath = (p: string): "svsweep" | "svstudy" | "" =>
  p.toLowerCase().endsWith(STUDY_EXT) ? "svstudy" : p.toLowerCase().endsWith(SWEEP_EXT) ? "svsweep" : "";
