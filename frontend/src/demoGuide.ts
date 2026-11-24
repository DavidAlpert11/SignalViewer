/* RV5: a demo opens what its welcome card promises and says, in one line, what to do next - with the
   click that does it (align the two clocks, put the cursors on the fault, open the panel that answers).
   Owner, 2026-11-23: "some examples load the finished result instead of showing how it is built - load, then lead the
   user". A demo is a short list of steps: each says what is on screen and what to do next, its button does that one
   thing, and the line moves to the next step; *Show the result* does every step left at once.
   UI only: the line is not saved; it goes when closed, when its files close or when another demo opens. */
import { api, type ExampleId } from "./api";
import { actions, useApp, type AppState } from "./store";
import type { TKey } from "./i18n";
import { applyTemplate } from "./templates";
import { applySyncOffset } from "./sync";
import { openAutoReport } from "./reportReady";
import { decodeAsMessages, makeRecording, streamFor } from "./messages";
import type { MessageStream } from "./store/model";
import { openWhatChanged } from "./investigation";

export interface DemoGuide { id: ExampleId; runs: string[]; step?: number; done?: boolean }

export interface Step {
  text: TKey; act?: TKey; go?: (runs: string[]) => Promise<void> | void;
  /** the step's result already holds (the user did it by hand: opened the panel, played): the line moves on by itself
   *  - it never offers what is already done (review 2026-11-24) */
  done?: (s: AppState) => boolean;
}
interface Demo {
  steps: Step[];
  /** what the line says once the last step's button was pressed (else the line goes) */
  done?: TKey;
  /** FR5: a demo that opens in Sweeps has its line there (no recordings open; the recordings' stage does not show it) */
  area?: "sweeps";
  /** the demo's own setup once its files are open, before its first step */
  setup?: (runs: string[]) => Promise<void> | void;
}

const panel = (p: "compare" | "log" | "report" | "investigate") => () => useApp.setState({ panel: p });
const isOpen = (p: AppState["panel"]) => (s: AppState) => s.panel === p;
/** the steps that open a panel: the button opens it; opened from the rail, the line moves on as well */
const open = (text: TKey, act: TKey, p: "compare" | "log"): Step => ({ text, act, go: panel(p), done: isOpen(p) });
const one = (text: TKey, act?: TKey, go?: Step["go"], done?: TKey): Demo => ({ steps: [{ text, act, go }], done });
/** UX5.4: the last step of a recordings demo - the report the app writes from the parts that fit what is open */
const report = (text: TKey): Step => ({ text, act: "demoReport1Act", go: () => openAutoReport(),
  done: (s) => s.panel === "report" && !!s.ws.report?.doc?.text });

/* UX5.4 (owner, 2026-11-23: "load, then lead the user"): each demo opens what its card shows, then two or three steps
   lead through the work - look (play, align, the cursors), compare or check, then the report written from it. */
export const DEMOS: Partial<Record<ExampleId, Demo>> = {
  flight: { steps: [
    { text: "demoFlight", act: "demoFlightAct", go: () => { if (!useApp.getState().playing) actions.togglePlay(); }, done: (s) => s.playing },
    { text: "demoFlight2", act: "demoChecksAct", go: () => { if (useApp.getState().playing) actions.togglePlay(); useApp.setState({ panel: "log" }); },
      done: isOpen("log") },
    report("demoFlight3"),
  ], done: "demoReportMade" },
  twoFlights: { steps: [open("demoTwoFlights", "demoCompareAct", "compare"), report("demoCompared")],
    done: "demoReportMade", setup: bothTracksOnOneMap },
  car: { steps: [open("demoCar", "demoCompareAct", "compare"), report("demoCompared")], done: "demoReportMade" },
  bench: { steps: [open("demoBench", "demoChecksAct", "log"), report("demoChecked")], done: "demoReportMade" },
  ardupilot: { steps: [open("demoArdupilot", "demoChecksAct", "log"), report("demoChecked")], done: "demoReportMade" },
  simVsFlight: { steps: [
    { text: "demoSimVsFlight", act: "demoAlignAct", go: alignSecond },
    open("demoSimVsFlightDone", "demoCompareAct", "compare"),
  ], done: "demoSimVsFlightDone2" },
  // the cursors are this demo's own (around the first bump): placed elsewhere by hand they do not count
  investigate: { steps: [
    { text: "demoInvestigate", act: "demoInvestigateAct", go: cursorsOnFirstBump },
    { text: "demoInvestigateDone", act: "demoInvestigateAct2", go: () => openWhatChanged({ a: 38.4, b: 39.3 }), done: (s) => !!s.whatChanged },
  ], done: "demoInvestigateDone2" },
  folderOfFlights: { ...one("demoFolder", "demoFolderAct", worstCopterFirst, "demoFolderDone"), area: "sweeps" },
  // the two runs plotted, then the report the app writes from the parts that fit them
  // review 2026-11-24: two steps like the other runs' demos - what differs, then the report written from the parts
  reportDemo: { steps: [open("demoReport1", "demoCompareAct", "compare"), report("demoReport2")], done: "demoReportDone" },
  // raw bytes -> the messages found in them -> their plots -> the link's report
  serialLink: {
    setup: (runs) => plotRaw(runs[0], ["tx_byte", "rx_byte"]),
    steps: [
      { text: "demoLink1", act: "demoLink1Act", go: (runs) => openLink(runs[0]) },
      { text: "demoLink2", act: "demoLink2Act", go: async (runs) => { if (!await decodeAsMessages(linkDef(runs[0]))) throw new Error("decode"); } },
      { text: "demoLink3", act: "demoLink3Act", go: () => openAutoReport("messages") },
    ],
    done: "demoLinkDone",
  },
  // the same link and its structure files -> each direction's messages a recording of their own
  linkStructure: {
    setup: (runs) => plotRaw(runs[0], ["tx_byte", "rx_byte"]),
    steps: [
      { text: "demoStruct1", act: "demoStruct1Act", go: (runs) => openLink(runs[0]) },
      { text: "demoStruct2", act: "demoStruct2Act", go: (runs) => useStructureFiles(runs[0]) },
      { text: "demoStruct3", act: "demoStruct3Act", go: (runs) => makeBothRecordings(runs[0]) },
    ],
    done: "demoStructDone",
  },
  // a receiver's NMEA read as a recording -> its track on the map -> speed, satellites, altitude
  gpsNmea: {
    steps: [
      { text: "demoGps1", act: "demoGps1Act", go: (runs) => gpsTrack(runs[0]) },
      { text: "demoGps2", act: "demoGps2Act", go: (runs) => gpsSide(runs[0]) },
    ],
    done: "demoGpsDone",
  },
};

/** the demo's step on screen now (null once its last button was pressed) */
export const currentStep = (g: DemoGuide): Step | null => DEMOS[g.id]?.steps[g.step ?? 0] ?? null;

/** Is the demo's line on screen: a demo with steps, its files still open, the welcome screen not over the plots.
 *  (FR2: the strip gives it the row of its own head - one rule for both.) */
export const demoLineUp = (s: { demoGuide: DemoGuide | null; runs: { id: string }[]; startOpen: boolean }): boolean =>
  !!s.demoGuide && !!DEMOS[s.demoGuide.id] && !DEMOS[s.demoGuide.id]!.area && !s.startOpen
  && s.demoGuide.runs.every((id) => s.runs.some((r) => r.id === id));

/** Called once a demo's files are open with their view: the demo's own setup, then its line. */
export async function startDemoGuide(id: ExampleId, runs: string[]) {
  const d = DEMOS[id];
  if (!d || (!runs.length && !d.area)) return;
  try { await d.setup?.(runs); } catch { /* the first step stands without it */ }
  useApp.setState({ demoGuide: { id, runs, step: 0 } });
}

/** The current step's button: its action, then the next step (or the demo's last line). Throws when it failed. */
export async function demoNext(g: DemoGuide) {
  const d = DEMOS[g.id], i = g.step ?? 0, step = d?.steps[i];
  if (!d || !step) return;
  await step.go?.(g.runs);
  const cur = useApp.getState().demoGuide;
  if (!cur || cur.id !== g.id || (cur.step ?? 0) > i || cur.done) return;     // moved on already (its result held: demoSkip)
  const next = i + 1;
  // FR2: once its button was pressed the line says what happened (the next step, or the "done" text) or goes -
  // it never keeps offering what was just done
  useApp.setState({ demoGuide: next < d.steps.length ? { ...g, step: next } : d.done ? { ...g, step: next, done: true } : null });
}

/** The current step's result already holds (done by hand): the next step, without running this one's action. */
function demoSkip(g: DemoGuide) {
  const d = DEMOS[g.id];
  if (!d) return;
  const next = (g.step ?? 0) + 1;
  useApp.setState({ demoGuide: next < d.steps.length ? { ...g, step: next } : d.done ? { ...g, step: next, done: true } : null });
}
// one watcher for every place the line is shown (above the plots, on a page, in the Report)
useApp.subscribe((s) => {
  const g = s.demoGuide;
  if (!g || g.done) return;
  if (currentStep(g)?.done?.(s)) demoSkip(g);
});

/** *Show the result*: every step left, one after the other. */
export async function demoFinish(g: DemoGuide) {
  let cur: DemoGuide | null = g;
  while (cur && !cur.done && currentStep(cur)) {
    await demoNext(cur);
    cur = useApp.getState().demoGuide;
  }
}

/* ---- the demos' own steps ------------------------------------------------------------------------------- */

/** The card's "two tracks on one map": Position on the map over both files, the first tab. */
async function bothTracksOnOneMap() {
  try {
    const r = await api.templates();
    const all = [...r.builtin, ...r.templates];
    const pos = r.builtin.find((x) => x.generator === "objects");
    if (!pos) return;
    const res = await applyTemplate(pos, all, { [pos.slots[0].id]: "*all" });
    if (!res.tabs) return;
    useApp.getState().commit((ws) => {
      const tab = ws.tabs.find((x) => x.id === ws.activeTab);
      if (tab) ws.tabs = [tab, ...ws.tabs.filter((x) => x !== tab)];
      return ws;
    });
  } catch { /* the Compare tabs stay */ }
}

/** The model and its flight ran on different clocks: the best offset the server finds, with Undo. */
async function alignSecond([ref, other]: string[]) {
  const c = (await api.syncSuggest(ref, other)).candidates[0];
  if (!c) throw new Error("no offset");
  await applySyncOffset(other, c.offset);
  actions.resetZoom();                    // both now in the same window
}

/** The roll leaves its set point first at ~38.4-39.3 s: the two cursors around it, Investigate open. */
function cursorsOnFirstBump() {
  const st = useApp.getState();
  useApp.setState({ cursor: { ...st.cursor, on: true, dual: true, t1: 38.4, t2: 39.3, active: 1 }, panel: "investigate" });
}

/** FR5: the folder of recordings - its answer is X8-A's vibration, 18 -> 67 over its six flights. The table sorted by
 *  vibration (X8-A's six flights are its top six) with them ticked: one more click opens them in Recordings. */
async function worstCopterFirst() {
  const [{ useSweeps }, { goFlow }] = await Promise.all([import("./sweeps/state"), import("./sweeps/goFlow")]);
  const st = useSweeps.getState(), s = st.studies[st.active];
  const tb = s?.tables[s.use];
  if (!s || !tb || !s.columns.some((c) => c.name === "vibration_max")) throw new Error("no vibration column");
  useSweeps.setState({ dataTab: "table", rawAsk: { table: tb.id, sort: { c: "vibration_max", desc: true }, tick: { col: "vehicle", value: "X8-A" } } });
  goFlow("data");
}

const sigId = (run: string, name: string) => useApp.getState().runs.find((r) => r.id === run)?.signals.find((s) => s.name === name)?.id;

/** The raw signals as they are - one plot each, in a tab of their own: what the file holds before anything is done. */
function plotRaw(run: string, names: string[]) {
  const ids = names.map((n) => sigId(run, n)).filter((x): x is string => !!x);
  if (ids.length) actions.plotsInNewTab(ids.map((id) => ({ title: id.slice(id.indexOf("/") + 1), ids: [id] })), useApp.getState().runs.find((r) => r.id === run)?.name ?? "");
}

/** The link's two signals as one stream: TX and RX (kept definition when there is one). */
function linkDef(run: string): MessageStream {
  const ids = [sigId(run, "tx_byte"), sigId(run, "rx_byte")];
  if (!ids[0] || !ids[1]) throw new Error("no tx_byte / rx_byte");
  const d = streamFor(ids as string[]);
  return d.carries === "pair" ? d : { ...d, carries: "pair", dir: null };
}

/** The Messages panel on the link (what Add a stream → TX and RX does). */
function openLink(run: string) {
  const d = linkDef(run);
  useApp.setState({ panel: "messages", msgFocus: { ids: d.sources, carries: "pair" } });
}

/** The link's two structure files (beside it in the example's folder) as the structures of TX and RX - one Undo step;
 *  the stream's editor shows them. */
async function useStructureFiles(run: string) {
  const path = useApp.getState().runs.find((r) => r.id === run)?.path ?? "";
  const dir = path.replace(/[\\/][^\\/]*$/, ""), sep = path.includes("\\") ? "\\" : "/";
  const [tx, rx] = await Promise.all(["link_tx", "link_rx"].map((n) => api.messagesStructure(`${dir}${sep}${n}.svmsg.json`).then((r) => r.structure)));
  const def = { ...linkDef(run), structures: { TX: tx, RX: rx } };
  useApp.getState().commit((ws) => {
    const key = def.sources.join(",");
    ws.messageStreams = [...(ws.messageStreams ?? []).filter((m) => m.sources.join(",") !== key), def];
    return ws;
  });
  // the fields the structures gave are the editor's step 3: in view, not under the fold (review 2026-11-24)
  setTimeout(() => document.querySelector(".msg-step-3")?.scrollIntoView({ block: "start" }), 150);
}

async function makeBothRecordings(run: string) {
  const def = linkDef(run);
  for (const side of ["TX", "RX"]) if (!await makeRecording(useApp.getState().ws.messageStreams?.find((m) => m.id === def.id) ?? def, side)) throw new Error("make");
}

/** MSG2: a GPS receiver's NMEA: its track on a map (the object found by name: GGA's position). */
async function gpsTrack(run: string) {
  const r = useApp.getState().runs.find((x) => x.id === run);
  if (!r) throw new Error("no run");
  const { detectObjects } = await import("./objectDetect");
  const { candidateObject, objectColors } = await import("./objectAdd");
  const found = detectObjects(r).candidates;
  const c = found.find((x) => /GGA/.test(x.name)) ?? found[0];
  if (!c) throw new Error("no position");
  actions.addObjectsToMaps([await candidateObject(c, objectColors(undefined)())]);
}

function gpsSide(run: string) {
  const r = useApp.getState().runs.find((x) => x.id === run);
  const by = (n: string) => r?.signals.find((s) => s.name.startsWith(n))?.id;
  const side = [by("RMC.speed"), by("GGA.sats"), by("GGA.alt")].filter((x): x is string => !!x);
  if (!side.length) throw new Error("no signals");
  actions.plotsInNewTab(side.map((id) => ({ title: id.slice(id.indexOf("/") + 1), ids: [id] })), r?.name ?? "");
}
