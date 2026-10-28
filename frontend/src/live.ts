import { api } from "./api";
import { actions, fileLabel, useApp } from "./store";
import { translate } from "./i18n";
import { openPaths, runJob } from "./files";
import type { ReloadSummary } from "./api";
import { clock, kindOf, shortWhat } from "./refreshInfo";

/** Read every open file again (button "Refresh all", F5, and the first step of live mode).
 *  Files whose size and date did not change are not read again. Returns false on failure. */
export async function refreshAll(opts: { quiet?: boolean } = {}): Promise<boolean> {
  const st = useApp.getState();
  const L = st.lang;
  if (!st.runs.some((r) => r.format !== "derived")) return true;
  try {
    const res = await runJob<{ reloaded: string[]; unchanged: string[]; errors: { id: string; name: string; message: string }[]; skipped: string[];
      details?: (ReloadSummary & { id: string; name: string })[] }>(
      "reloadAll", {}, translate(L, "refreshingAll"));
    if (!res) return false;                                   // cancelled
    const before = useApp.getState().runs;
    useApp.setState({ runs: await api.listRuns(), dataVersion: useApp.getState().dataVersion + 1 });
    actions.dropStaleRanges();
    actions.pinTimeToEnd(before);
    for (const e of res.errors) useApp.getState().toast({ kind: "error", text: translate(L, "refreshFailed", { name: e.name, msg: e.message }) });
    if (!opts.quiet) {
      // Q114: what each file did - "not changed on the disk" / "saved again, the data is the same" /
      // which signals changed; the same result stays on the file in the list (↻ / ✓ and the time)
      const det = res.details ?? [];
      const runsNow = useApp.getState().runs;
      const head = translate(L, "rfToastTitle", { time: det.length ? clock(det[0].at, L) : clock(Date.now() / 1000, L) });
      const name = (d: { id: string }) => `\u2068${fileLabel(runsNow, d.id)}\u2069`;      // isolated: right order in Hebrew
      const lines = det.slice(0, 4).map((d) => `${name(d)}: ${shortWhat(d, L)}`);
      if (det.length > 4) {
        const nNew = det.filter((d) => kindOf(d) === "new").length;
        lines.splice(0, lines.length, translate(L, "refreshedN", { n: nNew }), translate(L, "unchangedN", { n: det.length - nNew }),
          ...det.filter((d) => kindOf(d) === "new").slice(0, 3).map((d) => `${name(d)}: ${shortWhat(d, L)}`));
      }
      if (res.skipped.length) lines.push(translate(L, "copiesSkippedN", { n: res.skipped.length }));
      useApp.getState().toast({ kind: "info", text: [head, ...lines].join("\n"), ms: 10000, key: "refresh" });
    }
    return true;
  } catch (e) {
    useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
    return false;
  }
}

/** Live mode: first refresh every file (so what is shown is current), then follow the files
 *  that keep growing. Files opened while live mode runs are followed too. */
export async function startLive() {
  const st = useApp.getState();
  if (st.streaming) return;
  useApp.setState({ liveStarting: true });
  try {
    await refreshAll({ quiet: true });
    await api.streamStart();
    useApp.setState({ streaming: true, activity: {}, liveLastData: Date.now(), liveIdle: 0 });
    // live: the time goes to the newest data and stays there as data arrives (the map / 3D object
    // in its latest state); moving it back still works, End returns to following
    actions.pinTimeToEnd(useApp.getState().runs, true);
  } catch (e) {
    useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
  } finally {
    useApp.setState({ liveStarting: false });
  }
}

export async function stopLive(reason?: "idle") {
  useApp.setState({ streaming: false, activity: {} });
  api.streamStop().catch(() => {});
  if (reason === "idle") {
    const st = useApp.getState();
    st.toast({ kind: "info", text: translate(st.lang, "liveStoppedIdle", { n: String(st.liveAutoStop ?? 0) }),
      action: { label: translate(st.lang, "liveResume"), run: () => { startLive(); } }, ms: 20000 });
  }
}

export function toggleLive() {
  const st = useApp.getState();
  if (st.streaming) stopLive(); else if (!st.liveStarting) startLive();
}

/** New files next to the open ones appeared during live mode. */
const offered = new Set<string>();
export function handleNewFiles(files: { path: string; name: string }[]) {
  const st = useApp.getState();
  const fresh = files.filter((f) => !offered.has(f.path));
  fresh.forEach((f) => offered.add(f.path));
  if (!fresh.length || st.liveNewFiles === "ignore") return;
  if (st.liveNewFiles === "auto") {
    openPaths(fresh.map((f) => f.path));
    st.toast({ kind: "info", text: translate(st.lang, "newFilesOpened", { names: fresh.map((f) => f.name).join(", ") }) });
    return;
  }
  st.toast({
    kind: "info", text: translate(st.lang, fresh.length === 1 ? "newFileAppeared" : "newFilesAppeared", { names: fresh.map((f) => f.name).join(", "), n: fresh.length }),
    action: { label: translate(st.lang, "openThem"), run: () => { openPaths(fresh.map((f) => f.path)); } }, ms: 20000,
  });
}
