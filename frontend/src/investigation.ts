/* Investigation step 6: findings (notes with a status and the view they were found in), the journal
   of steps recorded as they happen, and the report's investigation sections built from them. */
import { api } from "./api";
import { translate, type TKey } from "./i18n";
import { activeTab, fileLabel, rangeKey, uid, useApp, type FindingStatus, type JournalStep, type SavedView, type StepKind } from "./store";
import { forgetPlotsBeside } from "./components/rail";

/** What is on screen now (to bring it back later). */
export function captureView(): SavedView {
  const st = useApp.getState();
  const tab = activeTab(st.ws);
  const ranges: Record<string, [number, number]> = {};
  for (const p of tab.plots) { const k = rangeKey(tab, p); const r = st.ranges[k]; if (r) ranges[k] = [r[0], r[1]]; }
  return { tab: tab.id, ranges, t1: st.cursor.on ? st.cursor.t1 : null, t2: st.cursor.on && st.cursor.dual ? st.cursor.t2 : null };
}
export function restoreView(v: SavedView) {
  const st = useApp.getState();
  if (st.ws.tabs.some((t) => t.id === v.tab)) useApp.setState({ ws: { ...st.ws, activeTab: v.tab } });
  useApp.setState({ ranges: { ...useApp.getState().ranges, ...v.ranges },
    cursor: { ...st.cursor, on: v.t1 !== null, dual: v.t2 !== null, t1: v.t1, t2: v.t2, active: 1 } });
}

/** "What changed?" around a span: the one shown before it goes to the earlier ones (kept, opened again with a click). */
export function openWhatChanged(span: { a: number; b: number }) {
  const st = useApp.getState();
  const same = (x: { a: number; b: number }) => x.a === span.a && x.b === span.b;
  const cur = st.whatChanged;
  const earlier = [...(cur && !same(cur) ? [cur] : []), ...st.wcEarlier.filter((x) => !same(x) && !(cur && x.a === cur.a && x.b === cur.b))].slice(0, 12);
  forgetPlotsBeside("investigate");          // a new answer to read: on the whole stage again (rail.ts)
  useApp.setState({ panel: "investigate", whatChanged: span, wcEarlier: earlier });
}

/** Add a step to the journal (no undo step: it is a record, not an edit). */
export function record(text: string, withView = true, kind?: StepKind) {
  const st = useApp.getState();
  const step: JournalStep = { id: uid("j"), at: Date.now(), text, include: true, ...(kind ? { kind } : {}), ...(withView ? { view: captureView() } : {}) };
  useApp.setState({ journal: [...st.journal, step].slice(-200) });
}

/** A note's status: the first time it becomes a finding, the view it was found in is kept with it. */
export function setFindingStatus(id: string, status: FindingStatus | "") {
  const st = useApp.getState();
  const n = st.ws.notes?.find((x) => x.id === id);
  if (!n) return;
  const view = n.view ?? (status ? captureView() : undefined);
  st.commit((ws) => {
    ws.notes = (ws.notes ?? []).map((x) => (x.id === id ? { ...x, status: status || undefined, ...(view ? { view } : {}) } : x));
    return ws;
  });
  if (status) record(translate(st.lang, "jFinding", { text: n.text, status: translate(st.lang, `fs_${status}` as TKey) }), true, "finding");
}

/** Parameters as a reader writes them - `window=5, kind=mean` - not as JSON (review C11). */
export const nameValues = (p: Record<string, unknown>) => Object.entries(p).filter(([, v]) => v !== undefined && v !== null && v !== "")
  .map(([k, v]) => `${k}=${typeof v === "object" ? (Array.isArray(v) ? v.join(" ") : JSON.stringify(v)) : String(v)}`).join(", ");

const when = (t: number, t2?: number) => (t2 !== undefined ? `${t.toPrecision(6)} – ${t2.toPrecision(6)} s` : `${t.toPrecision(6)} s`);
const ORDER: Record<string, number> = { open: 0, fault: 1, explained: 2 };

/** The report's investigation: findings, rejected hypotheses, analysis steps, conditions per run,
 *  and how to reproduce it all. Empty parts are left out. */
export async function investigationSections(lang: "en" | "he") {
  const st = useApp.getState();
  const t = (k: TKey, p?: Record<string, string | number>) => translate(lang, k, p);
  const notes = st.ws.notes ?? [];
  const files = st.runs.filter((r) => r.format !== "derived");
  const out: { title: string; text?: string; items?: string[]; table?: { head: string[]; rows: string[][] } }[] = [];
  const found = notes.filter((n) => n.status && n.status !== "rejected").sort((a, b) => (ORDER[a.status!] - ORDER[b.status!]) || a.t - b.t);
  if (found.length) out.push({ title: t("rFindings"), table: { head: [t("rWhen"), t("rWhat"), t("rStatus")],
    rows: found.map((n) => [when(n.t, n.t2), n.text, t(`fs_${n.status}` as TKey)]) } });
  const rejected = notes.filter((n) => n.status === "rejected");
  if (rejected.length) out.push({ title: t("rRejected"), text: t("rRejectedText"), items: rejected.map((n) => `${when(n.t, n.t2)}: ${n.text}`) });
  const steps = st.journal.filter((j) => j.include);
  if (steps.length) out.push({ title: t("rSteps"), items: steps.map((j) => j.text) });
  const conds = st.ws.conditions ?? [];
  if (conds.length) out.push({ title: t("conditions"), table: {
    head: [t("condName"), t("condWhen"), ...files.map((f) => fileLabel(st.runs, f.id))],
    rows: conds.map((c) => [c.name, c.combine ? c.combine.ids.map((id) => conds.find((x) => x.id === id)?.name ?? "?").join(c.combine.op === "and" ? " ∧ " : " ∨ ") : c.text,
      ...files.map((f) => { const r = st.condResults[c.id]?.[f.id]; return r?.missing?.length || r?.error ? "–" : String(r?.count ?? 0); })]) } });
  // how to reproduce: what was opened, how it was read, and everything that was computed or changed
  let version = "";
  try { version = (await api.diagnostics()).version; } catch { /* offline */ }
  const items: string[] = [];
  for (const f of files) {
    const s = f.importSettings ?? {};
    const extra = [s.time_column ? `${t("taColumn")}: ${s.time_column}` : "", s.time_scale ? `× ${s.time_scale}` : "", f.timeOffset ? `${t("taOffset")}: ${f.timeOffset} s` : ""].filter(Boolean).join(", ");
    // review C11: a report sent outside does not carry this computer's folders - the file's name, its samples and when
    // it was saved say which file it is; the full path only when chosen in Settings
    const at = f.fileTime ? new Date(f.fileTime * 1000).toISOString().slice(0, 16).replace("T", " ") : "–";
    const which = st.reportPaths ? f.path : t("rFileLine", { name: f.name, n: f.samples.toLocaleString("en-US"), when: at });
    items.push(`${fileLabel(st.runs, f.id)}: ${which}${extra ? ` (${extra})` : ""}`);
  }
  for (const c of conds.filter((x) => !x.combine)) {
    items.push(`${c.name}: ${c.text}${c.exit ? `; ${t("condExit")} ${c.exit}` : ""}${c.minDur ? `; ≥ ${c.minDur} s` : ""}${c.mergeGap ? `; ${t("condMergeGap")} ${c.mergeGap}` : ""}`);
  }
  for (const s of st.runs.find((r) => r.format === "derived")?.signals ?? []) items.push(`${s.name} = ${s.op ?? ""}(${(s.sources ?? []).join(", ")}) ${s.params ? nameValues(s.params) : ""}`.trim());
  for (const f of files) for (const s of f.signals) if (s.transform) items.push(`ƒ ${s.name}: ${nameValues(s.transform as unknown as Record<string, unknown>)}`);
  if (version) items.push(`Signal Viewer ${version}`);
  if (items.length) out.push({ title: t("rReproduce"), items });
  return out;
}
