/* 26.U8: one list of what happened in a recording - the log's mode changes, events, errors and
   messages, the health check's findings, the named conditions' stretches and the limits' violations -
   and ] / [ to jump to the next / previous one (a focused condition keeps its own stepping).

   Built from what the app already has (the Log panel's events, the health check, the conditions'
   results, the limits of the plotted signals); nothing is saved. */
import { api, type HealthFinding } from "./api";
import { actions, activeTab, fileLabel, rangeKey, useApp } from "./store";
import { ensureLogs } from "./logs";
import { fmtNum, translate, type TKey } from "./i18n";
import { findingText } from "./components/HealthRow";

export type EvKind = "mode" | "event" | "error" | "msg" | "finding" | "condition" | "limit";
export interface Ev { t: number; t2?: number; kind: EvKind; text: string; level: "info" | "warning" | "error"; run: string }

const health = new Map<string, { key: string; findings: HealthFinding[] }>();

async function findingsOf(rid: string): Promise<HealthFinding[]> {
  const st = useApp.getState();
  const run = st.runs.find((r) => r.id === rid);
  if (!run?.log) return [];
  const key = `${run.samples}:${run.timeOffset}:${run.log.events}`;
  const hit = health.get(rid);
  if (hit && hit.key === key) return hit.findings;
  let findings: HealthFinding[] = [];
  try { findings = (await api.runHealth(rid))?.findings ?? []; } catch { /* no health check for it */ }
  health.set(rid, { key, findings });
  return findings;
}

/** Every event of the open files (or of one), in time order - times as on the plots. */
export async function collectEvents(only?: string): Promise<Ev[]> {
  await ensureLogs();
  const st = useApp.getState();
  const lang = st.lang;
  const t = (k: TKey, v?: Record<string, string | number>) => translate(lang, k, v);
  const runs = st.runs.filter((r) => r.format !== "derived" && (!only || r.id === only));
  const many = runs.length > 1 && !only;
  const out: Ev[] = [];
  for (const r of runs) {
    const tag = many ? `${fileLabel(st.runs, r.id)}: ` : "";
    const info = st.logs[r.id];
    if (info) {
      const off = info.timeOffset || 0;
      for (const e of info.events) out.push({ t: e.t + off, kind: e.kind, text: tag + e.text, level: e.level === "info" ? "info" : e.level === "error" ? "error" : "warning", run: r.id });
    }
    for (const f of await findingsOf(r.id)) {
      if (f.level === "ok") continue;
      const at = f.t ?? f.spans[0]?.[0];
      if (at === undefined || at === null) continue;
      out.push({ t: at, t2: f.t === null ? f.spans[0]?.[1] : undefined, kind: "finding", text: tag + findingText(t, f), level: f.level, run: r.id });
    }
    for (const c of st.ws.conditions ?? []) {
      const res = st.condResults[c.id]?.[r.id];
      for (const [a, b] of res?.intervals ?? []) out.push({ t: a, t2: b, kind: "condition", text: tag + c.name, level: "info", run: r.id });
    }
  }
  // the limits of the signals plotted in this tab: where each is outside them
  const items = activeTab(st.ws).plots.flatMap((p) => p.signals.filter((s) => s.limits && (s.limits.lo != null || s.limits.hi != null)
    && runs.some((r) => s.sig.startsWith(`${r.id}/`)))
    .map((s) => ({ id: s.sig, lo: s.limits!.lo ?? null, hi: s.limits!.hi ?? null, scale: s.scale, offset: s.offset, tOffset: s.tOffset ?? 0 })));
  if (items.length) {
    try {
      const res = (await api.limits(items, null, null)).results;
      for (const it of items) {
        const lim = res[it.id];
        const name = it.id.slice(it.id.indexOf("/") + 1);
        const range = `${it.lo ?? "−∞"} … ${it.hi ?? "∞"}`;
        for (const [a, b] of lim?.spans ?? []) out.push({ t: a, t2: b, kind: "limit", text: t("evLimit", { name, range }), level: "warning", run: it.id.split("/")[0] });
      }
    } catch { /* a signal closed meanwhile */ }
  }
  return out.sort((a, b) => a.t - b.t);
}

/** What ] / [ step through: everything but the log's plain messages. */
const stepping = (e: Ev) => !(e.kind === "msg" && e.level === "info");

/** ] / [ : the cursor to the next / previous event (from the cursor, else from the left of the view). */
export async function stepEvent(dir: 1 | -1) {
  const all = (await collectEvents()).filter(stepping);
  const st = useApp.getState();
  const lang = st.lang;
  if (!all.length) { st.toast({ kind: "info", text: translate(lang, "evNone") }); return; }
  const tab = activeTab(st.ws);
  const p = tab.plots[tab.active];
  const view = p ? st.ranges[rangeKey(tab, p)] ?? null : null;
  const from = st.cursor.on && st.cursor.t1 !== null ? st.cursor.t1 : view ? (dir > 0 ? view[0] - 1e-9 : view[1] + 1e-9) : dir > 0 ? -Infinity : Infinity;
  let k = dir > 0 ? all.findIndex((e) => e.t > from + 1e-9) : -1;
  if (dir < 0) for (let i = all.length - 1; i >= 0; i--) if (all[i].t < from - 1e-9) { k = i; break; }
  if (k < 0) { st.toast({ kind: "info", text: translate(lang, dir > 0 ? "evLast" : "evFirst") }); return; }
  const e = all[k];
  actions.goToTime(e.t);
  useApp.setState({ eventAt: { text: `${translate(lang, `evKind_${e.kind}` as TKey)} · ${e.text}`, t: e.t, n: k + 1, of: all.length, level: e.level } });
}

/** The time as the event list writes it. */
export const evTime = (t: number, lang: "en" | "he") => fmtNum(t, lang, Math.abs(t) >= 1000 ? 7 : 5);
