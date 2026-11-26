/* CC4: what to do with the span between the two cursors - a note, Find similar, What changed? - in one place:
   the plot's ⋯ menu and its right-click menu (the same lines). It was a bar of its own in the plot's head. */
import { api } from "./api";
import { actions, activeTab, useApp, type MenuItem } from "./store";
import { translate } from "./i18n";
import { openWhatChanged } from "./investigation";

/** Each time plot's own guess from its drawn lines (TimeChart registers it), for when the server has no answer. */
export const spanFallback = new Map<string, (a: number, b: number) => void>();

/** The span between the two cursors, ordered; null with fewer than two cursors or none between them. */
export function cursorSpan(): { a: number; b: number } | null {
  const c = useApp.getState().cursor;
  if (!c.on || !c.dual || c.t1 === null || c.t2 === null || c.t1 === c.t2) return null;
  return { a: Math.min(c.t1, c.t2), b: Math.max(c.t1, c.t2) };
}

/** "Find similar": a condition from the span. Of the signals on this tab's time plots, the one most unusual inside
 *  the span (the server reads each one's usual level before it) - not just this plot's first line, which is often
 *  not what the user marked. Without an answer: the plot's own guess (spanFallback). */
export async function findSimilar(plotId: string): Promise<void> {
  const span = cursorSpan();
  if (!span) return;
  const tb = activeTab(useApp.getState().ws);
  const sigs = [...new Set(tb.plots.filter((p) => (p.mode ?? "time") === "time")
    .flatMap((p) => p.signals.filter((s) => !s.state).map((s) => s.sig)))];
  try {
    const s = await api.suggestCondition(span.a, span.b, sigs);
    if (s.id && s.text && s.name) {
      useApp.setState({ panel: "investigate", condEdit: { id: "new", draft: { name: `${s.name} ${s.up ? "↑" : "↓"}`, text: s.text } } });
      return;
    }
  } catch { /* the plot's own guess, below */ }
  const own = spanFallback.get(plotId);
  if (own) own(span.a, span.b);
  else useApp.setState({ panel: "investigate", condEdit: { id: "new", draft: {} } });
}

/** The span's lines, first in a time plot's menus (none without a span). */
export function spanMenuItems(plotId: string): MenuItem[] {
  const span = cursorSpan();
  if (!span) return [];
  const lang = useApp.getState().lang;
  return [
    { label: `✎ ${translate(lang, "selNote")}`, run: () => actions.addNoteAtCursor() },
    { label: `⌕ ${translate(lang, "selFindSimilar")}`, run: () => { void findSimilar(plotId); } },
    { label: `? ${translate(lang, "selWhatChanged")}`, run: () => openWhatChanged(span) },
    { label: "", run: () => {}, sep: true },
  ];
}
