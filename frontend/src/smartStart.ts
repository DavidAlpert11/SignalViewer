import { api, type HealthFinding } from "./api";
import { tabHasContent, useApp } from "./store";
import { translate } from "./i18n";
import { applyTemplate, fits, rankTemplates, tx } from "./templates";

/**
 * Smart start (T29): when the first file goes into an empty workspace, a small card suggests the
 * template that fits it best (the backend's matching, ranked like the library does) and, for a
 * flight log, the three findings of its health check most worth a look. Nothing is applied by
 * itself; the card goes away when closed or when its template is opened.
 */
export interface StartCard {
  runId: string;
  template: { id: string; name: string; fit: number } | null;
  health: HealthFinding[] | null;      // the worst findings (errors, then warnings); [] = nothing found
  files?: number;                      // F20: opened together with others - the card offers Compare
}

const FIT_MIN = 0.5;                   // a suggestion must have at least half of what it plots
const FLIGHT = new Set(["bin", "tlog", "ulg"]);

/** Called by openPaths when it opened files into an empty workspace. */
export async function offerStart(runId: string, files = 1, auto = false) {
  const st = useApp.getState();
  const run = st.runs.find((r) => r.id === runId);
  if (!run || st.mavlink?.running) return;            // a live link opens its own recording: no card
  let template: StartCard["template"] = null;
  if (files >= 2) {                                    // F20: files opened together are compared
    try {
      const cmp = (await api.templates()).builtin.find((x) => x.generator === "compare");
      if (cmp) {
        const card: StartCard = { runId, template: { id: cmp.id, name: cmp.name, fit: 1 }, health: null, files };
        useApp.setState({ startCard: card });
        if (auto) await openSuggested(card);           // T48: an example opens ready to look at
      }
    } catch { /* no suggestion */ }
    return;
  }
  try {
    const r = await api.templates();
    const all = [...r.builtin, ...r.templates];
    const fitOf = await fits(all, useApp.getState().runs);
    const best = rankTemplates(all.filter((x) => !x.generator && (fitOf.get(x.id) ?? 0) >= FIT_MIN), fitOf, run.format)[0];
    if (best) template = { id: best.id, name: best.name, fit: fitOf.get(best.id) ?? 0 };
  } catch { /* no suggestion */ }
  let health: HealthFinding[] | null = null;
  if (FLIGHT.has(run.format) && run.log) {
    try {
      const h = await api.runHealth(runId);
      const rank = (f: HealthFinding) => (f.level === "error" ? 0 : 1);
      health = h ? h.findings.filter((f) => f.level !== "ok").sort((a, b) => rank(a) - rank(b)).slice(0, 3) : null;
    } catch { /* no health check for this file */ }
  }
  if (!template && health === null) return;
  if (!useApp.getState().runs.some((r) => r.id === runId)) return;      // closed meanwhile
  const card: StartCard = { runId, template, health };
  useApp.setState({ startCard: card });
  if (auto && template) await openSuggested(card);      // T48: an example opens ready to look at
}

/** Whether openPaths should offer a start: the workspace has nothing plotted yet. */
export const isEmptyStart = () => !useApp.getState().ws.tabs.some(tabHasContent);

/** "Open it": the suggested template on that file, as the library would open it. */
export async function openSuggested(card: StartCard) {
  const st = useApp.getState();
  const L = st.lang;
  if (!card.template) return;
  try {
    const r = await api.templates();
    const all = [...r.builtin, ...r.templates];
    const t = all.find((x) => x.id === card.template!.id);
    if (!t) return;
    const b = await api.bindTemplate(t, all, card.runId);
    const res = await applyTemplate(t, all, b.bind);
    // the view is open: the card keeps only the log's findings (each a click from its moment), if any
    useApp.setState({ startCard: card.health?.length ? { ...card, template: null } : null });
    if (!res.tabs) { st.toast({ kind: "error", text: translate(L, "tplNothing2", { names: res.missing.slice(0, 5).join(", ") }), ms: 12000 }); return; }
    st.toast({ kind: "info", ms: res.dropped.length ? 12000 : 4000, text: translate(L, "tplOpened", { name: tx(t.name, L), n: res.tabs, p: res.plots })
      + (res.dropped.length ? " " + translate(L, "tplLeftOut", { list: res.dropped.slice(0, 4).join(", ") + (res.dropped.length > 4 ? "…" : "") }) : "") });
  } catch (e) {
    st.toast({ kind: "error", text: String((e as Error).message) });
  }
}

/** T48: a template chip opens its template at once when nothing has to be asked - every file slot
 *  finds its own file. Otherwise (or when it cannot tell) the library opens on it, as before.
 *  Returns whether it opened. */
export async function openTemplateNow(id: string): Promise<boolean> {
  const st = useApp.getState();
  const L = st.lang;
  try {
    const r = await api.templates();
    const all = [...r.builtin, ...r.templates];
    const t = all.find((x) => x.id === id);
    if (!t || t.broken) return false;
    const b = await api.bindTemplate(t, all, null);
    const files = Object.values(b.bind).filter(Boolean);
    if (!b.slots.length || files.length < b.slots.length || new Set(files).size < files.length) return false;
    // a slot is settled when its file is the clear best (more of the template's signals than any
    // other open file) or it takes all files ("*all": Compare); a tie is a question for the library
    const settled = b.slots.every((sl) => {
      const v = b.bind[sl.id];
      if (v === "*all") return true;
      const mine = sl.counts[v] ?? 0;
      return !Object.entries(sl.counts).some(([rid, n]) => rid !== v && n >= mine);
    });
    if (!settled) return false;
    const res = await applyTemplate(t, all, b.bind);
    if (!res.tabs) { st.toast({ kind: "error", text: translate(L, "tplNothing2", { names: res.missing.slice(0, 5).join(", ") }), ms: 12000 }); return true; }
    useApp.setState({ startCard: null });
    st.toast({ kind: "info", ms: res.dropped.length ? 12000 : 5000, text: translate(L, "tplOpened", { name: tx(t.name, L), n: res.tabs, p: res.plots })
      + (res.dropped.length ? " " + translate(L, "tplLeftOut", { list: res.dropped.slice(0, 4).join(", ") + (res.dropped.length > 4 ? "…" : "") }) : ""),
      action: { label: translate(L, "undo"), run: () => useApp.getState().undo() } });
    return true;
  } catch {
    return false;
  }
}
