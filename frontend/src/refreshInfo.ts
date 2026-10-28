/** Q114: what a refresh (F5, Refresh all, a file's ↻) did, in words - for the file list, its tooltip
 *  and the message after a refresh. Small changes in the data used to leave the user unsure whether
 *  the file had been read again at all. */
import type { ReloadSummary, RunInfo } from "./api";
import { fmtInt, translate } from "./i18n";
import type { Lang } from "./i18n";

export function clock(at: number, lang: Lang): string {
  const d = new Date(at * 1000), loc = lang === "he" ? "he-IL" : "en-GB";
  const time = d.toLocaleTimeString(loc, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  return d.toDateString() === new Date().toDateString() ? time : `${d.toLocaleDateString(loc)} ${time}`;
}

const list = (names: string[], n: number) => names.slice(0, 6).join(", ") + (n > 6 ? ` +${n - 6}` : "");

/** The kind of result: not changed on the disk / saved again with the same data / new data. */
export function kindOf(r: ReloadSummary): "disk" | "same" | "new" {
  return !r.same ? "new" : r.fileChanged ? "same" : "disk";
}

/** A short line: "3 signals changed (Roll, Motor3, Wind) · 6,000 → 7,200 samples". */
export function shortWhat(r: ReloadSummary, lang: Lang): string {
  const k = kindOf(r);
  if (k === "disk") return translate(lang, "rfShortDisk");
  if (k === "same") return translate(lang, "rfShortSame");
  const parts: string[] = [];
  if (r.nChanged) parts.push(translate(lang, r.nChanged === 1 ? "rfChangedOne" : "rfChanged", { n: fmtInt(r.nChanged, lang), list: list(r.changed, r.nChanged) }));
  if (r.nAdded) parts.push(translate(lang, "rfAdded", { list: list(r.added, r.nAdded) }));
  if (r.nRemoved) parts.push(translate(lang, "rfRemoved", { list: list(r.removed, r.nRemoved) }));
  if (r.samplesAfter !== r.samplesBefore) parts.push(translate(lang, "rfSamples", { a: fmtInt(r.samplesBefore, lang), b: fmtInt(r.samplesAfter, lang) }));
  if (!parts.length) parts.push(translate(lang, "rfShortNew"));
  return parts.join(" · ");
}

/** The file row's tooltip lines: since when the data is what it is (and what changed then), the last
 *  check, when the file itself was saved. */
export function freshLines(run: RunInfo, lang: Lang): string[] {
  const out: string[] = [];
  const u = run.lastUpdate, r = run.lastReload;
  if (u) out.push(translate(lang, "rfChangedAt", { time: clock(u.at, lang), what: shortWhat(u, lang) }));
  else if (run.dataAt ?? run.readAt) out.push(translate(lang, "rfReadAt", { time: clock((run.dataAt ?? run.readAt)!, lang) }));
  if (r && (!u || r.at !== u.at)) out.push(translate(lang, "rfLast", { time: clock(r.at, lang), what: shortWhat(r, lang) }));
  if (run.fileTime) out.push(translate(lang, "rfFileTime", { time: clock(run.fileTime, lang) }));
  const nc = (r ?? u)?.notCompared ?? 0;
  if (nc > 0) out.push(translate(lang, "rfNotCompared", { n: fmtInt(nc, lang) }));
  return out;
}
