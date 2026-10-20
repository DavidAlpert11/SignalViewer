/* Notes at a moment of the recording (saved with the session, in reports). Through commit. */
import { translate } from "../../i18n";
import { uid } from "../model";
import { useApp } from "../state";

export const noteActions = {
  async addNoteAtCursor() {
    const st = useApp.getState();
    if (!st.cursor.on || st.cursor.t1 === null) {
      st.toast({ kind: "info", text: translate(st.lang, "noteNeedsCursor") });
      return;
    }
    // T23: with two cursors the note covers the time between them
    const range = st.cursor.dual && st.cursor.t2 !== null && st.cursor.t2 !== st.cursor.t1
      ? [Math.min(st.cursor.t1, st.cursor.t2), Math.max(st.cursor.t1, st.cursor.t2)] as const : null;
    const at = range ? range[0] : st.cursor.active === 2 && st.cursor.t2 !== null ? st.cursor.t2 : st.cursor.t1;
    const { prompt } = await import("../../components/Overlays");
    const where = range ? translate(st.lang, "noteFromTo", { a: range[0].toPrecision(7), b: range[1].toPrecision(7) })
      : translate(st.lang, "noteAt", { t: at.toPrecision(7) });
    const text = await prompt(translate(st.lang, "noteAdd"), where, "", true);
    if (!text || !text.trim()) return;
    st.commit((ws) => { ws.notes = [...(ws.notes ?? []), { id: uid("n"), t: at, ...(range ? { t2: range[1] } : {}), text: text.trim() }]; return ws; });
  },
  async editNote(id: string) {
    const st = useApp.getState();
    const n = st.ws.notes?.find((x) => x.id === id);
    if (!n) return;
    const { prompt } = await import("../../components/Overlays");
    const where = n.t2 !== undefined ? translate(st.lang, "noteFromTo", { a: n.t.toPrecision(7), b: n.t2.toPrecision(7) })
      : translate(st.lang, "noteAt", { t: n.t.toPrecision(7) });
    const text = await prompt(translate(st.lang, "noteEdit"), where, n.text, true);
    if (text === null) return;
    st.commit((ws) => { ws.notes = (ws.notes ?? []).map((x) => (x.id === id ? { ...x, text: text.trim() } : x)).filter((x) => x.text); return ws; });
  },
  removeNote(id: string) {
    useApp.getState().commit((ws) => { ws.notes = (ws.notes ?? []).filter((x) => x.id !== id); return ws; });
  },
};
