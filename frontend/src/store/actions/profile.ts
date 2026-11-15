/* L5 D14: profiles - a template's (or the user's) run-at-a-glance numbers and pinned searches in the
   session, through `commit` (Undo). The strip (OverviewStrip) shows `ws.glance`, the signal list
   `ws.searches`; a template carries both (templates.ts: templateFromTabs / applyTemplate). */
import type { GlanceItem, GlanceStat, PinnedSearch, Workspace } from "../model";
import { useApp } from "../state";

/** The strip has room for four numbers (plan §3.6). */
export const GLANCE_MAX = 4;
/** F4: the live instruments' tiles (two columns in a side panel; more would need scrolling). */
export const INSTRUMENTS_MAX = 8;
const gKey = (g: GlanceItem) => `${g.stat}|${g.name}`;

/** The profiles' numbers and searches not in the session yet (the first template's own first, then the ones
 *  it includes), at most GLANCE_MAX numbers. Changes `ws` in place (inside a commit); returns what was added. */
export function mergeProfile(ws: Workspace, profiles: { glance?: GlanceItem[]; searches?: PinnedSearch[]; instruments?: string[] }[]): { glance: number; searches: number } {
  const g = [...(ws.glance ?? [])], q = [...(ws.searches ?? [])], ins = [...(ws.instruments ?? [])];
  const n0 = g.length, m0 = q.length, i0 = ins.length;
  for (const p of profiles) {
    for (const it of p.glance ?? []) if (g.length < GLANCE_MAX && !g.some((x) => gKey(x) === gKey(it))) g.push({ ...it });
    for (const s of p.searches ?? []) if (!q.some((x) => x.q === s.q)) q.push({ ...s });
    for (const n of p.instruments ?? []) if (ins.length < INSTRUMENTS_MAX && !ins.includes(n)) ins.push(n);   // F4
  }
  if (g.length > n0) ws.glance = g;
  if (q.length > m0) ws.searches = q;
  if (ins.length > i0) ws.instruments = ins;
  return { glance: g.length - n0, searches: q.length - m0 };
}

/** The session's profile, as a template keeps it (nothing when empty: older templates stay the same). */
export function profileOf(ws: Workspace): { glance?: GlanceItem[]; searches?: PinnedSearch[]; instruments?: string[] } {
  return { ...(ws.glance?.length ? { glance: ws.glance.map((g) => ({ ...g })) } : {}),
    ...(ws.searches?.length ? { searches: ws.searches.map((s) => ({ ...s })) } : {}),
    ...(ws.instruments?.length ? { instruments: [...ws.instruments] } : {}) };
}

export const profileActions = {
  /** *Pin to at a glance*: false when the strip is full or the number is there already. */
  pinGlance(name: string, stat: GlanceStat): boolean {
    const ws = useApp.getState().ws;
    const it = { name, stat };
    if ((ws.glance ?? []).length >= GLANCE_MAX || (ws.glance ?? []).some((x) => gKey(x) === gKey(it))) return false;
    useApp.getState().commit((w) => { w.glance = [...(w.glance ?? []), it]; return w; });
    return true;
  },
  unpinGlance(index: number) {
    useApp.getState().commit((w) => { const g = (w.glance ?? []).filter((_x, i) => i !== index); if (g.length) w.glance = g; else delete w.glance; return w; });
  },
  /** F4: the instruments' tiles. `shown` = the tiles on screen now (the profile's names while the session has
   *  none of its own): the first change makes them the session's own list, so nothing shown disappears. */
  addInstrument(name: string, shown: string[]): boolean {
    const cur = useApp.getState().ws.instruments ?? shown;
    if (!name.trim() || cur.includes(name) || cur.length >= INSTRUMENTS_MAX) return false;
    useApp.getState().commit((w) => { w.instruments = [...cur, name]; return w; });
    return true;
  },
  removeInstrument(name: string, shown: string[]) {
    const cur = useApp.getState().ws.instruments ?? shown;
    useApp.getState().commit((w) => { w.instruments = cur.filter((n) => n !== name); return w; });
  },
  /** *Pin a search*: the signal list's search text as a chip (kept with a template). */
  pinSearch(q: string): boolean {
    const text = q.trim();
    if (!text || (useApp.getState().ws.searches ?? []).some((s) => s.q === text)) return false;
    useApp.getState().commit((w) => { w.searches = [...(w.searches ?? []), { q: text }]; return w; });
    return true;
  },
  unpinSearch(q: string) {
    useApp.getState().commit((w) => { const s = (w.searches ?? []).filter((x) => x.q !== q); if (s.length) w.searches = s; else delete w.searches; return w; });
  },
};
