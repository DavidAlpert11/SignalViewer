import { api, type InspectFrame, type MessagesInspect, type SignalInfo } from "./api";
import { findDerived } from "./peers";
import { translate } from "./i18n";
import { actions, useApp } from "./store";
import type { MessageStream, StructMessage, Structure } from "./store/model";
import type { ByteRole } from "./components/ByteView";
import { freeGroup } from "./frames";
import { appendToDoc } from "./reportDoc";
import { confirmAsk, prompt } from "./components/Overlays";

/* MSG1: *Decode as messages…* - a signal of bytes (or byte columns, one message per row) defined as a stream of
   messages (owner, 2026-11-19): it carries only TX, only RX, or both - with a direction column beside it that says
   whose each byte is. The definition is kept in the session (ws.messageStreams, one Undo) and the report's
   [[messages]] uses it. The messages themselves (svcore/bytestream.py finds the header, the length, the type and
   the checksum, unless given) become derived signals of the op "messages" - type, length, interval, checksum good -
   and a tab with one plot per quantity, the bytes first, one line per direction. */

export const DIR_NAME = /^(.*[._ ])?(dir|direction|rxtx|tx_rx|rx_tx|txrx|port|channel|src|source)$/i;
const WHATS = [["type", "msgType"], ["length", "msgLen"], ["interval", "msgInterval"], ["ok", "msgOk"]] as const;
const bare = (id: string) => id.slice(id.indexOf("/") + 1);
const safe = (s: string) => s.replace(/[^\w-]+/g, "_").replace(/^_+|_+$/g, "") || "bytes";
const uid = () => `m${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

/** A direction column beside a byte signal - MSG5: any other column of the file (its values are asked for when it is
 *  chosen: 2..32 of them); named like one first, then text values (2..4), then the rest. */
export function directionCandidates(sigId: string): SignalInfo[] {
  const rid = sigId.slice(0, sigId.indexOf("/"));
  const run = useApp.getState().runs.find((r) => r.id === rid);
  const few = (s: SignalInfo) => !!s.labels && Object.keys(s.labels).length >= 2 && Object.keys(s.labels).length <= 4;
  const list = (run?.signals ?? []).filter((s) => s.id !== sigId);
  const named = list.filter((s) => DIR_NAME.test(s.name)), texts = list.filter((s) => !DIR_NAME.test(s.name) && few(s));
  return [...named, ...texts, ...list.filter((s) => !named.includes(s) && !texts.includes(s))];
}

/** MSG5: TX and RX picked from a direction column's values - a text like TX / RX (out / in...) first, else its first
 *  two values. */
export function guessDirections(values: { v: number; label: string | null }[]): { tx: number | null; rx: number | null } {
  if (values.length < 2) return { tx: null, rx: null };
  const tx = values.find((x) => x.label && /tx|out|send|up/i.test(x.label)) ?? values[0];
  const rx = values.find((x) => x !== tx && x.label && /rx|in|recv|receive|down/i.test(x.label)) ?? values.find((x) => x !== tx)!;
  return { tx: tx.v, rx: rx.v };
}

/** The definition to start from: the one kept for these signals, else a guess (a direction column -> both; a name
 *  with rx -> RX; else TX). */
export function streamFor(ids: string[]): MessageStream {
  const kept = (useApp.getState().ws.messageStreams ?? []).find((m) => m.sources.join(",") === ids.join(","));
  if (kept) return kept;
  const dir = ids.length === 1 ? directionCandidates(ids[0]).find((s) => DIR_NAME.test(s.name) && !!s.labels && Object.keys(s.labels).length >= 2 && Object.keys(s.labels).length <= 4) : undefined;
  const tx = dir?.labels ? Object.entries(dir.labels).find(([, v]) => /tx|out|send|up/i.test(v))?.[0] ?? Object.keys(dir.labels)[0] : null;
  const rxName = (id: string) => /(^|[^a-z])rx|recv|receive|down/i.test(bare(id));
  // two signals, one named like TX and one like RX: the two directions of one link (TX first)
  if (ids.length === 2 && rxName(ids[0]) !== rxName(ids[1]))
    return { id: uid(), sources: rxName(ids[0]) ? [ids[1], ids[0]] : ids, carries: "pair" };
  return { id: uid(), sources: ids, carries: dir ? "both" : rxName(ids[0]) ? "rx" : "tx",
    dir: dir?.id ?? null, txValue: tx === null ? null : Number(tx) };
}

/** The streams of a definition: (label, sources, params) - both ways: one per direction value. */
export function streamsOf(def: MessageStream): { label: string; sources: string[]; params: Record<string, unknown> }[] {
  const prm: Record<string, unknown> = {};
  if (def.header) prm.header = def.header;
  if (def.checksum) prm.checksum = def.checksum;
  if (def.carries === "pair") return def.sources.slice(0, 2).map((s, i) => ({ label: i ? "RX" : "TX", sources: [s], params: prm }));
  if (def.carries !== "both" || !def.dir) return [{ label: def.carries.toUpperCase(), sources: def.sources, params: prm }];
  // MSG5: the user's two values - TX and RX (the column's other values left out)
  if (def.txValue != null && def.rxValue != null)
    return [["TX", def.txValue], ["RX", def.rxValue]].map(([label, c]) => ({ label: label as string, sources: [def.sources[0], def.dir!], params: { ...prm, dir: c } }));
  const run = useApp.getState().runs.find((r) => r.id === def.dir!.slice(0, def.dir!.indexOf("/")));
  const labels = run?.signals.find((s) => s.id === def.dir)?.labels ?? {};
  const codes = Object.keys(labels).map(Number).sort((a, b) => a - b);
  const tx = def.txValue ?? codes[0] ?? 0;
  return [tx, ...codes.filter((c) => c !== tx)].map((c, i) => ({
    label: i === 0 ? "TX" : codes.length > 2 ? `RX ${labels[String(c)] ?? c}` : "RX", sources: [def.sources[0], def.dir!], params: { ...prm, dir: c } }));
}

/** Keep the definition (one Undo step), make the message signals and plot them in a new tab. */
export async function decodeAsMessages(def: MessageStream) {
  const st = useApp.getState();
  const tr = (k: string, v: Record<string, string | number> = {}) => translate(st.lang, k as never, v);
  const ids = def.sources;
  const name = ids.length === 1 ? bare(ids[0]) : `${bare(ids[0])}…${bare(ids[ids.length - 1])}`;
  st.commit((ws) => {
    const key = ids.join(",");
    ws.messageStreams = [...(ws.messageStreams ?? []).filter((m) => m.sources.join(",") !== key), def];
    return ws;
  });
  const per: Record<string, string[]> = Object.fromEntries(WHATS.map(([w]) => [w, []]));
  const made: string[] = [];
  try {
    for (const s of streamsOf(def)) {
      const runs = useApp.getState().runs;
      const have = WHATS.map(([w]) => findDerived(runs, "messages", { what: w, ...s.params }, s.sources, ["group"]));
      if (have.every(Boolean)) { WHATS.forEach(([w], i) => per[w].push(have[i]!)); continue; }
      const g = freeGroup(`${safe(name)}_${safe(s.label)}.msg`, runs, WHATS.map(([w]) => w));
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
    return false;
  }
  // both directions: each answered request's reply latency over time (svcore exchange) - if anything answers
  const lat: string[] = [];
  const two = streamsOf(def);
  if (two.length >= 2) {
    const prm = def.carries === "pair" ? { what: "latency", link: true } : { what: "latency", dir: two[0].params.dir, rxdir: two[1].params.dir };
    const src = def.carries === "pair" ? def.sources.slice(0, 2) : [def.sources[0], def.dir!];
    const have = findDerived(useApp.getState().runs, "messages", prm, src, ["group"]);
    if (have) lat.push(have);
    else {
      try {
        const g = freeGroup(`${safe(name)}.link`, useApp.getState().runs, ["latency"]);
        const r = await api.createDerived("messages", src, { ...prm, group: g }, `${g}.latency`);
        useApp.setState({ runs: r.runs });
        lat.push(r.id);
      } catch { /* nothing answers anything: streaming both ways - the other plots stand */ }
    }
  }
  actions.plotsInNewTab([
    { title: tr("msgBytes"), ids: ids.slice(0, 4) },
    ...WHATS.map(([w, k]) => ({ title: tr(k), ids: per[w] })),
    ...(lat.length ? [{ title: tr("msgLatency"), ids: lat }] : []),
  ], tr("msgTab", { name }));
  return true;
}

/* ---- MSG2: a structure -> a recording --------------------------------------------------------- */

/** The recording's name for one direction of a definition. */
export function recordingName(def: MessageStream, label: string): string {
  const ids = def.sources;
  const base = ids.length === 1 ? bare(ids[0]) : `${bare(ids[0])}…${bare(ids[ids.length - 1])}`;
  const one = streamsOf(def).length > 1 ? (def.carries === "pair" ? bare(streamsOf(def).find((s) => s.label === label)?.sources[0] ?? "") : `${base} ${label}`) : base;
  return `${one} - messages`;
}

/** Make (or make again) the recording of one direction from its structure; keep the definition (one Undo step)
 *  and plot each message's fields in a new tab. Returns the new recording's id, or null (a message said why). */
export async function makeRecording(def: MessageStream, label: string, opts: { plot?: boolean; id?: string } = {}): Promise<string | null> {
  const st = useApp.getState();
  const tr = (k: string, v: Record<string, string | number> = {}) => translate(st.lang, k as never, v);
  const s = streamsOf(def).find((x) => x.label === label) ?? streamsOf(def)[0];
  const structure = def.structures?.[label];
  if (!s || !structure) return null;
  const name = recordingName(def, label);
  let r: Awaited<ReturnType<typeof api.messagesParse>>;
  try {
    const skip = def.skip?.[label]?.filter((n) => structure.messages.some((m) => m.name === n));
    r = await api.messagesParse(s.sources, skip?.length ? { ...s.params, skip } : s.params, structure, name, opts.id);
  } catch (e) {
    st.toast({ kind: "error", text: tr("msgNone", { name, msg: String((e as Error).message) }) });
    return null;
  }
  useApp.setState({ runs: r.runs, dataVersion: useApp.getState().dataVersion + 1 });
  if (opts.id) return r.run;                       // a session reopened: its plots are there already
  const made = [...(def.made ?? []).filter((m) => m.label !== label), { label, run: r.run, name }];
  useApp.getState().commit((ws) => {
    const key = def.sources.join(",");
    ws.messageStreams = [...(ws.messageStreams ?? []).filter((m) => m.sources.join(",") !== key), { ...def, made }];
    return ws;
  });
  const rep = r.report as { bad?: number; unknown?: Record<string, number>; messages?: Record<string, number> };
  const n = Object.values(rep.messages ?? {}).reduce((a, b) => a + b, 0);
  useApp.getState().toast({ kind: "info", text: tr("msgMade", { name, n, k: r.signals.length, bad: rep.bad ?? 0,
    unknown: Object.values(rep.unknown ?? {}).reduce((a, b) => a + b, 0) }) });
  if (opts.plot !== false) {
    // a plot per message (its first fields), so the decoded values are seen at once
    const by = new Map<string, string[]>();
    let seq: string | undefined;
    for (const id of r.signals) {
      if (bare(id) === "message") { seq = id; continue; }
      const msg = bare(id).split(".")[0];
      by.set(msg, [...(by.get(msg) ?? []), id]);
    }
    // MSG7: the messages in order as a lane on every plot (which message passed when)
    actions.plotTabs([{ name: tr("msgRecTab", { name }), lanes: seq ? [seq] : undefined,
      plots: [...by.entries()].filter(([, ids]) => ids.length).slice(0, 12).map(([msg, ids]) => ({ title: msg, ids: ids.slice(0, 6) })) }]);
  }
  return r.run;
}

/** MSG7: one message's values in a tab of their own - a plot per field (the recording made first when it is not yet),
 *  with the lane of every message in order under them. */
export async function plotMessage(def: MessageStream, label: string, msg: string): Promise<boolean> {
  const st = useApp.getState();
  const tr = (k: string, v: Record<string, string | number> = {}) => translate(st.lang, k as never, v);
  const made = def.made?.find((m) => m.label === label);
  let runId = made && st.runs.some((r) => r.id === made.run) ? made.run : null;
  if (!runId) runId = await makeRecording(def, label, { plot: false });
  if (!runId) return false;
  const run = useApp.getState().runs.find((r) => r.id === runId);
  const ids = (run?.signals ?? []).filter((s) => s.name.startsWith(msg + ".")).map((s) => s.id);
  const seq = run?.signals.find((s) => s.name === "message")?.id;
  if (!ids.length) {
    useApp.getState().toast({ kind: "info", text: tr("msgPlotNone", { msg }) });
    return false;
  }
  actions.plotTabs([{ name: `${msg} · ${recordingName(def, label)}`, lanes: seq ? [seq] : undefined, cols: ids.length > 3 ? 2 : 1,
    plots: ids.slice(0, 12).map((id) => ({ title: bare(id).slice(msg.length + 1), ids: [id] })) }]);
  return true;
}

/** A session reopened: its recordings made from messages are made again, with the ids its plots refer to. */
export async function remakeRecordings(streams: MessageStream[] | undefined): Promise<string[]> {
  const ids: string[] = [];
  for (const def of streams ?? []) for (const m of def.made ?? []) {
    const id = await makeRecording(def, m.label, { plot: false, id: m.run });
    if (id) ids.push(id);
  }
  return ids;
}

/* ---- MSG3: the Messages panel's other actions --------------------------------------------------- */

/** "Add to the report": the definition kept (one Undo step with it) and a [[messages <this stream>]] at the end. */
/** A byte stream's definition taken out of the session (one Undo): the stream goes back to what the app finds by
 *  itself. A recording made from it stays open now; it is not made again when the session opens. */
export function forgetStream(ids: string[]) {
  const st = useApp.getState();
  const key = ids.join(",");
  if (!(st.ws.messageStreams ?? []).some((m) => m.sources.join(",") === key)) return;
  st.commit((ws) => { ws.messageStreams = (ws.messageStreams ?? []).filter((m) => m.sources.join(",") !== key); return ws; });
}

export function addStreamToReport(def: MessageStream) {
  const st = useApp.getState();
  const ids = def.sources;
  const name = def.carries === "pair" ? ids.slice(0, 2).map(bare).join(", ") : ids.length === 1 ? bare(ids[0]) : `${bare(ids[0])}…${bare(ids[ids.length - 1])}`;
  const ref = `[[messages ${name}]]`;
  st.commit((ws) => {
    const key = ids.join(",");
    const old = (ws.messageStreams ?? []).find((m) => m.sources.join(",") === key);
    ws.messageStreams = [...(ws.messageStreams ?? []).filter((m) => m.sources.join(",") !== key), { ...def, made: def.made ?? old?.made }];
    return appendToDoc(ws, st.lang, ref);
  });
  st.toast({ kind: "info", text: translate(st.lang, "rdAdded", { ref }), action: { label: translate(st.lang, "report"), run: () => useApp.setState({ panel: "report" }) } });
}

/** A structure into the library's folder (asks before replacing one of the same name). */
export async function saveToLibrary(structure: Structure): Promise<boolean> {
  const st = useApp.getState();
  const name = (await prompt(translate(st.lang, "msgpSaveLib"), translate(st.lang, "msgpSaveAsk"), structure.name || "messages"))?.trim();
  if (!name) return false;
  try {
    let r;
    structure = { ...structure, name };
    try { r = await api.messagesLibrarySave(structure, name); } catch (e) {
      if (!/already in the library/.test(String((e as Error).message))) throw e;
      if (!await confirmAsk(translate(st.lang, "msgpSaveLib"), translate(st.lang, "msgpReplace", { name }))) return false;
      r = await api.messagesLibrarySave(structure, name, true);
    }
    st.toast({ kind: "info", text: translate(st.lang, "msgpSaved", { path: r.path }), ms: 10000 });
    return true;
  } catch (e) {
    st.toast({ kind: "error", text: String((e as Error).message) });
    return false;
  }
}

/** The message types of a log / recording (MAVLink .tlog, DataFlash .bin, .ulg, a link's or a stream's recording):
 *  its signals grouped by the name before the first dot - each type's fields, count and rate. */
export const LOG_FORMATS = new Set(["tlog", "bin", "ulg", "mcap"]);
export function isMessageLog(r: { format?: string; path?: string; importSettings?: Record<string, unknown> }) {
  return LOG_FORMATS.has(r.format ?? "") || r.importSettings?.format === "svraw" || (r.path ?? "").startsWith("python:messages/");
}
export function messageTypes(signals: SignalInfo[]): { type: string; ids: string[]; count: number; rate: number | null }[] {
  const by = new Map<string, { type: string; ids: string[]; count: number; rate: number | null }>();
  for (const s of signals) {
    const dot = s.name.indexOf(".");
    if (dot <= 0) continue;
    const type = s.name.slice(0, dot);
    const g = by.get(type) ?? { type, ids: [], count: 0, rate: null };
    g.ids.push(s.id);
    g.count = Math.max(g.count, s.n ?? 0);
    if (s.rate !== undefined) g.rate = Math.max(g.rate ?? 0, s.rate);
    by.set(type, g);
  }
  return [...by.values()].sort((a, b) => b.count - a.count || a.type.localeCompare(b.type));
}

/* ---- MSG4: a click on a byte says what it is ------------------------------------------------------ */

const hx = (v: number) => v.toString(16).toUpperCase().padStart(2, "0");
const SIZE: Record<string, number> = { u8: 1, i8: 1, u16: 2, i16: 2, u24: 3, i24: 3, u32: 4, i32: 4, u64: 8, i64: 8, f32: 4, f64: 8 };
/** How many bytes a binary field takes (MSG8: an ascii field says it). */
export const fieldSize = (f: { type?: string; size?: number }) => f.type === "ascii" ? Math.max(1, f.size ?? 1) : SIZE[f.type ?? "u8"] ?? 1;

/** The structure after the user said what a byte (or a text part) of one shown message is: the header ends here, the
 *  length / type byte, the footer starts here, a field of a type starts here, or not a field. Pure - the panel's
 *  step 2 and the tests. A frame of a type the structure has no message for gets one. */
export function applyRole(s: Structure, frame: InspectFrame, role: ByteRole): Structure {
  const st: Structure = JSON.parse(JSON.stringify(s));
  const b = frame.bytes ?? [];
  const msgOf = (): StructMessage => {
    const byName = st.messages.find((m) => frame.message && m.name === frame.message);
    if (byName) return byName;
    const id = st.kind === "text" ? String(frame.id ?? "MSG") : st.type ? Number(frame.id ?? 0) : 0;
    const same = st.messages.find((m) => String(m.id) === String(id));
    if (same) return same;
    const m: StructMessage = { id, name: st.kind === "text" ? String(id) : `MSG_${hx(Number(id))}`, fields: [] };
    st.messages.push(m);
    return m;
  };
  switch (role.kind) {
    case "header": st.header = b.slice(0, role.upto + 1).map(hx).join(""); break;
    case "length": st.length = { offset: role.at, add: (frame.len ?? b.length) - b[role.at] }; st.size = null; break;
    case "footer": st.footer = b.slice(role.from).map(hx).join(""); break;
    case "type": {
      const id = b[role.at];
      const had = !!st.type;
      st.type = { offset: role.at };
      if (!had && st.messages.length === 1) st.messages[0].id = id;          // one message until now: it is this type
      else if (!st.messages.some((m) => Number(m.id) === id)) st.messages.push({ id, name: `MSG_${hx(id)}`, fields: [] });
      if (!had && st.messages.length === 1 && st.size) { st.messages[0].size = st.size; }
      break;
    }
    case "field": {
      const m = msgOf();
      const n = role.type === "ascii" ? Math.max(1, role.size ?? 1) : SIZE[role.type] ?? 1;
      m.fields = m.fields.filter((f) => { const a = f.offset ?? 0, z = a + fieldSize(f); return z <= role.at || a >= role.at + n; });
      m.fields.push(role.type === "ascii" ? { name: `text_${role.at}`, offset: role.at, type: "ascii", size: n }
        : { name: `value_${role.at}`, offset: role.at, type: role.type, ...(n > 1 ? { endian: role.endian } : {}) });
      m.fields.sort((x, y) => (x.offset ?? 0) - (y.offset ?? 0));
      break;
    }
    case "nofield": {
      const m = msgOf();
      m.fields = m.fields.filter((f) => { const a = f.offset ?? 0, z = a + fieldSize(f); return !(role.at >= a && role.at < z); });
      break;
    }
    case "text": {
      const m = msgOf();
      const old = m.fields.find((f) => f.index === role.index);
      m.fields = m.fields.filter((f) => f.index !== role.index);
      m.fields.push({ name: old?.name ?? `f${role.index}`, index: role.index, type: role.type });
      m.fields.sort((x, y) => (x.index ?? 0) - (y.index ?? 0));
      break;
    }
    case "notype": {                                 // MSG9: one kind of message - this frame's, with its fields and length
      const m = msgOf();
      const L = frame.len ?? b.length;
      st.type = null;
      st.messages = [{ ...m, id: 0, name: m.name.startsWith("MSG_") ? "MSG" : m.name, size: undefined }];
      if (!st.length) st.size = L;
      break;
    }
    case "start": break;                                                   // the editor re-proposes with this header
  }
  return st;
}

/** The shown frames with their message's field names (and, for text, which field each part is). */
export function withFieldNames(info: MessagesInspect): MessagesInspect {
  const st = info.structure;
  if (!st) return info;
  return { ...info, frames: info.frames.map((f) => {
    const m = st.messages.find((x) => x.name === f.message);
    const names = (m?.fields ?? []).map((x) => x.name);
    const at = f.parts ? f.parts.map((_p, i) => { const k = (m?.fields ?? []).findIndex((x) => x.index === i); return k < 0 ? null : k; }) : undefined;
    return { ...f, fieldNames: names, ...(at ? { fieldAt: at } : {}) };
  }) };
}
