import { api, type SignalInfo } from "./api";
import { findDerived } from "./peers";
import { translate } from "./i18n";
import { actions, useApp } from "./store";
import { freeGroup } from "./frames";

/* MSG1: *Decode as messages…* - the messages of a byte stream (svcore/bytestream.py finds the header, the length,
   the type and the checksum by itself) as derived signals of the op "messages" - type, length, interval, checksum
   good, at the messages' times - and a tab with one plot per quantity, the bytes first. A stream recorded both ways
   (a direction column beside it with text values, e.g. TX / RX): each direction its own stream, its own lines. */

export const DIR_NAME = /^(.*[._ ])?(dir|direction|rxtx|tx_rx|rx_tx|txrx|port|channel|src|source)$/i;
const WHATS = [["type", "msgType"], ["length", "msgLen"], ["interval", "msgInterval"], ["ok", "msgOk"]] as const;
const bare = (id: string) => id.slice(id.indexOf("/") + 1);
const safe = (s: string) => s.replace(/[^\w-]+/g, "_").replace(/^_+|_+$/g, "") || "bytes";

/** The direction column beside a byte signal (text values, 2..4 of them), if its file has one. */
export function directionOf(sigId: string): SignalInfo | null {
  const rid = sigId.slice(0, sigId.indexOf("/"));
  const run = useApp.getState().runs.find((r) => r.id === rid);
  return run?.signals.find((s) => s.id !== sigId && DIR_NAME.test(s.name) && s.labels
    && Object.keys(s.labels).length >= 2 && Object.keys(s.labels).length <= 4) ?? null;
}

/** Make the message signals of these byte signals (one stream byte by byte, or several columns, one message per
 *  row) and plot them in a new tab. Not a byte stream: a message says why. */
export async function decodeAsMessages(ids: string[]) {
  const st = useApp.getState();
  const tr = (k: string, v: Record<string, string | number> = {}) => translate(st.lang, k as never, v);
  const name = ids.length === 1 ? bare(ids[0]) : `${bare(ids[0])}…${bare(ids[ids.length - 1])}`;
  const dir = ids.length === 1 ? directionOf(ids[0]) : null;
  const streams: { label: string; sources: string[]; params: Record<string, unknown> }[] = dir
    ? Object.entries(dir.labels!).map(([code, text]) => ({ label: text, sources: [ids[0], dir.id], params: { dir: Number(code) } }))
    : [{ label: "", sources: ids, params: {} }];
  const per: Record<string, string[]> = Object.fromEntries(WHATS.map(([w]) => [w, []]));
  const made: string[] = [];
  try {
    for (const s of streams) {
      const runs = useApp.getState().runs;
      const base = safe(name) + (s.label ? "_" + safe(s.label) : "");
      const have = WHATS.map(([w]) => findDerived(runs, "messages", { what: w, ...s.params }, s.sources, ["group"]));
      if (have.every(Boolean)) { WHATS.forEach(([w], i) => per[w].push(have[i]!)); continue; }
      const g = freeGroup(`${base}.msg`, runs, WHATS.map(([w]) => w));
      for (const [w] of WHATS) {
        const r = await api.createDerived("messages", s.sources, { what: w, ...s.params, group: g }, `${g}.${w}`);
        useApp.setState({ runs: r.runs });
        made.push(r.id);
        per[w].push(r.id);
      }
    }
  } catch (e) {
    for (const id of made) await api.deleteDerived(id.slice("derived/".length)).catch(() => {});
    if (made.length) useApp.setState({ runs: await api.listRuns() });
    st.toast({ kind: "error", text: tr("msgNone", { name, msg: String((e as Error).message) }) });
    return;
  }
  const tab = tr("msgTab", { name: dir ? bare(ids[0]) : name });
  actions.plotsInNewTab([
    { title: tr("msgBytes"), ids: ids.slice(0, 4) },
    ...WHATS.map(([w, k]) => ({ title: tr(k), ids: per[w] })),
  ], tab);
}
