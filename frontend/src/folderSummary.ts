/* FL1 (owner, 2026-11-16): a folder of recordings as one Sweeps table - a row per recording, the same measures in
   each, parameters from the names, a `recording` column that opens it again. The one way in, used by the Runs
   matrix (Summarize a folder), Sweeps > Data (From a folder of recordings) and the welcome card. The backend reads
   the folder one file at a time (app/routes/jobs.py summarizeFolder); without measures given it uses the folder's
   measures.json. */
import { api } from "./api";
import { openPaths, runJob } from "./files";
import { translate, type TFn } from "./i18n";
import { pickPath, useApp, type Measure } from "./store";

const folderName = (dir: string) => dir.split(/[\\/]/).filter(Boolean).pop() ?? dir;

/** Summarize `dir` (with these measures, or the folder's measures.json) and open the table in Sweeps.
 *  false: nothing to show (cancelled, failed - said - or no row). */
export async function summarizeFolder(dir: string, measures?: Omit<Measure, "id">[], pattern?: string): Promise<boolean> {
  const t: TFn = (k, v) => translate(useApp.getState().lang, k, v);
  const toast = useApp.getState().toast;
  let res: { columns: string[]; rows: (string | number | null)[][]; skipped: string[] } | null;
  try {
    res = await runJob("summarizeFolder", { folder: dir, ...(measures?.length ? { measures, pattern: pattern ?? "" } : {}) },
      t("mxSumFolderJob"));
  } catch (e) { toast({ kind: "error", text: (e as Error).message }); return false; }
  if (!res) return false;
  if (res.skipped.length) toast({ kind: "info", text: t("mxSumSkipped", { n: res.skipped.length, names: res.skipped.slice(0, 3).join("; ") }) });
  if (!res.rows.length) { toast({ kind: "error", text: t("mxNoRows", { folder: folderName(dir) }) }); return false; }
  const { useSweeps } = await import("./sweeps/state");
  useApp.setState({ matrixOpen: false, matrixFolder: null, area: "sweeps", startOpen: false });
  await useSweeps.getState().openRows(folderName(dir), res.columns, res.rows);
  return true;
}

/** Rows of a Sweeps table opened again as recordings, together (their signals side by side, Compare-ready). */
export function openRecordings(paths: string[]): void {
  useApp.setState({ area: "recordings", startOpen: false });
  void openPaths(paths, undefined, { autoView: true });
}

/** Sweeps > Data > From a folder of recordings: pick a folder; with its measures.json it is summed up at once,
 *  else its first recording opens with the Runs matrix to define the measures on it (Summarize then uses this folder). */
export async function fromFolder(): Promise<void> {
  const t: TFn = (k, v) => translate(useApp.getState().lang, k, v);
  const dir = await pickPath({ mode: "folder", title: t("mxSumFolderTitle") });
  if (!dir) return;
  let info: Awaited<ReturnType<typeof api.summaryFolder>>;
  try { info = await api.summaryFolder(dir); } catch (e) { useApp.getState().toast({ kind: "error", text: (e as Error).message }); return; }
  if (!info.first) { useApp.getState().toast({ kind: "error", text: t("mxNoRecordings", { folder: folderName(dir) }) }); return; }
  if (info.measures?.length) { await summarizeFolder(info.folder); return; }
  useApp.setState({ area: "recordings", startOpen: false, panel: "investigate", matrixFolder: info.folder });
  const open = useApp.getState().runs.some((r) => r.path === info.first);
  if (!open) await openPaths([info.first]);
  useApp.setState({ matrixOpen: true });
}
