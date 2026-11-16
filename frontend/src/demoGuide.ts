/* RV5: a demo opens what its welcome card promises and says, in one line, what to do next - with the
   click that does it (align the two clocks, put the cursors on the fault, open the panel that answers).
   UI only: the line is not saved; it goes when closed, when its files close or when another demo opens. */
import { api, type ExampleId } from "./api";
import { actions, useApp } from "./store";
import type { TKey } from "./i18n";
import { applyTemplate } from "./templates";
import { applySyncOffset } from "./sync";

export interface DemoGuide { id: ExampleId; runs: string[]; done?: boolean }

interface Step { text: TKey; act?: TKey; done?: TKey; go?: (runs: string[]) => Promise<void> | void }

const panel = (p: "compare" | "log" | "report" | "investigate") => () => useApp.setState({ panel: p });

export const DEMO_STEPS: Partial<Record<ExampleId, Step>> = {
  flight: { text: "demoFlight", act: "demoFlightAct", go: () => { if (!useApp.getState().playing) actions.togglePlay(); } },
  twoFlights: { text: "demoTwoFlights", act: "demoCompareAct", go: panel("compare") },
  car: { text: "demoCar", act: "demoCompareAct", go: panel("compare") },
  bench: { text: "demoBench", act: "demoChecksAct", go: panel("log") },
  ardupilot: { text: "demoArdupilot", act: "demoChecksAct", go: panel("log") },
  simVsFlight: { text: "demoSimVsFlight", act: "demoAlignAct", done: "demoSimVsFlightDone", go: alignSecond },
  investigate: { text: "demoInvestigate", act: "demoInvestigateAct", done: "demoInvestigateDone", go: cursorsOnFirstBump },
};

/** Called once a demo's files are open with their view: the demo's own setup, then its line. */
export async function startDemoGuide(id: ExampleId, runs: string[]) {
  if (!runs.length || !DEMO_STEPS[id]) return;
  if (id === "twoFlights") await bothTracksOnOneMap();
  useApp.setState({ demoGuide: { id, runs } });
}

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
