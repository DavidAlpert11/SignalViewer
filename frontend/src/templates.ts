import type { RunInfo, Template, TplObject, TplObjectRole, TplPlot, TplSlot, TplTab } from "./api";
import { fileLabel, nextColor, uid, useApp, type MapObject, type ObjectKind, type Plot, type Tab } from "./store";
import { translate } from "./i18n";
import { guessRoles } from "./mapObjects";

const OBJ_ROLES: TplObjectRole[] = ["lat", "lon", "alt", "yaw", "pitch", "roll", "qw", "qx", "qy", "qz"];

/* ============================================================================ templates
   A template is a set of tabs; each plotted signal is stored by NAME together with the file SLOT it
   comes from ("File", or e.g. "Autopilot log" + "Telemetry"). Opening a template gives every slot an
   open file - suggested automatically from how many of the slot's signals each file has - or "all
   files that fit" (to overlay them). A template may include other templates by reference: a
   collection, which opens all their tabs (slots with the same id are the same file). */

export const ALL = "*all";                  // slot binding: every open file that has the signal
const nameOf = (sig: string) => sig.slice(sig.indexOf("/") + 1);
const runOf = (sig: string) => sig.slice(0, sig.indexOf("/"));

/* Names match exactly first; otherwise without the unit and the instance number ("ATT.Roll" finds
   "ATT.Roll [deg]", "IMU.AccX" finds "IMU[0].AccX [m/s/s]"), and a name may list alternatives:
   "XKF4.SV|NKF4.SV" (EKF3, else EKF2). */
const bare = (n: string) => n.replace(/ \[[^\]]*\]$/, "").replace(/^([^.[]+)\[\d+\]\./, "$1.");

/* A file's names, indexed once (exact set + bare name -> first name in sorted order) and reused
   for as long as the file's signal list is the same object: with hundreds of templates and
   thousands of signals, matching every name against every name each time froze the UI. */
interface NameIndex { exact: Set<string>; bare: Map<string, string> }
const indexOf = (names: string[]): NameIndex => {
  const exact = new Set(names);
  const b = new Map<string, string>();
  for (const n of names) {
    const k = bare(n);
    const cur = b.get(k);
    if (cur === undefined || n < cur) b.set(k, n);
  }
  return { exact, bare: b };
};
const runIndex = new WeakMap<RunInfo["signals"], NameIndex>();
const indexOfRun = (run: RunInfo): NameIndex => {
  let ix = runIndex.get(run.signals);
  if (!ix) { ix = indexOf(run.signals.map((x) => x.name)); runIndex.set(run.signals, ix); }
  return ix;
};
const matchIn = (ix: NameIndex, wanted: string): string | null => {
  for (const alt of wanted.split("|")) {
    if (ix.exact.has(alt)) return alt;
    const hit = ix.bare.get(bare(alt));
    if (hit !== undefined) return hit;
  }
  return null;
};
export function matchSignal(names: string[], wanted: string): string | null {
  return matchIn(indexOf(names), wanted);
}
/** matchSignal against an open file, using its cached index. */
export const matchSignalInRun = (run: RunInfo, wanted: string): string | null => matchIn(indexOfRun(run), wanted);

/** "@key" -> its translation (built-in templates' texts), anything else as it is. */
export function tx(s: string | undefined, lang = useApp.getState().lang): string {
  if (!s) return "";
  return s.startsWith("@") ? translate(lang, s.slice(1) as "tplApAtt") : s;
}

/* --------------------------------------------------------------- capture from the workspace */
/** A tab's name for a template: its own name; if it never got one, what it shows (the first plot
 *  titles, else the first signals), so a template is not saved as "Tab 1". */
export function suggestTabName(tab: Tab, index: number, lang = useApp.getState().lang): string {
  const own = (tab.name || "").trim();
  if (own) return own;
  const titles = tab.plots.map((p) => (p.title || "").trim()).filter(Boolean);
  if (titles.length) return titles.slice(0, 2).join(", ") + (titles.length > 2 ? "…" : "");
  const sigs = Array.from(new Set(tab.plots.flatMap((p) => p.signals.map((x) => (x.label || nameOf(x.sig)).replace(/ \[[^\]]*\]$/, "")))));
  if (sigs.length) return sigs.slice(0, 2).join(", ") + (sigs.length > 2 ? "…" : "");
  const objs = Array.from(new Set(tab.plots.flatMap((p) => (p.objects ?? []).map((o) => o.name))));
  if (objs.length) return objs.slice(0, 2).join(", ") + (objs.length > 2 ? "…" : "");
  return `${translate(lang, "tab")} ${index + 1}`;
}

/** Tabs of the workspace -> a template. Each file used becomes a slot (one file: a single slot
 *  "File"), so the template can later be given other files of the same kind. Formula signals
 *  belong to the session and are left out. */
export function templateFromTabs(tabs: Tab[], name: string): { template: Template; skipped: number; slotRuns: Record<string, string> } {
  const st = useApp.getState();
  const used: string[] = [];
  let skipped = 0;
  const note = (sig: string) => { const r = runOf(sig); if (r !== "derived" && !used.includes(r)) used.push(r); };
  tabs.forEach((t) => t.plots.forEach((p) => {
    p.signals.forEach((s) => note(s.sig)); if (p.xSignal) note(p.xSignal);
    (p.objects ?? []).forEach((o) => OBJ_ROLES.forEach((k) => { if (o[k]) note(o[k]!); }));
  }));
  tabs.forEach((t) => (t.sharedStates ?? []).forEach(note));
  const slotOf = new Map<string, string>();
  const slots: TplSlot[] = used.map((rid, i) => {
    const run = st.runs.find((r) => r.id === rid);
    const id = used.length === 1 ? "main" : `f${i + 1}`;
    slotOf.set(rid, id);
    // named after its file, and remembers it: opening the template later finds the same file by name
    const file = run ? baseName(run.path) : undefined;
    return { id, name: file ?? fileLabel(st.runs, rid), formats: run ? [run.format] : undefined,
      ...(file ? { file } : {}), ...(run && !run.copy ? { path: run.path } : {}) };
  });
  if (!slots.length) slots.push({ id: "main", name: "@tplSlotFile" });
  const keep = (sig: string) => { if (runOf(sig) === "derived") { skipped++; return false; } return true; };
  const tplTabs: TplTab[] = tabs.map((tab, k) => ({
    name: suggestTabName(tab, st.ws.tabs.indexOf(tab) >= 0 ? st.ws.tabs.indexOf(tab) : k, st.lang), rows: tab.rows, cols: tab.cols, rowSizes: tab.rowSizes, colSizes: tab.colSizes,
    linkX: tab.linkX, linkY: tab.linkY,
    ...(tab.sharedStates?.length ? { lanes: tab.sharedStates.filter(keep).map((id) => ({ name: nameOf(id), slot: slotOf.get(runOf(id)) })) } : {}),
    plots: tab.plots.map((p): TplPlot => ({
      title: p.title, mode: p.mode, xSignal: p.xSignal && keep(p.xSignal) ? nameOf(p.xSignal) : null,
      ...(p.xSignal ? { xSlot: slotOf.get(runOf(p.xSignal)) } : {}), xyAlign: p.xyAlign, fftWindow: p.fftWindow, fftMethod: p.fftMethod,
      fftLog: p.fftLog, specN: p.specN, caption: p.caption, ylim: p.ylim ?? null,
      signals: p.signals.filter((s) => keep(s.sig)).map((s) => ({ name: nameOf(s.sig), slot: slotOf.get(runOf(s.sig)), color: s.color,
        width: s.width, scale: s.scale, offset: s.offset, state: s.state, tOffset: s.tOffset, label: s.label,
        ...(s.limits ? { limits: s.limits } : {}) })),
      ...(p.objects?.length ? { objects: p.objects.map((o): TplObject => ({
        name: o.name, kind: o.kind, color: o.color, angleUnit: o.angleUnit, altRef: o.altRef, trail: o.trail, size: o.size,
        roles: Object.fromEntries(OBJ_ROLES.filter((k) => o[k] && keep(o[k]!)).map((k) => [k, { name: nameOf(o[k]!), slot: slotOf.get(runOf(o[k]!)) }])),
      })) } : {}),
    })),
  }));
  const slotRuns: Record<string, string> = {};
  slotOf.forEach((slot, rid) => { slotRuns[slot] = rid; });
  return { template: { version: 2, id: "", name, slots, tabs: tplTabs }, skipped, slotRuns };
}

/* --------------------------------------------------------------- collections */
export interface Expanded { slots: TplSlot[]; tabs: (TplTab & { from: string })[]; missing: string[]; generators: Template[] }

/** A template with its included templates (recursively, each once; a loop is cut). */
export function expand(t: Template, all: Template[], seen = new Set<string>()): Expanded {
  const out: Expanded = { slots: [...t.slots], tabs: t.tabs.map((x) => ({ ...x, from: t.name })), missing: [], generators: t.generator ? [t] : [] };
  seen.add(t.id);
  for (const id of t.includes ?? []) {
    const inc = all.find((x) => x.id === id);
    if (!inc) { out.missing.push(id); continue; }
    if (seen.has(id)) continue;
    const e = expand(inc, all, seen);
    for (const s of e.slots) if (!out.slots.some((x) => x.id === s.id)) out.slots.push(s);
    out.tabs.push(...e.tabs);
    out.missing.push(...e.missing);
    out.generators.push(...e.generators);
  }
  return out;
}

/** Templates that include `id` (directly or through others) - it cannot include them back. */
export function includers(id: string, all: Template[]): Set<string> {
  const out = new Set<string>([id]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const t of all) if (!out.has(t.id) && (t.includes ?? []).some((i) => out.has(i))) { out.add(t.id); grew = true; }
  }
  return out;
}

/* --------------------------------------------------------------- slots -> files */
const slotOfSignal = (slot: string | undefined, slots: TplSlot[]) => slot ?? slots[0]?.id ?? "main";

/** The signal names a slot asks for, over the given tabs. */
export function slotNames(slotId: string, slots: TplSlot[], tabs: TplTab[]): string[] {
  const out: string[] = [];
  for (const tab of tabs) {
    for (const p of tab.plots) {
      for (const s of p.signals) if (slotOfSignal(s.slot, slots) === slotId) out.push(s.name);
      if (p.xSignal && slotOfSignal(p.xSlot, slots) === slotId) out.push(p.xSignal);
      for (const o of p.objects ?? []) for (const r of Object.values(o.roles)) if (r && slotOfSignal(r.slot, slots) === slotId) out.push(r.name);
    }
  }
  return Array.from(new Set(out));
}

const dataRuns = (runs: RunInfo[]) => runs.filter((r) => r.format !== "derived");
export const baseName = (p: string) => p.split(/[\\/]/).pop() || p;

/** The open file with the same name as the one the slot was saved from (and that has some of its signals). */
export function sameNameRun(slot: TplSlot, names: string[], runs: RunInfo[], taken = new Set<string>()): RunInfo | null {
  if (!slot.file) return null;
  const want = slot.file.toLowerCase();
  return dataRuns(runs).find((r) => !taken.has(r.id) && baseName(r.path).toLowerCase() === want
    && (!names.length || matchCount(r, names) > 0)) ?? null;
}

/** How many of the names a file has (alternatives and loose matching included). */
export function matchCount(run: RunInfo, names: string[]): number {
  const ix = indexOfRun(run);
  return names.filter((n) => matchIn(ix, n)).length;
}

/** A file for every slot: the one that has most of the slot's signals (a preferred format breaks ties),
 *  each file used once while others are left; generators: their own rule. prefer: a file to favour. */
export function autoBind(e: Expanded, runs: RunInfo[], prefer?: string | null): Record<string, string> {
  const data = dataRuns(runs);
  const bind: Record<string, string> = {};
  const taken = new Set<string>();
  for (const g of e.generators) {
    if (g.generator === "compare") bind[g.slots[0].id] = ALL;
  }
  const order = [...e.slots].sort((a, b) => slotNames(b.id, e.slots, e.tabs).length - slotNames(a.id, e.slots, e.tabs).length);
  // first: the same file as when the template was saved (same name, open, has its signals)
  for (const s of order) {
    if (bind[s.id]) continue;
    const same = sameNameRun(s, slotNames(s.id, e.slots, e.tabs), runs, taken);
    if (same) { bind[s.id] = same.id; taken.add(same.id); }
  }
  // then: for the others, the open file that has most of their signals
  for (const s of order) {
    if (bind[s.id]) continue;
    const names = slotNames(s.id, e.slots, e.tabs);
    let best: RunInfo | null = null, bestScore = -1;
    for (const r of data) {
      const share = names.length ? matchCount(r, names) / names.length : 0.5;
      const score = share + (s.formats?.includes(r.format) ? 0.25 : 0) + (r.id === prefer ? 0.3 : 0) - (taken.has(r.id) ? 1 : 0);
      if (score > bestScore) { bestScore = score; best = r; }
    }
    if (best && (bestScore > 0 || !names.length)) { bind[s.id] = best.id; taken.add(best.id); } else bind[s.id] = "";
  }
  return bind;
}

/** 0..1: how well the open files fit a template (for the list). */
export function fit(t: Template, all: Template[], runs: RunInfo[]): number {
  const data = dataRuns(runs);
  if (!data.length) return 0;
  const e = expand(t, all);
  if (e.generators.length && !e.tabs.length) {
    // "position on the map" fits only when a file has latitude and longitude signals
    if (e.generators.every((g) => g.generator === "objects")) return data.some((r) => { const g = guessRoles(r); return !!(g.lat && g.lon); }) ? 1 : 0;
    return 1;
  }
  let found = 0, total = 0;
  const bind = autoBind(e, runs);
  for (const s of e.slots) {
    const names = slotNames(s.id, e.slots, e.tabs);
    const runsFor = bind[s.id] === ALL ? data : data.filter((r) => r.id === bind[s.id]);
    total += names.length;
    found += runsFor.length ? Math.max(...runsFor.map((r) => matchCount(r, names))) : 0;
  }
  return total ? found / total : 0;
}

/* --------------------------------------------------------------- generators (built-in, any file) */
const PER_TAB = 4;
/** "Position on the map & 3D": the file's position (and attitude) signals, found by their names, as an
 *  object on a map and in the 3D view. */
function objectTabs(run: RunInfo | undefined, slot: string, lang: "en" | "he"): TplTab[] {
  if (!run) return [];
  const g = guessRoles(run);
  if (!g.lat || !g.lon) return [];
  const bare = (id?: string) => (id ? id.slice(id.indexOf("/") + 1) : undefined);
  const roles = Object.fromEntries(OBJ_ROLES.filter((k) => g[k]).map((k) => [k, { name: bare(g[k])!, slot }]));
  const obj: TplObject = { name: run.name.replace(/\.[^.]+$/, ""), kind: "aircraft", color: "#E5534B", roles };
  return [{ name: translate(lang, "tplObjTab"), rows: 1, cols: 2, linkX: false, plots: [
    { title: translate(lang, "modeGeo"), mode: "geo", signals: [], objects: [obj] },
    { title: translate(lang, "mode3d"), mode: "3d", signals: [], objects: [obj] }] }];
}

function quickLookTabs(run: RunInfo | undefined, slot: string, lang: "en" | "he"): TplTab[] {
  if (!run) return [];
  const lines = run.signals.filter((s) => !s.labels).map((s) => s.name);
  const states = run.signals.filter((s) => s.labels).map((s) => s.name).slice(0, 2);
  const tabs: TplTab[] = [];
  for (let i = 0; i < Math.min(lines.length, PER_TAB * 12); i += PER_TAB) {
    const part = lines.slice(i, i + PER_TAB);
    tabs.push({ name: `${translate(lang, "tplQuickTab")} ${tabs.length + 1}`, rows: part.length, cols: 1, linkX: true,
      lanes: states.map((n) => ({ name: n, slot })), plots: part.map((n) => ({ title: n, signals: [{ name: n, slot }] })) });
  }
  return tabs;
}
function compareTabs(runs: RunInfo[], slot: string, lang: "en" | "he"): TplTab[] {
  const data = dataRuns(runs);
  const count = new Map<string, number>();
  data.forEach((r) => new Set(r.signals.filter((s) => !s.labels).map((s) => bare(s.name))).forEach((n) => count.set(n, (count.get(n) ?? 0) + 1)));
  const common = Array.from(count).filter(([, c]) => c >= 2).map(([n]) => n);
  const tabs: TplTab[] = [];
  for (let i = 0; i < Math.min(common.length, PER_TAB * 10); i += PER_TAB) {
    const part = common.slice(i, i + PER_TAB);
    tabs.push({ name: `${translate(lang, "tplCompareTab")} ${tabs.length + 1}`, rows: part.length, cols: 1, linkX: true,
      plots: part.map((n) => ({ title: n, signals: [{ name: n, slot }] })) });
  }
  return tabs;
}

/* --------------------------------------------------------------- open a template */
export interface ApplyResult { tabs: number; plots: number; dropped: string[]; missing: string[] }

/** Open a template's tabs (or only those chosen, by index into the expanded tabs) with these files. */
export function applyTemplate(t: Template, all: Template[], bind: Record<string, string>, chosen?: number[]): ApplyResult {
  const st = useApp.getState();
  const L = st.lang;
  const e = expand(t, all);
  let tabs = e.tabs.filter((_x, i) => !chosen || chosen.includes(i));
  for (const g of e.generators) {
    const slot = g.slots[0].id;
    tabs = [...tabs, ...(g.generator === "quicklook" ? quickLookTabs(st.runs.find((r) => r.id === bind[slot]), slot, L)
      : g.generator === "objects" ? objectTabs(st.runs.find((r) => r.id === bind[slot]), slot, L)
      : compareTabs(st.runs, slot, L)).map((x) => ({ ...x, from: g.name }))];
  }
  const data = dataRuns(st.runs);
  const missing = new Set<string>();
  const ids = (name: string, slot: string | undefined) => {
    const b = bind[slotOfSignal(slot, e.slots)];
    const files = b === ALL ? data : data.filter((r) => r.id === b);
    const out = files.flatMap((r) => { const hit = matchSignalInRun(r, name); return hit ? [`${r.id}/${hit}`] : []; });
    if (!out.length) missing.add(name.split("|")[0]);
    return out;
  };
  const res: ApplyResult = { tabs: 0, plots: 0, dropped: [], missing: [] };
  let firstNew: string | null = null;
  st.commit((ws) => {
    // the workspace is just the empty starting tab: the template's tabs replace it
    const emptyStart = ws.tabs.length === 1 && ws.tabs[0].plots.every((p) => !p.signals.length && !p.objects?.length);
    const before = ws.tabs.length;
    for (const tt of tabs) {
      const plots: Plot[] = [];
      for (const tp of tt.plots) {
        const p: Plot = { id: uid("p"), title: tp.title, signals: [], mode: (tp.mode as Plot["mode"]) ?? "time",
          xyAlign: tp.xyAlign as Plot["xyAlign"], fftWindow: tp.fftWindow as Plot["fftWindow"], fftMethod: tp.fftMethod as Plot["fftMethod"], fftLog: tp.fftLog, specN: tp.specN,
          caption: tp.caption, ylim: tp.ylim ?? null };
        if (tp.xSignal) p.xSignal = ids(tp.xSignal, tp.xSlot)[0] ?? null;
        tp.signals.forEach((s) => {
          const got = ids(s.name, s.slot);
          for (const id of got) {
            p.signals.push({ sig: id, color: s.color && got.length === 1 ? s.color : nextColor(ws), width: s.width ?? 1.5,
              scale: s.scale ?? 1, offset: s.offset ?? 0, state: s.state, tOffset: s.tOffset, label: got.length === 1 ? s.label : undefined,
              ...(s.limits ? { limits: s.limits } : {}) });
          }
        });
        // objects: each signal found by name in its slot's file; one without its position is left out
        for (const to of tp.objects ?? []) {
          const roleId = (k: TplObjectRole) => { const r = to.roles[k]; return r ? ids(r.name, r.slot)[0] ?? null : null; };
          const lat = roleId("lat"), lon = roleId("lon");
          if (!lat || !lon) continue;
          const o: MapObject = { id: uid("o"), name: to.name, kind: (to.kind as ObjectKind) ?? "aircraft", color: to.color ?? nextColor(ws), lat, lon,
            alt: roleId("alt"), yaw: roleId("yaw"), pitch: roleId("pitch"), roll: roleId("roll"),
            qw: roleId("qw"), qx: roleId("qx"), qy: roleId("qy"), qz: roleId("qz"),
            angleUnit: to.angleUnit as MapObject["angleUnit"], altRef: to.altRef as MapObject["altRef"], trail: to.trail, size: to.size };
          p.objects = [...(p.objects ?? []), o];
        }
        if (p.signals.some((x) => !x.state) || (p.mode === "geo" && p.xSignal && p.signals.length) || p.objects?.length) plots.push(p);
        else res.dropped.push(`${tt.name} › ${tp.title}`);
      }
      if (!plots.length) continue;
      const lanes = (tt.lanes ?? []).flatMap((l) => ids(l.name, l.slot).slice(0, 2));
      const rows = plots.length < tt.plots.length ? Math.max(1, Math.ceil(plots.length / tt.cols)) : tt.rows;
      const tab: Tab = { id: uid("t"), name: tt.name, rows, cols: tt.cols, rowSizes: rows === tt.rows ? tt.rowSizes : undefined,
        colSizes: tt.colSizes, plots, active: 0, linkX: tt.linkX ?? true, linkY: tt.linkY, ...(lanes.length ? { sharedStates: lanes } : {}) };
      ws.tabs.push(tab);
      firstNew ??= tab.id;
      res.tabs++; res.plots += plots.length;
    }
    if (firstNew) {
      ws.activeTab = firstNew;
      if (emptyStart && ws.tabs.length > before) ws.tabs = ws.tabs.slice(1);
    }
    return ws;
  });
  res.missing = Array.from(missing);
  return res;
}

/* ============================================================================ built-in templates */
const C = ["#3D8BFD", "#F2A93B", "#4CC38A", "#E5534B", "#B083F0", "#39C5CF", "#F778BA", "#8B949E"];
const sig = (name: string, i: number, extra: Record<string, unknown> = {}) => ({ name, color: C[i % C.length], width: 1.5, ...extra });
const P = (title: string, names: string[], extra: Partial<TplPlot> = {}): TplPlot => ({ title, signals: names.map((n, i) => sig(n, i)), ...extra });
const tab1 = (name: string, rows: number, cols: number, plots: TplPlot[], lanes?: { name: string; slot?: string }[]): TplTab =>
  ({ name, rows, cols, linkX: true, plots, ...(lanes ? { lanes } : {}) });
const one = (id: string, group: string, name: string, desc: string, slot: TplSlot, tab: TplTab): Template =>
  ({ version: 2, id, name, description: desc, group, builtin: true, slots: [slot], tabs: [tab] });

const AP: TplSlot = { id: "main", name: "@tplSlotAp", formats: ["bin"] };
const MAV: TplSlot = { id: "main", name: "@tplSlotTl", formats: ["tlog"] };
const PX4: TplSlot = { id: "main", name: "@tplSlotPx4", formats: ["ulg"] };
const AP_L = [{ name: "MODE.Mode" }], MAV_L = [{ name: "HEARTBEAT.custom_mode" }], PX4_L = [{ name: "vehicle_status.nav_state" }];

const apAtt = one("bi-ap-attitude", "ardupilot", "ArduPilot · Attitude", "@tplApAtt", AP, tab1("Attitude", 3, 1, [
  P("Roll", ["ATT.DesRoll", "ATT.Roll"]), P("Pitch", ["ATT.DesPitch", "ATT.Pitch"]), P("Yaw", ["ATT.DesYaw", "ATT.Yaw"])], AP_L));
const apRate = one("bi-ap-rates", "ardupilot", "ArduPilot · Rates (PID)", "@tplApRate", AP, tab1("Rates", 3, 1, [
  P("Roll rate", ["RATE.RDes", "RATE.R"]), P("Pitch rate", ["RATE.PDes", "RATE.P"]), P("Yaw rate", ["RATE.YDes", "RATE.Y"])], AP_L));
const apVibe = one("bi-ap-vibration", "ardupilot", "ArduPilot · Vibration", "@tplApVibe", AP, tab1("Vibration", 3, 1, [
  P("Vibration", ["VIBE.VibeX", "VIBE.VibeY", "VIBE.VibeZ"]), P("Clipping", ["VIBE.Clip|VIBE.Clip0", "VIBE.Clip1", "VIBE.Clip2"]),
  P("IMU Z spectrogram", ["IMU.AccZ"], { mode: "spec", specN: 1024 })], AP_L));
const apBatt = one("bi-ap-battery", "ardupilot", "ArduPilot · Battery & power", "@tplApBatt", AP, tab1("Battery", 2, 2, [
  P("Voltage", ["BAT.Volt|BATT.Volt|CURR.Volt"]), P("Current", ["BAT.Curr|BATT.Curr|CURR.Curr"]),
  P("Used (mAh)", ["BAT.CurrTot|BATT.CurrTot|CURR.CurrTot"]), P("Board / servo power", ["POWR.Vcc", "POWR.VServo"])], AP_L));
const apGps = one("bi-ap-gps", "ardupilot", "ArduPilot · GPS", "@tplApGps", AP, tab1("GPS", 2, 2, [
  P("Satellites & HDop", ["GPS.NSats", "GPS.HDop"]), P("Altitude", ["GPS.Alt", "BARO.Alt", "CTUN.Alt"]),
  P("Ground speed", ["GPS.Spd"]), P("Track", ["GPS.Lat"], { mode: "geo", xSignal: "GPS.Lng" })], AP_L));
const apMot = one("bi-ap-motors", "ardupilot", "ArduPilot · Motors & RC", "@tplApMot", AP, tab1("Motors", 2, 1, [
  P("Motor outputs", ["RCOU.C1", "RCOU.C2", "RCOU.C3", "RCOU.C4"]), P("RC inputs", ["RCIN.C1", "RCIN.C2", "RCIN.C3", "RCIN.C4"])], AP_L));
const apAlt = one("bi-ap-altitude", "ardupilot", "ArduPilot · Altitude", "@tplApAlt", AP, tab1("Altitude", 2, 1, [
  P("Altitude", ["CTUN.DAlt", "CTUN.Alt", "CTUN.BAlt"]), P("Climb rate", ["CTUN.DCRt", "CTUN.CRt"])], AP_L));
// EKF3 (XKF), EKF2 (NKF), and the EKF of ArduPilot 3.3 and older (EKF4 / EKF3, magnetometer as SMX)
const apEkf = one("bi-ap-ekf", "ardupilot", "ArduPilot · EKF", "@tplApEkf", AP, tab1("EKF", 2, 1, [
  P("Variances", ["XKF4.SV|NKF4.SV|EKF4.SV", "XKF4.SP|NKF4.SP|EKF4.SP", "XKF4.SH|NKF4.SH|EKF4.SH", "XKF4.SM|NKF4.SM|NKF4.SMX|EKF4.SMX"]),
  P("Innovations (velocity)", ["XKF3.IVN|NKF3.IVN|EKF3.IVN", "XKF3.IVE|NKF3.IVE|EKF3.IVE", "XKF3.IVD|NKF3.IVD|EKF3.IVD"])], AP_L));

const mavAtt = one("bi-mav-attitude", "mavlink", "MAVLink · Attitude", "@tplMavAtt", MAV, tab1("Attitude", 3, 1, [
  P("Roll", ["ATTITUDE.roll"]), P("Pitch", ["ATTITUDE.pitch"]), P("Yaw", ["ATTITUDE.yaw"])], MAV_L));
const mavBatt = one("bi-mav-battery", "mavlink", "MAVLink · Battery & GPS", "@tplMavBatt", MAV, tab1("Battery & GPS", 2, 2, [
  P("Battery", ["SYS_STATUS.voltage_battery"]), P("Current", ["BATTERY_STATUS.current_battery|SYS_STATUS.current_battery"]),
  P("Satellites", ["GPS_RAW_INT.satellites_visible"]), P("Track", ["GPS_RAW_INT.lat"], { mode: "geo", xSignal: "GPS_RAW_INT.lon" })], MAV_L));
const mavVibe = one("bi-mav-vibration", "mavlink", "MAVLink · Vibration", "@tplMavVibe", MAV, tab1("Vibration", 2, 1, [
  P("Vibration", ["VIBRATION.vibration_x", "VIBRATION.vibration_y", "VIBRATION.vibration_z"]),
  P("Clipping", ["VIBRATION.clipping_0", "VIBRATION.clipping_1", "VIBRATION.clipping_2"])], MAV_L));
const mavLink = one("bi-mav-link", "mavlink", "MAVLink · Radio link", "@tplMavLink", MAV, tab1("Radio link", 2, 1, [
  P("Signal strength", ["RADIO_STATUS.rssi", "RADIO_STATUS.remrssi", "RADIO_STATUS.noise", "RADIO_STATUS.remnoise"]),
  P("Errors & buffer", ["RADIO_STATUS.rxerrors", "RADIO_STATUS.fixed", "RADIO_STATUS.txbuf"])], MAV_L));
const px4Batt = one("bi-px4-battery", "px4", "PX4 · Battery & GPS", "@tplPx4Batt", PX4, tab1("Battery & GPS", 2, 2, [
  P("Battery", ["battery_status.voltage_v"]), P("Current", ["battery_status.current_a"]),
  P("Satellites", ["vehicle_gps_position.satellites_used|sensor_gps.satellites_used"]),
  P("Track", ["vehicle_gps_position.lat|sensor_gps.lat"], { mode: "geo", xSignal: "vehicle_gps_position.lon|sensor_gps.lon" })], PX4_L));

// a flight on the map and in 3D: the vehicle as an object (position + attitude by name)
const obj = (name: string, roles: Partial<Record<TplObjectRole, string>>): TplObject =>
  ({ name, kind: "aircraft", color: C[3], roles: Object.fromEntries(Object.entries(roles).map(([k, n]) => [k, { name: n as string }])) });
const flightTab = (o: TplObject): TplTab => ({ name: "Flight", rows: 1, cols: 2, linkX: false, plots: [
  { title: "Map", mode: "geo", signals: [], objects: [o] }, { title: "3D", mode: "3d", signals: [], objects: [o] }] });
const apFlight = one("bi-ap-flight", "ardupilot", "ArduPilot · Flight on the map & 3D", "@tplApFlight", AP, flightTab(obj("Vehicle", {
  lat: "GPS.Lat|POS.Lat", lon: "GPS.Lng|POS.Lng", alt: "GPS.Alt|POS.Alt", yaw: "ATT.Yaw", pitch: "ATT.Pitch", roll: "ATT.Roll" })));
const mavFlight = one("bi-mav-flight", "mavlink", "MAVLink · Flight on the map & 3D", "@tplMavFlight", MAV, flightTab(obj("Vehicle", {
  lat: "GLOBAL_POSITION_INT.lat|GPS_RAW_INT.lat", lon: "GLOBAL_POSITION_INT.lon|GPS_RAW_INT.lon", alt: "GLOBAL_POSITION_INT.alt|GPS_RAW_INT.alt",
  yaw: "ATTITUDE.yaw", pitch: "ATTITUDE.pitch", roll: "ATTITUDE.roll" })));
// PX4 logs the attitude only as a quaternion
const px4Flight = one("bi-px4-flight", "px4", "PX4 · Flight on the map & 3D", "@tplPx4Flight", PX4, flightTab(obj("Vehicle", {
  lat: "vehicle_global_position.lat|vehicle_gps_position.lat|sensor_gps.lat", lon: "vehicle_global_position.lon|vehicle_gps_position.lon|sensor_gps.lon",
  alt: "vehicle_global_position.alt|sensor_gps.altitude_msl_m|vehicle_gps_position.alt",
  qw: "vehicle_attitude.q[0]", qx: "vehicle_attitude.q[1]", qy: "vehicle_attitude.q[2]", qz: "vehicle_attitude.q[3]" })));

// the autopilot's log and the telemetry of the same flight, on top of each other (57.29578: rad -> deg)
const SAP: TplSlot = { id: "ap", name: "@tplSlotAp", formats: ["bin", "ulg"] };
const STL: TplSlot = { id: "tl", name: "@tplSlotTl", formats: ["tlog"] };
const both = (title: string, ap: string, tl: string, scale = 1): TplPlot => ({ title, signals: [
  { name: ap, slot: "ap", color: C[0], width: 3 }, { name: tl, slot: "tl", color: C[3], width: 1.5, scale }] });
const PAIR_L = [{ name: "MODE.Mode", slot: "ap" }, { name: "HEARTBEAT.custom_mode", slot: "tl" }];
const pairAtt: Template = { version: 2, id: "bi-pair-attitude", group: "compare", builtin: true, name: "Autopilot log vs telemetry · Attitude & altitude",
  description: "@tplPairAtt", slots: [SAP, STL], tabs: [tab1("Attitude & altitude", 3, 1, [
    both("Roll (deg)", "ATT.Roll", "ATTITUDE.roll", 57.29578), both("Pitch (deg)", "ATT.Pitch", "ATTITUDE.pitch", 57.29578),
    both("Altitude", "CTUN.Alt|BARO.Alt", "VFR_HUD.alt|GLOBAL_POSITION_INT.relative_alt")], PAIR_L)] };
const pairBatt: Template = { version: 2, id: "bi-pair-battery", group: "compare", builtin: true, name: "Autopilot log vs telemetry · Battery, GPS & link",
  description: "@tplPairBatt", slots: [SAP, STL], tabs: [tab1("Battery, GPS & link", 2, 2, [
    both("Battery voltage", "BAT.Volt|BATT.Volt|CURR.Volt", "SYS_STATUS.voltage_battery"),
    both("GPS satellites", "GPS.NSats", "GPS_RAW_INT.satellites_visible"), both("Ground speed", "GPS.Spd", "VFR_HUD.groundspeed"),
    { title: "Radio link (telemetry)", signals: [{ name: "RADIO_STATUS.rssi", slot: "tl" }, { name: "RADIO_STATUS.remrssi", slot: "tl" }] }], PAIR_L)] };

export const BUILTIN_TEMPLATES: Template[] = [
  // any file
  { version: 2, id: "bi-quicklook", group: "general", builtin: true, name: "Quick look", description: "@tplQuickDesc",
    slots: [{ id: "main", name: "@tplSlotFile" }], tabs: [], generator: "quicklook" },
  { version: 2, id: "bi-compare-files", group: "general", builtin: true, name: "Compare open files", description: "@tplCompareDesc",
    slots: [{ id: "main", name: "@tplSlotAll" }], tabs: [], generator: "compare" },
  { version: 2, id: "bi-position", group: "general", builtin: true, name: "Position on the map & 3D", description: "@tplObjDesc",
    slots: [{ id: "main", name: "@tplSlotFile" }], tabs: [], generator: "objects" },
  // flight logs
  { version: 2, id: "bi-ap-review", group: "ardupilot", builtin: true, name: "ArduPilot · Full review", description: "@tplApReview",
    slots: [AP], tabs: [], includes: [apAtt.id, apRate.id, apVibe.id, apBatt.id, apGps.id, apMot.id, apAlt.id, apEkf.id, apFlight.id] },
  apAtt, apRate, apVibe, apBatt, apGps, apMot, apAlt, apEkf, apFlight,
  { version: 2, id: "bi-mav-review", group: "mavlink", builtin: true, name: "MAVLink · Full review", description: "@tplMavReview",
    slots: [MAV], tabs: [], includes: [mavAtt.id, mavBatt.id, mavVibe.id, mavLink.id, mavFlight.id] },
  mavAtt, mavBatt, mavVibe, mavLink, mavFlight, px4Batt, px4Flight,
  pairAtt, pairBatt,
  { version: 2, id: "bi-pair-review", group: "compare", builtin: true, name: "Autopilot log vs telemetry · Full comparison",
    description: "@tplPairReview", slots: [SAP, STL], tabs: [], includes: [pairAtt.id, pairBatt.id] },
];
