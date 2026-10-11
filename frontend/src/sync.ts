import { api, type SyncCandidate } from "./api";
import { newPlotSignal, TRACE_COLORS, uid, useApp, type Plot, type Tab } from "./store";
import { translate } from "./i18n";
import { LOG_FORMATS } from "./values";

/* Aligning the time of two recordings of the same flight (autopilot log .bin / .ulg and ground
   station telemetry .tlog). The server proposes offsets (boot clock, matching events, signal
   correlation); applying one sets the other file's time offset, with Undo. */

const bump = async () => useApp.setState({ runs: await api.listRuns(), dataVersion: useApp.getState().dataVersion + 1 });

export async function applySyncOffset(other: string, offset: number) {
  const st = useApp.getState();
  const info = st.runs.find((r) => r.id === other);
  if (!info) return;
  const before = info.timeOffset ?? 0;
  await api.patchRun(other, { timeOffset: offset });
  await bump();
  // the "same flight - align?" notice for this file is answered
  useApp.setState({ toasts: useApp.getState().toasts.filter((x) => !(x.text.includes(info.name) && x.action?.label === translate(useApp.getState().lang, "syncAlign"))) });
  const L = useApp.getState().lang;
  useApp.getState().toast({
    kind: "info", text: translate(L, "syncApplied", { name: info.name, s: offset.toFixed(3) }), ms: 12000,
    action: { label: translate(L, "undo"), run: async () => { await api.patchRun(other, { timeOffset: before }); await bump(); } },
  });
}

/** A new tab to check an alignment by eye: the same quantity from both files, and both flight modes. */
export function openSyncCheck(ref: string, other: string, c: SyncCandidate) {
  const st = useApp.getState();
  const ck = c.check;
  if (!ck) return;
  const L = st.lang;
  st.commit((ws) => {
    const plots: Plot[] = [];
    if (ck.pair) {
      const p: Plot = { id: uid("p"), title: translate(L, "syncCheckSignal"), signals: [] };
      // two clearly different colours, the reference thicker: a perfect overlap still shows both
      const r = newPlotSignal(`${ref}/${ck.pair[0]}`, ws);
      r.color = TRACE_COLORS[0]; r.width = 3.5;
      const o = newPlotSignal(`${other}/${ck.pair[1]}`, ws);
      o.color = TRACE_COLORS[2]; o.width = 1.5;
      o.scale = ck.scale || 1;
      p.signals.push(r, o);
      plots.push(p);
    }
    if (ck.refMode || ck.otherMode) {
      const p: Plot = { id: uid("p"), title: translate(L, "syncCheckModes"), signals: [] };
      if (ck.refMode) p.signals.push({ ...newPlotSignal(`${ref}/${ck.refMode}`, ws), color: TRACE_COLORS[0] });
      if (ck.otherMode) p.signals.push({ ...newPlotSignal(`${other}/${ck.otherMode}`, ws), color: TRACE_COLORS[2] });
      plots.push(p);
    }
    if (!plots.length) return ws;
    const tab: Tab = { id: uid("t"), name: translate(L, "syncCheckTab"), rows: plots.length, cols: 1, plots, active: 0, linkX: true };
    ws.tabs.push(tab);
    ws.activeTab = tab.id;
    return ws;
  });
}

/** When an autopilot log and a telemetry log of the same flight are both open and not aligned yet,
 *  offer to align them (once per pair). */
const asked = new Set<string>();
export async function detectSameFlight() {
  const st = useApp.getState();
  const logs = st.runs.filter((r) => LOG_FORMATS.has(r.format) && !r.copy);
  const ap = logs.filter((r) => r.format === "bin" || r.format === "ulg");
  const tl = logs.filter((r) => r.format === "tlog");
  for (const a of ap) for (const b of tl) {
    const key = `${a.id}|${b.id}`;
    if (asked.has(key)) continue;
    asked.add(key);
    let c: SyncCandidate | undefined;
    try { c = (await api.syncSuggest(a.id, b.id)).candidates[0]; } catch { continue; }
    if (!c || c.quality !== "high" || (c.method !== "boot" && c.method !== "events")) continue;
    if (Math.abs(c.offset - c.current) < 0.05) continue;                  // already aligned
    const L = useApp.getState().lang;
    useApp.getState().toast({
      kind: "info", ms: 30000,
      text: translate(L, "syncDetected", { a: b.name, b: a.name, s: c.delta.toFixed(2) }),
      action: { label: translate(L, "syncAlign"), run: () => { applySyncOffset(b.id, c!.offset); } },
    });
  }
}
