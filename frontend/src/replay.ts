/**
 * R1: the replay page - the tab on screen as one HTML file that opens in any browser, offline, on the
 * moment the user is looking at: one time for the whole page (a click on any plot, the timeline under the
 * plots or Play moves every plot's cursor and every map's markers), one zoom for every time plot, the
 * log's errors and warnings, the health check's findings and the user's notes as marks to jump to, and a
 * line saying where it came from. It IS the HTML report (backend app/report.py, `replay`) - one builder,
 * one viewer; this file only says what to put in it.
 */
import { api, type HealthFinding, type LogInfo } from "./api";
import { activeTab, pickPath, recordingExtent, useApp, type Tab } from "./store";
import { translate, type Lang, type TKey } from "./i18n";
import { pagePlots, plotSpec } from "./plotSpec";
import { runJob } from "./files";
import { findingText } from "./components/HealthRow";

export type ReplayLevel = "error" | "warning" | "note" | "finding";
export interface ReplayEvent { t: number; text: string; level: ReplayLevel }

/** The moment the page opens on: the cursor when it is on, else the middle of what is shown, else null
 *  (the page starts at the beginning). */
export function replayMoment(cursor: { on: boolean; t1: number | null }, shown: [number, number] | null): number | null {
  if (cursor.on && cursor.t1 !== null && Number.isFinite(cursor.t1)) return cursor.t1;
  if (shown && Number.isFinite(shown[0]) && Number.isFinite(shown[1])) return (shown[0] + shown[1]) / 2;
  return null;
}

/** The marks along the page's timeline, in time order: what the app's own timeline marks (errors and
 *  warnings of the logs, mode changes and info left out), the findings and the notes. */
export function replayEvents(
  logs: { info: LogInfo }[],
  findings: { t: number; text: string; level: HealthFinding["level"] }[],
  notes: { t: number; text: string }[],
): ReplayEvent[] {
  const out: ReplayEvent[] = [];
  for (const { info } of logs) {
    for (const e of info.events) {
      if (e.kind === "mode" || (e.level !== "error" && e.level !== "warning")) continue;
      out.push({ t: e.t + (info.timeOffset || 0), text: e.text, level: e.level });
    }
  }
  for (const f of findings) if (f.level !== "ok") out.push({ t: f.t, text: f.text, level: "finding" });
  for (const n of notes) out.push({ t: n.t, text: n.text, level: "note" });
  return out.filter((e) => Number.isFinite(e.t)).sort((a, b) => a.t - b.t).slice(0, 500);
}

/** A file name from the tab and the first file: "copter_flight-replay.html". */
export function replayFileName(tabName: string, fileName: string | undefined): string {
  const stem = (fileName ?? "").replace(/\.[^.]+$/, "") || tabName || "signalviewer";
  return `${stem.replace(/[\\/:*?"<>|\s]+/g, "_").slice(0, 60)}-replay.html`;
}

/** Plots a replay can draw: the one rule of every page (plotSpec.ts pagePlot) - lines, a map in 2D or 3D. */
export const replayPlots = (tab: Tab) => pagePlots(tab).filter((x) => x.include);
/** What a page left out, and why (a video, occurrences) - said in the toast, not dropped without a word. */
export const replayLeftOut = (tab: Tab) => pagePlots(tab).filter((x) => !x.include && x.why !== "pageWhyEmpty");

function findingTime(f: HealthFinding): number { return f.t ?? f.spans[0]?.[0] ?? NaN; }

/** The page's one time (1.26: every HTML report is live): the moment it opens on, the recording's span and
 *  the marks. `compact`: the replay's layout and one zoom for all; a report keeps its layout, each plot zooms alone. */
export function replayInfo(lang: Lang, compact: boolean) {
  const st = useApp.getState();
  const tr = (k: TKey, v?: Record<string, string | number>) => translate(lang, k, v);
  const files = st.runs.filter((r) => r.format !== "derived" && r.end > r.start);
  const logs = files.filter((r) => st.logs[r.id]).map((r) => ({ info: st.logs[r.id] }));
  const findings = files.flatMap((r) => (st.findingMarks[r.id] ?? []).map((f) => ({
    t: findingTime(f) + (st.logs[r.id]?.timeOffset || 0), text: findingText(tr, f), level: f.level })));
  const shown = Object.values(st.ranges)[0] ?? null;
  return { t: replayMoment(st.cursor, shown), extent: recordingExtent(st.runs), events: replayEvents(logs, findings, st.ws.notes ?? []),
    compact, link: compact };
}

/** What the server needs (POST /api/report with `replay`). */
export function replayBody(path: string) {
  const st = useApp.getState();
  const tab = activeTab(st.ws);
  const lang: Lang = st.lang;
  const tr = (k: TKey, v?: Record<string, string | number>) => translate(lang, k, v);
  const plotLabel = tr("plotTitle", { n: "{n}" });
  const files = st.runs.filter((r) => r.format !== "derived" && r.end > r.start);
  const name = tab.name || tr("tab");
  return {
    path, format: "html", lang, theme: st.theme,
    title: files.length ? `${name} · ${files.map((r) => r.name).slice(0, 3).join(", ")}` : name,
    notes: (st.ws.notes ?? []).map((n) => ({ t: n.t, ...(n.t2 !== undefined ? { t2: n.t2 } : {}), text: n.text })),
    tabs: [{ name, plots: replayPlots(tab).map(({ p, pi }) => plotSpec(tab, p, pi, plotLabel)) }],
    replay: replayInfo(lang, true),
  };
}

/** Save the tab as a replay page, then offer to open it in the browser (to look before sending). */
export async function makeReplay() {
  const st = useApp.getState();
  const lang = st.lang;
  const tab = activeTab(st.ws);
  if (!replayPlots(tab).length) { st.toast({ kind: "error", text: translate(lang, "replayEmpty") }); return; }
  const first = st.runs.find((r) => r.format !== "derived");
  const path = await pickPath({ mode: "save", title: translate(lang, "replaySave"), exts: [".html"], defaultName: replayFileName(tab.name, first?.name) });
  if (!path) return;
  try {
    const r = await runJob<{ path: string }>("report", replayBody(path), translate(lang, "replayMaking"));
    if (!r) return;
    const out = replayLeftOut(tab).map(({ p, pi, why }) => `${p.title || translate(lang, "plotTitle", { n: pi + 1 })} (${translate(lang, why!)})`);
    const saved = translate(lang, "replaySaved", { path: r.path }) + (out.length ? ` · ${translate(lang, "pageLeftOut", { list: out.join(", ") })}` : "");
    useApp.getState().toast({ kind: "info", text: saved, ms: 12000,
      action: { label: translate(lang, "replayOpen"), run: () => { api.openPage(r.path).catch(() => {}); } } });
  } catch (e) {
    useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
  }
}
