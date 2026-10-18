import { api, type RunInfo, type Template, type TplObject, type TplObjectRole, type TplPlot, type TplSlot, type TplTab } from "./api";
import { colorAllocator, fileLabel, TRACE_COLORS, uid, useApp, type MapObject, type ObjectKind, type Plot, type Tab } from "./store";
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

/* Matching names, choosing files for slots, how well files fit and a template's tabs with real
   signal ids are in the backend (svcore/templates.py, /api/templates/*): one implementation for
   the UI and the command line (batch reports). This file keeps what only the UI does: capturing
   tabs as a template, the structure helpers the dialogs show, the generators, and turning the
   resolved tabs into workspace tabs. */
const bare = (n: string) => n.replace(/ \[[^\]]*\]$/, "").replace(/^([^.[]+)\[\d+\]\./, "$1.");   // generator "compare" only

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

/** How well the open files fit each template (0..1; null: decide here - the objects generator). */
export async function fits(all: Template[], runs: RunInfo[]): Promise<Map<string, number>> {
  const r = await api.templateFits(all);
  return new Map(all.map((t) => [t.id, r.fits[t.id] ?? objectsFit(t, runs)]));
}
/** Templates best first for the open files: how well they fit, a template made for the file's
 *  format (preferFmt) first, and a collection ahead of its parts. Shared by the library (its first
 *  selection) and the start card, so both suggest the same one. */
export function rankTemplates(all: Template[], fitOf: Map<string, number>, preferFmt?: string | null): Template[] {
  const score = (x: Template) => (fitOf.get(x.id) ?? 0) + (preferFmt && x.slots.some((s) => s.formats?.includes(preferFmt)) ? 0.5 : 0)
    + (x.includes?.length ? 0.1 : 0);
  return all.filter((x) => !x.broken).sort((a, b) => score(b) - score(a));
}

/** "Position on the map & 3D" fits only when a file has latitude and longitude signals. */
const objectsFit = (t: Template, runs: RunInfo[]) =>
  t.generator === "objects" && dataRuns(runs).some((r) => { const g = guessRoles(r); return !!(g.lat && g.lon); }) ? 1 : 0;

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

/** Open a template's tabs (or only those chosen, by index into the expanded tabs) with these files:
 *  the backend resolves the names to signal ids, this turns the result into workspace tabs. */
export async function applyTemplate(t: Template, all: Template[], bind: Record<string, string>, chosen?: number[]): Promise<ApplyResult> {
  const st = useApp.getState();
  const L = st.lang;
  const e = expand(t, all);
  const extraTabs: TplTab[] = [];
  for (const g of e.generators) {
    const slot = g.slots[0].id;
    extraTabs.push(...(g.generator === "quicklook" ? quickLookTabs(st.runs.find((r) => r.id === bind[slot]), slot, L)
      : g.generator === "objects" ? objectTabs(st.runs.find((r) => r.id === bind[slot]), slot, L)
      : compareTabs(st.runs, slot, L)));
  }
  const r = await api.resolveTemplate(t, all, bind, chosen ?? null, extraTabs);
  const res: ApplyResult = { tabs: 0, plots: 0, dropped: r.dropped, missing: r.missing };
  let firstNew: string | null = null;
  st.commit((ws) => {
    const color = colorAllocator(ws);   // F13: one allocator for the whole apply
    const fileOrder = dataRuns(st.runs).map((x) => x.id);
    // the workspace is just the empty starting tab: the template's tabs replace it
    const emptyStart = ws.tabs.length === 1 && ws.tabs[0].plots.every((p) => !p.signals.length && !p.objects?.length);
    const before = ws.tabs.length;
    for (const rt of r.tabs) {
      const plots: Plot[] = rt.plots.map((rp) => {
        // the same signal from several files in one plot (Compare open files): one colour per FILE,
        // the same in every plot, so a run keeps its colour across the tabs (F13)
        const nameOf = (sig: string) => sig.slice(sig.indexOf("/") + 1);
        const runsOfName = new Map<string, Set<string>>();
        rp.signals.forEach((s) => runsOfName.set(nameOf(s.sig), (runsOfName.get(nameOf(s.sig)) ?? new Set()).add(s.sig.split("/")[0])));
        const byFile = (sig: string) => (runsOfName.get(nameOf(sig))?.size ?? 0) >= 2 && fileOrder.includes(sig.split("/")[0])
          ? TRACE_COLORS[fileOrder.indexOf(sig.split("/")[0]) % TRACE_COLORS.length] : null;
        return {
          id: uid("p"), title: rp.title, mode: (rp.mode as Plot["mode"]) ?? "time", xyAlign: rp.xyAlign as Plot["xyAlign"],
          fftWindow: rp.fftWindow as Plot["fftWindow"], fftMethod: rp.fftMethod as Plot["fftMethod"], fftLog: rp.fftLog, specN: rp.specN,
          caption: rp.caption, ylim: rp.ylim ?? null, ...(rp.xSignal ? { xSignal: rp.xSignal } : {}),
          signals: rp.signals.map((s) => ({ sig: s.sig, color: s.color ?? byFile(s.sig) ?? color(), width: s.width ?? 1.5, scale: s.scale ?? 1,
            offset: s.offset ?? 0, state: s.state ?? undefined, tOffset: s.tOffset ?? undefined, label: s.label ?? undefined,
            ...(s.limits ? { limits: s.limits } : {}) })),
          ...(rp.objects?.length ? { objects: rp.objects.map((o): MapObject => ({ ...o, id: uid("o"), kind: (o.kind as ObjectKind) ?? "aircraft",
            color: o.color ?? color(), angleUnit: o.angleUnit as MapObject["angleUnit"], altRef: o.altRef as MapObject["altRef"] })) } : {}),
        };
      });
      const tab: Tab = { id: uid("t"), name: rt.name, rows: rt.rows, cols: rt.cols, rowSizes: rt.rowSizes ?? undefined,
        colSizes: rt.colSizes ?? undefined, plots, active: 0, linkX: rt.linkX ?? true, linkY: rt.linkY ?? undefined,
        ...(rt.sharedStates?.length ? { sharedStates: rt.sharedStates } : {}) };
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
  return res;
}
