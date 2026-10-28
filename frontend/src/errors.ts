/* The error between the two lines of a plot - a flight computer's X against the true X - and the same
   for every plot of the tab that holds two lines: one derived signal each (second line − first, made
   once and reused), all of them in a new tab, a plot per axis titled with its RMS, mean and largest
   error over the run. */
import { api } from "./api";
import { translate } from "./i18n";
import { findDerived } from "./peers";
import { record } from "./investigation";
import { activeTab, signalName, uid, useApp, type Plot, type Tab } from "./store";

const COLORS = ["#E5677A", "#3D8BFD", "#2FBF9F", "#9B7BFF", "#F07B3F", "#4FC3E8"];

/** The plot's two lines over time (states left out), or null when it has not exactly two. */
export function twoLines(p: Plot): [string, string] | null {
  if ((p.mode ?? "time") !== "time") return null;
  const lines = p.signals.filter((s) => !s.state);
  return lines.length === 2 ? [lines[0].sig, lines[1].sig] : null;
}

/** Plots of the active tab with exactly two lines. */
export function plotsWithTwoLines(): Plot[] {
  return activeTab(useApp.getState().ws).plots.filter((p) => twoLines(p));
}

const g = (x: number) => Number(x.toPrecision(3)).toString();

export async function errorsOf(plots: Plot[]) {
  const st = useApp.getState();
  const L = st.lang;
  const pairs = plots.map(twoLines).filter((x): x is [string, string] => !!x);
  if (!pairs.length) return;
  const made: { id: string; a: string; b: string }[] = [];
  try {
    for (const [a, b] of pairs) {
      let id = findDerived(useApp.getState().runs, "sub", {}, [b, a]);
      if (!id) {
        const r = await api.createDerived("sub", [b, a], {});
        useApp.setState({ runs: r.runs });
        id = r.id;
      }
      made.push({ id, a, b });
    }
  } catch (err) {
    st.toast({ kind: "error", text: String((err as Error).message) });
    if (!made.length) return;
  }
  // RMS, mean and the largest error where both have data - and the flight mode (the file's phase
  // signal, as the strip shows it) where they part ways most
  type Seg = Awaited<ReturnType<typeof api.errorSegments>>;
  const seg: Record<string, Seg> = {};
  const phaseOf: Record<string, string | null> = {};
  for (const m of made) {
    const rid = m.b.slice(0, m.b.indexOf("/"));
    if (!(rid in phaseOf)) { try { phaseOf[rid] = (await api.overview(rid, [])).phaseSignal; } catch { phaseOf[rid] = null; } }
    const ph = phaseOf[rid];
    try { seg[m.id] = await api.errorSegments(m.b, m.a, ph ? `${rid}/${ph}` : null, "linear"); }
    catch { try { seg[m.id] = await api.errorSegments(m.b, m.a, null, "linear"); } catch { /* a title without numbers */ } }
  }
  const runs = useApp.getState().runs;
  const title = (m: { id: string; a: string; b: string }) => {
    const name = `${signalName(runs, m.b)} − ${signalName(runs, m.a)}`;
    const tot = seg[m.id]?.total;
    if (!tot || !tot.n || tot.rms === undefined) return name;
    let text = translate(L, "pairErrTitle", { name, rms: g(tot.rms), mean: g(tot.mean ?? 0), max: g(tot.maxAbs ?? 0), at: g(tot.tMaxAbs ?? 0) });
    // per mode (its stretches together): named only when it stands out - 1.5 x the next one
    const by = new Map<string, { n: number; ss: number }>();
    for (const r of seg[m.id]?.rows ?? []) {
      if (!r.n || r.rms === undefined) continue;
      const k = r.label ?? String(r.value), e = by.get(k) ?? { n: 0, ss: 0 };
      e.n += r.n; e.ss += r.n * r.rms * r.rms; by.set(k, e);
    }
    const modes = [...by.entries()].map(([k, e]) => ({ k, rms: Math.sqrt(e.ss / e.n) })).sort((p, q) => q.rms - p.rms);
    if (modes.length > 1 && modes[0].rms >= 1.5 * modes[1].rms)
      text += translate(L, "pairErrWorstPhase", { phase: modes[0].k, rms: g(modes[0].rms) });
    return text;
  };
  useApp.getState().commit((ws) => {
    const plotsOut: Plot[] = made.map((m, i) => ({ id: uid("p"), title: title(m),
      signals: [{ sig: m.id, color: COLORS[i % COLORS.length], width: 1.5, scale: 1, offset: 0 }] }));
    const tab: Tab = { id: uid("t"), name: translate(L, "pairErrTabName"), rows: plotsOut.length, cols: 1, plots: plotsOut, active: 0, linkX: true };
    ws.tabs.push(tab); ws.activeTab = tab.id;
    return ws;
  });
  // the cursor on the largest error of them all
  const big = made.map((m) => seg[m.id]?.total).filter((x) => x && x.maxAbs !== undefined && x.tMaxAbs !== undefined)
    .sort((p, q) => q!.maxAbs! - p!.maxAbs!)[0];
  if (big) useApp.setState({ cursor: { ...useApp.getState().cursor, on: true, dual: false, t1: big.tMaxAbs!, active: 1 } });
  const ranked = made.map((m) => ({ m, r: seg[m.id]?.total?.rms })).filter((x) => x.r !== undefined).sort((p, q) => q.r! - p.r!);
  record(translate(L, "jErrors", { list: made.map((m) => {
    const tt = seg[m.id]?.total;
    return `${signalName(runs, m.b)} − ${signalName(runs, m.a)}${tt?.rms !== undefined ? ` (RMS ${g(tt.rms)}, max ${g(tt.maxAbs ?? 0)} at ${g(tt.tMaxAbs ?? 0)} s)` : ""}`;
  }).join("; ") }), true, "error");
  st.toast({ kind: "info", ms: 9000, text: translate(L, "pairErrDone", { n: made.length })
    + (ranked.length > 1 ? ` ${translate(L, "pairErrWorst", { name: signalName(runs, ranked[0].m.b), rms: g(ranked[0].r!) })}` : "") });
}
