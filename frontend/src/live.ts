import { api } from "./api";
import { actions, fileLabel, useApp } from "./store";
import { clock, forgetNewer } from "./fileTimes";
import { translate } from "./i18n";
import { openPaths, runJob } from "./files";

/** Read every open file again (button "Refresh all", F5, and the first step of live mode).
 *  Files whose size and date did not change are not read again. Returns false on failure. */
export async function refreshAll(opts: { quiet?: boolean } = {}): Promise<boolean> {
  const st = useApp.getState();
  const L = st.lang;
  if (!st.runs.some((r) => r.format !== "derived")) return true;
  try {
    const res = await runJob<{ reloaded: string[]; unchanged: string[]; errors: { id: string; name: string; message: string }[]; skipped: string[] }>(
      "reloadAll", {}, translate(L, "refreshingAll"));
    if (!res) return false;                                   // cancelled
    const before = useApp.getState().runs;
    useApp.setState({ runs: await api.listRuns(), dataVersion: useApp.getState().dataVersion + 1 });
    actions.dropStaleRanges();
    actions.pinTimeToEnd(before);
    for (const e of res.errors) useApp.getState().toast({ kind: "error", text: translate(L, "refreshFailed", { name: e.name, msg: e.message }) });
    forgetNewer(res.reloaded);
    if (!opts.quiet) {
      // Q123: a line per file - read again (and the time its new version was saved) or not changed on
      // the disk - so a small change in the data still shows that the file was read; it stays 10 s and
      // the next refresh replaces it
      const runsNow = useApp.getState().runs;
      const line = (id: string, key: "ftUpdated" | "ftUnchanged") => {
        const r = runsNow.find((x) => x.id === id);
        return translate(L, key, { name: `\u2068${fileLabel(runsNow, id)}\u2069`, time: r?.fileTime ? clock(r.fileTime, L) : "–" });
      };
      const ids = [...res.reloaded.map((id) => [id, "ftUpdated"] as const), ...res.unchanged.map((id) => [id, "ftUnchanged"] as const)];
      const lines = ids.length <= 5 ? ids.map(([id, k]) => line(id, k))
        : [translate(L, "refreshedN", { n: res.reloaded.length }) + (res.unchanged.length ? " · " + translate(L, "unchangedN", { n: res.unchanged.length }) : ""),
           ...res.reloaded.slice(0, 4).map((id) => line(id, "ftUpdated"))];
      if (res.skipped.length) lines.push(translate(L, "copiesSkippedN", { n: res.skipped.length }));
      useApp.getState().toast({ kind: "info", text: lines.join("\n"), ms: 10000, key: "refresh" });
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
