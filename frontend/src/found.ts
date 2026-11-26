/* AU1 (owner, 2026-11-26: "the user cannot guess such a thing exists"): what the app can do by itself with a file,
   found from its signal names - one list, offered in one place (the file panel's *Found in this file* line, the
   file's right-click menu, the palette). Each find names the signals it matched (its *Why?*); the rules live in
   their own modules (desired.ts, objectDetect.ts, templates.ts) - this file only gathers them, plus the two rules of
   its own: truth and navigation of the same platform (AU2) and sensors recorded in several copies (AU3). */
import type { RunInfo, SignalInfo } from "./api";
import { actions, activeTab, useApp, type MapObject, type Plot } from "./store";
import { translate, type TKey } from "./i18n";
import { openTemplateNow } from "./smartStart";
import { getPrefValue, setPref } from "./prefs";
import { openTemplates } from "./templateMenu";
import { addable, candidateObject, byPosition, candidateSource, firstSource, isAdded, objectColors, positionCounts, positionNote, addedSummary } from "./objectAdd";
import { setpointPairs } from "./desired";
import { classOfSegment, detectObjects, type Candidate } from "./objectDetect";
import { effortNames, ENVELOPE_MIN_RUNS, sharedNames } from "./templates";
import { BYTE_COL } from "./messages";

export type FindId = "pairs" | "objects" | "truthnav" | "states" | "copies" | "effort" | "bytes" | "envelope";
export interface Find {
  id: FindId;
  n: number;
  /** what was matched, one line each ("roll_cmd → roll", "truth ↔ ins") - the *Why?* */
  why: string[];
}

const bare = (name: string) => name.replace(/ \[[^\]]*\]$/, "");
const data = (run: Pick<RunInfo, "signals">) => run.signals.filter((s) => !s.labels);

/* ---- AU2: truth and navigation of the same platform ---------------------------------------------- */

/** A prefix without its class words: the platform it belongs to ("uav1.truth" -> "uav1", "6dof" -> ""). */
export function platformOf(prefix: string): string {
  return prefix.split(/[./_]/).filter((s) => s && !["truth", "navigation"].includes(classOfSegment(s) ?? "")).join(".").toLowerCase();
}
/** Each navigation solution with the truth of its platform: the same prefix once the class words are taken out
 *  (`uav1.truth` / `uav1.nav`), or - one truth in the file - that truth for every navigation solution. */
export function truthNavPairs(cands: Candidate[]): { truth: Candidate; nav: Candidate }[] {
  const ok = cands.filter(addable);
  const truths = ok.filter((c) => c.cls === "truth"), navs = ok.filter((c) => c.cls === "navigation");
  const out: { truth: Candidate; nav: Candidate }[] = [];
  for (const nav of navs) {
    const same = truths.find((c) => platformOf(c.prefix) === platformOf(nav.prefix));
    const truth = same ?? (truths.length === 1 ? truths[0] : undefined);
    if (truth) out.push({ truth, nav });
  }
  return out;
}

/* ---- AU3: sensors in several copies ---------------------------------------------------------------- */

/** A group written with a copy number: IMU[1], imu2, gyro_3. */
const INSTANCE = /^(?:(.+?)\[(\d+)\]|(.*[A-Za-z])[_-]?(\d+))$/;
/** Fields every message has (time, its counter, the instance itself): not what makes two groups copies. */
const COMMON = /^(time|timeus|timems|timestamp|t|c|i|id|idx|index|inst|instance)$/i;
export interface CopySet {
  base: string;                   // "IMU", "imu"
  copies: string[];               // "IMU[0]", "IMU[1]"
  fields: { field: string; ids: string[] }[];
}
/** The groups recorded in several copies - the same fields under a group that differs only by its number. A group
 *  numbered without brackets (imu1 / imu2) must share most of its fields with its siblings: XKF1 and XKF2 are
 *  different messages, IMU1 and IMU2 are two sensors. */
export function copySets(signals: Pick<SignalInfo, "id" | "name" | "labels">[]): CopySet[] {
  const groups = new Map<string, { base: string; bracket: boolean; copies: Map<string, Map<string, string>> }>();
  for (const s of signals) {
    if (s.labels) continue;
    const segs = bare(s.name).split(".");
    for (let i = 0; i < segs.length - 1; i++) {
      const m = INSTANCE.exec(segs[i]);
      if (!m) continue;
      const bracket = m[1] !== undefined;
      const base = bracket ? m[1] : m[3];
      const key = [...segs.slice(0, i), `${base}${bracket ? "[#]" : "#"}`].join(".");
      const g = groups.get(key) ?? { base: [...segs.slice(0, i), base].join("."), bracket, copies: new Map() };
      groups.set(key, g);
      const copy = [...segs.slice(0, i + 1)].join(".");
      const fields = g.copies.get(copy) ?? new Map<string, string>();
      g.copies.set(copy, fields);
      fields.set(segs.slice(i + 1).join("."), s.id);
      break;
    }
  }
  const num = (c: string) => Number(/(\d+)\]?$/.exec(c)?.[1] ?? 0);
  const out: CopySet[] = [];
  for (const g of groups.values()) {
    if (g.copies.size < 2) continue;
    const copies = [...g.copies.keys()].sort((a, b) => num(a) - num(b));
    const count = new Map<string, number>();
    for (const f of g.copies.values()) for (const k of f.keys()) if (!COMMON.test(k)) count.set(k, (count.get(k) ?? 0) + 1);
    const shared = [...count].filter(([, n]) => n >= 2).map(([k]) => k);
    if (!shared.length) continue;
    const least = Math.min(...[...g.copies.values()].map((f) => [...f.keys()].filter((k) => !COMMON.test(k)).length || 1));
    if (!g.bracket && (shared.length < 2 || shared.length < 0.6 * least)) continue;
    out.push({ base: g.base, copies, fields: shared.map((field) => ({ field, ids: copies.map((c) => g.copies.get(c)!.get(field)).filter((x): x is string => !!x) })) });
  }
  return out;
}

/* ---- everything found in one file ------------------------------------------------------------------ */

const MAX_WHY = 12;
const cut = (xs: string[]) => (xs.length > MAX_WHY ? [...xs.slice(0, MAX_WHY), `… +${xs.length - MAX_WHY}`] : xs);
const leaf = (id: string) => bare(id.slice(id.indexOf("/") + 1));

/** What the app can do by itself with this file. `onMap`: whether an object candidate is already on a map (it is
 *  then not offered again); `runs`: every open file (the finds of several files: an envelope). */
export function findIn(run: RunInfo, runs: RunInfo[], onMap: (c: Candidate) => boolean = () => false): Find[] {
  const out: Find[] = [];
  const pairs = setpointPairs(data(run).map((s) => s.id));
  if (pairs.length) out.push({ id: "pairs", n: pairs.length, why: cut(pairs.map((p) => `${leaf(p.setpoint)} → ${leaf(p.measured)}`)) });
  const cands = detectObjects(run).candidates.filter(addable);
  const fresh = cands.filter((c) => !onMap(c));
  if (fresh.length) out.push({ id: "objects", n: fresh.length, why: cut(fresh.map((c) => `${c.name} (${[c.picks.lat?.name ?? c.picks.px?.name, c.picks.lon?.name ?? c.picks.py?.name].filter(Boolean).join(", ")})`)) });
  const tn = truthNavPairs(cands);
  if (tn.length) out.push({ id: "truthnav", n: tn.length, why: tn.map((p) => `${p.truth.name} ↔ ${p.nav.name}`) });
  const states = run.signals.filter((s) => s.labels);
  if (states.length) out.push({ id: "states", n: states.length, why: cut(states.map((s) => bare(s.name))) });
  const copies = copySets(run.signals);
  if (copies.length) out.push({ id: "copies", n: copies.length, why: cut(copies.map((c) => `${c.copies.join(" / ")}: ${c.fields.slice(0, 4).map((f) => f.field).join(", ")}${c.fields.length > 4 ? "…" : ""}`)) });
  const effort = effortNames(run);
  if (effort.length) out.push({ id: "effort", n: effort.length, why: cut(effort.map(bare)) });
  const bytes = byteColumns(run);
  if (bytes.length >= 2) out.push({ id: "bytes", n: 1, why: [`${leaf(bytes[0])} … ${leaf(bytes[bytes.length - 1])}`] });
  const files = runs.filter((r) => r.format !== "derived");
  if (files.length >= ENVELOPE_MIN_RUNS) {
    const shared = sharedNames(files, ENVELOPE_MIN_RUNS);
    if (shared.length) out.push({ id: "envelope", n: files.length, why: cut(shared) });
  }
  return out;
}

/** The byte columns of a file (byte_0 … byte_N): one message per row, for Messages. */
export const byteColumns = (run: Pick<RunInfo, "signals">) => data(run).filter((s) => BYTE_COL.test(bare(s.name))).map((s) => s.id);

/* ---- what a click does ------------------------------------------------------------------------------ */

/** The chip's words, by find ({n}: how many). */
export const FIND_LABEL: Record<FindId, TKey> = {
  pairs: "fndPairs", objects: "fndObjects", truthnav: "fndTruthNav", states: "fndStates", copies: "fndCopies",
  effort: "fndEffort", bytes: "fndBytes", envelope: "fndEnvelope",
};

const derivedSignals = () => useApp.getState().runs.find((r) => r.format === "derived")?.signals ?? [];
/** Every map / 3D plot of every tab. */
export const mapPlots = (): Plot[] => useApp.getState().ws.tabs.flatMap((tb) => tb.plots).filter((p) => p.mode === "geo" || p.mode === "3d");
/** The objects not on any map yet (L4: the same first recorded source, through any conversion). */
export const onSomeMap = (c: Candidate) => mapPlots().some((p) => isAdded(c, p, derivedSignals()));
const tabMap = (): Plot | undefined => activeTab(useApp.getState().ws).plots.find((p) => p.mode === "geo" || p.mode === "3d");

function say(text: string, undo = false) {
  const st = useApp.getState();
  st.toast({ kind: "info", text, ...(undo ? { undoesWs: true, action: { label: translate(st.lang, "undo"), run: () => useApp.getState().undo() } } : {}) });
}

/** N5: objects found on a map - the tab's map, a new one when it has none (P2: no position, no object). */
export async function addFoundObjects(cands: Candidate[]): Promise<{ plotId: string | null; left: boolean }> {
  const st = useApp.getState();
  const next = objectColors(tabMap());
  const { keep, none, few } = byPosition(cands, await positionCounts(cands));
  const note = positionNote(none, few, st.lang);
  if (!keep.length) { if (note) say(note); return { plotId: null, left: true }; }
  const objs: MapObject[] = [];
  for (const c of keep) objs.push(await candidateObject(c, next()));
  const id = actions.addObjectsToMaps(objs);
  if (id) say(addedSummary(keep, st.lang) + (note ? ` ${note}` : ""), true);
  return { plotId: id, left: none.length > 0 };       // left: what stays in the file has no position
}

/** AU2: truth and navigation on a map (added when missing), the truth the reference, the navigation solution the
 *  compared one, and *Compare objects…* opened on them. */
export async function compareTruthNav(pair: { truth: Candidate; nav: Candidate }) {
  const missing = [pair.truth, pair.nav].filter((c) => !isAdded(c, tabMap(), derivedSignals()));
  const plotId = missing.length ? (await addFoundObjects(missing)).plotId : tabMap()?.id ?? null;
  const plot = plotId ? useApp.getState().ws.tabs.flatMap((tb) => tb.plots).find((p) => p.id === plotId) : null;
  if (!plot) return;
  const idOf = (c: Candidate) => plot.objects?.find((o) => firstSource(o, derivedSignals()) === candidateSource(c))?.id;
  const P = idOf(pair.truth), S = idOf(pair.nav);
  if (!P || !S) return;
  actions.setObjectPair(plot.id, P, S);
  useApp.setState({ compareDialog: { plotId: plot.id }, compareOffer: null });
}

/** Mode signals as lanes: on the tab's time plots when it has some, else a tab of their own. */
function showStates(ids: string[], name: string) {
  const tab = activeTab(useApp.getState().ws);
  if (tab.plots.some((p) => (!p.mode || p.mode === "time") && p.signals.length)) {
    useApp.getState().commit((ws) => {
      const tb = activeTab(ws);
      tb.sharedStates = [...new Set([...(tb.sharedStates ?? []), ...ids])];
      return ws;
    });
  } else actions.plotSignalsInNewTab(ids, name);
}

async function template(id: string) { if (!(await openTemplateNow(id))) openTemplates(id); }

/** Do what the find offers, on this file. */
export async function runFind(id: FindId, run: RunInfo) {
  const st = useApp.getState();
  const L = st.lang;
  try {
    if (id === "pairs") actions.plotSetpointPairs(run.id);
    else if (id === "objects") await addFoundObjects(detectObjects(run).candidates.filter((c) => addable(c) && !onSomeMap(c)));
    else if (id === "truthnav") { const p = truthNavPairs(detectObjects(run).candidates)[0]; if (p) await compareTruthNav(p); }
    else if (id === "states") showStates(run.signals.filter((s) => s.labels).map((s) => s.id), translate(L, "fndStatesTab"));
    else if (id === "copies") {
      const sets = copySets(run.signals);
      actions.plotTabs([{ name: translate(L, "fndCopiesTab"), plots: sets.flatMap((c) => c.fields.map((f) => ({ title: `${c.base} · ${f.field}`, ids: f.ids }))).slice(0, 24) }]);
    }
    else if (id === "effort") await template("bi-effort");
    else if (id === "envelope") await template("bi-envelope");
    else if (id === "bytes") useApp.setState({ panel: "messages", msgFocus: { ids: byteColumns(run) } });
  } catch (e) { st.toast({ kind: "error", text: String((e as Error).message) }); }
}

/* ---- dismissed and used -------------------------------------------------------------------------- */

const PREF = "sv3.foundHidden";
export const foundHidden = (): string[] => getPrefValue<string[]>(PREF) ?? [];
export function hideFound(run: Pick<RunInfo, "id" | "name">) {
  setPref(PREF, [...new Set([...foundHidden(), run.name])].slice(-200));
  useApp.setState((s) => ({ objSuggestHidden: [...s.objSuggestHidden, run.id] }));
}
/** A find is used: its chip goes for this file (this run of the app). */
export const markFound = (runId: string, id: FindId) => useApp.setState((s) => ({ foundDone: [...s.foundDone, `${runId}:${id}`] }));

