/* 26.U4: "judge a run" - open a recording, the app proposes a baseline (a golden run you marked, or
   the file whose name says it is the reference), Compare shows pass / fail per file and where it
   fails, then a report.

   Golden runs are remembered in the app's settings (prefs: path + the tolerances last used with it),
   not in a session: they belong to the test, not to one look at the data. */
import { api, type CompareAllRow, type Tolerances } from "./api";
import { getPrefValue, setPref } from "./prefs";
import { fileLabel, uid, useApp, type ReportVerdict } from "./store";
import { openPaths } from "./files";
import { translate, fmtNum } from "./i18n";

export interface Golden { path: string; name: string; tolerances?: Tolerances | null; at: number }
const KEY = "sv.goldenRuns";
const MAX = 20;
const FIT_MIN = 0.5;                 // a golden run is proposed for a file with at least half of its signals
const norm = (p: string) => p.replace(/\\/g, "/").toLowerCase();
const bare = (n: string) => n.replace(/\s*\[[^\]]*\]\s*$/, "").toLowerCase();

export const goldenRuns = (): Golden[] => getPrefValue<Golden[]>(KEY) ?? [];
export const isGolden = (path: string | undefined) => !!path && goldenRuns().some((g) => norm(g.path) === norm(path));

/** Mark (or unmark) a file as a golden run; its tolerances are remembered with it. */
export function setGolden(path: string, on: boolean, tolerances?: Tolerances | null) {
  const rest = goldenRuns().filter((g) => norm(g.path) !== norm(path));
  const name = path.split(/[\\/]/).pop() ?? path;
  setPref(KEY, on ? [{ path, name, tolerances: tolerances ?? null, at: Date.now() }, ...rest].slice(0, MAX) : rest);
}

/** Remember the tolerances last used against a golden run (they are proposed with it next time). */
export function rememberTolerances(path: string, tolerances: Tolerances) {
  const all = goldenRuns();
  const g = all.find((x) => norm(x.path) === norm(path));
  if (!g || JSON.stringify(g.tolerances ?? null) === JSON.stringify(tolerances)) return;
  setPref(KEY, all.map((x) => (x === g ? { ...x, tolerances } : x)));
}

/** The baseline Compare starts with: an open golden run, else a file named as the reference
 *  (golden, reference, baseline, nominal, expected), else the first file - as before. */
export function proposeBaseline(runs: { id: string; path: string; name: string }[]): string {
  const g = runs.find((r) => isGolden(r.path));
  if (g) return g.id;
  const named = runs.find((r) => /(^|[^a-z])(golden|gold|ref|reference|baseline|nominal|expected)([^a-z]|$)/i.test(r.name));
  return (named ?? runs[0])?.id ?? "";
}

/** A golden run (not open, not this file) that fits a file just opened: the most of its signals. */
export async function goldenFor(runId: string): Promise<(Golden & { share: number }) | null> {
  const run = useApp.getState().runs.find((r) => r.id === runId);
  if (!run || isGolden(run.path)) return null;
  const mine = new Set(run.signals.map((s) => bare(s.name)));
  let best: (Golden & { share: number }) | null = null;
  for (const g of goldenRuns()) {
    if (norm(g.path) === norm(run.path)) continue;
    try {
      const { signals } = await api.fileSignals(g.path);
      const share = signals.length ? signals.filter((n) => mine.has(bare(n))).length / Math.max(mine.size, 1) : 0;
      if (share >= FIT_MIN && (!best || share > best.share)) best = { ...g, share };
    } catch { /* moved or deleted: not proposed */ }
  }
  return best;
}

/** Judge `runId` against the golden run at `path`: open it (if it is not), its tolerances, Compare. */
export async function judgeAgainst(runId: string, golden: Golden) {
  const key = norm(golden.path);
  let g = useApp.getState().runs.find((r) => r.format !== "derived" && norm(r.path) === key);
  if (!g) {
    await openPaths([golden.path], undefined, { noStart: true });     // the card is this run's, not the golden one's
    g = useApp.getState().runs.find((r) => r.format !== "derived" && norm(r.path) === key);
  }
  if (!g) return;
  useApp.setState({
    ...(golden.tolerances ? { compareTol: golden.tolerances } : {}),
    compareJudge: { baseline: g.id, runs: [g.id, runId] }, panel: "compare",
  });
}

/** Per file against the baseline: the signals judged, those outside (worst first). */
export interface FileVerdict { run: string; judged: number; failed: { name: string; outsidePct: number | null; maxAbs: number }[] }
export function verdicts(rows: CompareAllRow[], baseline: string, active: string[]): FileVerdict[] {
  return active.filter((rid) => rid !== baseline).map((rid) => {
    const per = rows.flatMap((x) => (x.diffs ?? []).filter((d) => d.run === rid && d.pass !== null && d.pass !== undefined)
      .map((d) => ({ name: x.name, pass: d.pass!, outsidePct: d.outsidePct ?? null, maxAbs: d.maxAbsDiff })));
    const failed = per.filter((p) => !p.pass).sort((a, b) => (b.outsidePct ?? 0) - (a.outsidePct ?? 0))
      .map(({ name, outsidePct, maxAbs }) => ({ name, outsidePct, maxAbs }));
    return { run: rid, judged: per.length, failed };
  });
}

const tolText = (x: CompareAllRow) => {
  const t = x.tol ?? {};
  return [t.abs !== undefined ? `±${t.abs}` : "", t.pct !== undefined ? `±${t.pct} %` : "", t.time ? `±${t.time} s` : "",
    t.outside_pct ? `≤ ${t.outside_pct} % out` : ""].filter(Boolean).join(" / ");
};

/** The report's verdict (a table per signal and file), in the report's language. */
export function reportVerdict(rows: CompareAllRow[], baseline: string, active: string[], lang: "en" | "he"): ReportVerdict {
  const runs = useApp.getState().runs;
  const t = (k: Parameters<typeof translate>[1], p?: Record<string, string | number>) => translate(lang, k, p);
  const others = active.filter((r) => r !== baseline);
  const vs = verdicts(rows, baseline, active);
  const summary = vs.map((v) => `${fileLabel(runs, v.run)}: ${v.failed.length
    ? t("judgeFailN", { n: v.failed.length, of: v.judged }) : t("judgePassAll", { of: v.judged })}`);
  const judged = rows.filter((x) => (x.diffs ?? []).some((d) => d.pass !== null && d.pass !== undefined));
  judged.sort((a, b) => Number(a.pass ?? true) - Number(b.pass ?? true));        // failures first
  return {
    title: t("judgeReportTitle", { base: fileLabel(runs, baseline) }),
    summary,
    head: [t("signal"), t("tolerance"), ...others.map((r) => fileLabel(runs, r))],
    rows: judged.map((x) => [x.name, tolText(x), ...others.map((rid) => {
      const d = x.diffs?.find((y) => y.run === rid);
      if (!d || d.pass === null || d.pass === undefined) return "–";
      return `${d.pass ? "✓" : "✗"} ${fmtNum(d.outsidePct ?? 0, lang, 3)} % ${t("judgeOutside")} · max |Δ| ${fmtNum(d.maxAbsDiff, lang, 4)}`;
    })]),
    id: uid("v"),
  };
}
