/* The values at the cursor, fetched as it moves (N6: its own component - the App, and so every panel
   under it, re-rendered on every frame of playback while this lived in it). Renders nothing. */
import { useEffect, useRef } from "react";
import { api } from "../api";
import { activeTab, useApp } from "../store";

export default function CursorValues() {
  const tab = useApp((s) => activeTab(s.ws));
  const cursor = useApp((s) => s.cursor);
  const dataVersion = useApp((s) => s.dataVersion);
  /* cursor values: full-resolution interpolation on the server.
     A signal with its own time offset is read at (cursor time - offset). */
  const sigOffsets = new Map<string, number>();
  tab.plots.forEach((p) => {
    p.signals.forEach((s) => { if (!sigOffsets.has(s.sig)) sigOffsets.set(s.sig, s.tOffset ?? 0); });
    if ((p.mode === "xy" || p.mode === "geo") && p.xSignal && !sigOffsets.has(p.xSignal)) sigOffsets.set(p.xSignal, 0);
  });
  const sigKey = Array.from(sigOffsets, ([k, o]) => `${k}@${o}`).join("|");
  /* One request at a time; when it returns and the cursor has moved meanwhile, one more for where it
     is NOW. (A debounce never fired while dragging - every step took longer than it - so each step
     sent a request and each answer redrew the plot: 154 requests for one drag.) The values follow
     the drag and playback instead of appearing only when the cursor stops. */
  const cvReq = useRef({ busy: false, again: false, want: "" });
  const cvWant = cursor.on && cursor.t1 !== null && sigKey ? `${cursor.t1}|${cursor.dual ? cursor.t2 : ""}|${sigKey}|${dataVersion}` : "";
  useEffect(() => {
    const R = cvReq.current;
    R.want = cvWant;
    if (!cvWant) return;
    const fetchNow = async () => {
      if (R.busy) { R.again = true; return; }
      R.busy = true;
      const c = useApp.getState().cursor;
      const key = R.want;
      const entries = key.split("|").slice(2, -1).join("|").split("|").map((e) => { const i = e.lastIndexOf("@"); return [e.slice(0, i), Number(e.slice(i + 1))] as [string, number]; });
      const groups = new Map<number, string[]>();
      entries.forEach(([sig, off]) => groups.set(off, [...(groups.get(off) ?? []), sig]));
      try {
        if (c.on && c.t1 !== null) {
          const out: Record<string, [number | null, number | null]> = {};
          await Promise.all(Array.from(groups, async ([off, sigs]) => {
            const a = await api.cursor(sigs, c.t1! - off);
            const b = c.dual && c.t2 !== null ? await api.cursor(sigs, c.t2 - off) : null;
            for (const sg of sigs) out[sg] = [a.values[sg] ?? null, b ? b.values[sg] ?? null : null];
          }));
          if (R.want) useApp.setState({ cvals: out });
        }
      } catch { /* the next move asks again */ }
      R.busy = false;
      if (R.again || (R.want && R.want !== key)) { R.again = false; if (R.want) fetchNow(); }
    };
    fetchNow();
  }, [cvWant]);
  return null;
}
