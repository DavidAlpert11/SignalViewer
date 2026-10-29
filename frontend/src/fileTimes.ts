/** Q123: when each open file was saved to the disk, and whether it was saved again since the app read
 *  it. A user pressed F5, the message went by, and with small changes in the data it was not clear
 *  whether the file had been read again: the file list now shows the saved time of the version on
 *  screen, and turns it amber (click to read it again) when the file on the disk is newer. */
import { api } from "./api";
import type { RunInfo } from "./api";
import { translate } from "./i18n";
import type { Lang } from "./i18n";
import { useApp } from "./store";

const loc = (lang: Lang) => (lang === "he" ? "he-IL" : "en-GB");

/** 21:24:07 today; with the date on another day. */
export function clock(at: number, lang: Lang): string {
  const d = new Date(at * 1000);
  const time = d.toLocaleTimeString(loc(lang), { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  return d.toDateString() === new Date().toDateString() ? time : `${d.toLocaleDateString(loc(lang))} ${time}`;
}

/** The short form on the file row: 21:24 today, the date (27/10) on another day. */
export function shortClock(at: number, lang: Lang): string {
  const d = new Date(at * 1000);
  return d.toDateString() === new Date().toDateString()
    ? d.toLocaleTimeString(loc(lang), { hour: "2-digit", minute: "2-digit", hour12: false })
    : d.toLocaleDateString(loc(lang), { day: "2-digit", month: "2-digit" });
}

/** The file row's tooltip lines. */
export function fileTimeLines(run: RunInfo, lang: Lang, newer?: number): string[] {
  const out: string[] = [];
  if (newer) out.push(translate(lang, "ftNewer", { time: clock(newer, lang) }));
  if (run.fileTime) out.push(translate(lang, "ftSaved", { time: clock(run.fileTime, lang) }));
  if (run.readAt) out.push(translate(lang, "ftRead", { time: clock(run.readAt, lang) }));
  return out;
}

/** Ask every few seconds which open files were saved again (not in live mode: it reads them itself;
 *  not while the window is hidden). Only date and size are looked at - cheap even for big files. */
let started = false;
export function watchNewerOnDisk(everyMs = 3000) {
  if (started) return;
  started = true;
  const tick = async () => {
    const st = useApp.getState();
    if (st.streaming || document.visibilityState !== "visible" || !st.runs.some((r) => r.format !== "derived" && !r.copy)) {
      if (Object.keys(st.newerOnDisk).length) useApp.setState({ newerOnDisk: {} });
      return;
    }
    try {
      const now = await api.newerOnDisk();
      const old = useApp.getState().newerOnDisk;
      if (JSON.stringify(now) !== JSON.stringify(old)) useApp.setState({ newerOnDisk: now });
    } catch { /* the server is busy or gone: ask again next time */ }
  };
  window.setInterval(tick, everyMs);
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") tick(); });
}

/** After a refresh: the files read again are no longer newer on the disk (the next poll confirms). */
export function forgetNewer(ids: string[]) {
  const cur = { ...useApp.getState().newerOnDisk };
  let changed = false;
  for (const id of ids) if (id in cur) { delete cur[id]; changed = true; }
  if (changed) useApp.setState({ newerOnDisk: cur });
}
