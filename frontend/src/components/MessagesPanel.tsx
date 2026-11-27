import { useEffect, useMemo, useRef, useState } from "react";
import { actions, useApp } from "../store";
import { fmtNum, useT } from "../i18n";
import { api, type AnomalyKind, type LibraryItem, type StreamLink, type StreamRow } from "../api";
import { forgetStream, isMessageLog, keepChannel, messageTypes } from "../messages";
import { Icon } from "../icons";
import { confirmAsk, openMenu } from "./Overlays";
import StreamEditor from "./StreamEditor";
import AddStream, { streamTitle } from "./AddStream";
import PanelFrame, { usePlace } from "../shell/PanelFrame";

/* MSG3 (owner, 2026-11-20: "organise all the message data - MAVLink, NMEA, general messages - in one central
   place"): the Messages panel. What is running now (a link, MAVLink - started and stopped in Live ▾), the byte
   streams of the open files (found by themselves or defined; each opens into its definition, its structure and the
   actions: plot the messages, make the recording, add to the report), the message types of the open logs (MAVLink
   .tlog, DataFlash .bin, .ulg, a link's recording: fields, count, rate) and the structure library. A signal's
   right-click *Decode as messages…* opens the panel on it (msgFocus). */
const bare = (id: string) => id.slice(id.indexOf("/") + 1);
/** a direction's label from its name: "tx_byte RX" -> "RX" (nothing for a stream that has only one) */
const dirLabel = (r: StreamRow) => { const b = bare(r.ids[0]); const rest = r.name.startsWith(b) ? r.name.slice(b.length).trim() : ""; return rest.startsWith("…") ? "" : rest; };
const hex = (v: number) => "0x" + v.toString(16).toUpperCase().padStart(2, "0");

export default function MessagesPanel() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const defs = useApp((s) => s.ws.messageStreams);
  const focus = useApp((s) => s.msgFocus);
  const link = useApp((s) => s.rawlink);
  const mav = useApp((s) => s.mavlink);
  const [rows, setRows] = useState<StreamRow[] | null>(null);
  const [links, setLinks] = useState<StreamLink[]>([]);
  const [lib, setLib] = useState<{ folder: string; items: LibraryItem[] } | null>(null);
  const [open, setOpen] = useState<string[]>([]);
  // streams added by hand (Add a stream, a signal's right-click) - listed though the app did not find them itself
  const [added, setAdded] = useState<string[]>([]);
  const [carries, setCarries] = useState<Record<string, "pair">>({});      // a pair said so in the form
  const [adding, setAdding] = useState<boolean | null>(null);             // the form; null: open while nothing is listed
  const [gen, setGen] = useState<Record<string, number>>({});         // a stream's editor started again (Start over)
  const body = useRef<HTMLDivElement>(null);
  const place = usePlace();
  const files = runs.filter((r) => r.format !== "derived");
  const scan = files.filter((r) => !isMessageLog(r) || r.importSettings?.format === "svraw");     // logs are decoded already
  const seen = scan.map((r) => `${r.id}:${r.version ?? ""}`).join("|") + JSON.stringify(defs ?? []);
  useEffect(() => {
    let live = true;
    if (!scan.length) { setRows([]); return; }
    setRows((r) => r ?? null);
    api.messagesStreams(defs ?? [], scan.map((r) => r.id)).then((r) => { if (live) { setRows(r.streams); setLinks(r.links ?? []); } }).catch(() => { if (live) setRows([]); });
    return () => { live = false; };
  }, [seen]);                                  // eslint-disable-line react-hooks/exhaustive-deps
  const loadLib = () => { api.messagesLibrary().then(setLib).catch(() => {}); };
  useEffect(loadLib, []);
  // a signal's right-click: its editor open, at the top of the view
  useEffect(() => {
    if (!focus) return;
    const key = focus.ids.join(",");
    if (focus.carries) setCarries((c) => ({ ...c, [key]: focus.carries! }));
    setAdding(false);
    setOpen((o) => [key, ...o.filter((k) => k !== key)]);
    setAdded((a) => (a.includes(key) ? a : [key, ...a]));
    useApp.setState({ msgFocus: null });
    window.setTimeout(() => body.current?.querySelector(`[data-key="${CSS.escape(key)}"]`)?.scrollIntoView({ block: "start" }), 50);
  }, [focus]);

  const groups = useMemo(() => {
    const by = new Map<string, StreamRow[]>();
    for (const r of rows ?? []) by.set(r.key, [...(by.get(r.key) ?? []), r]);
    for (const k of [...added, ...(defs ?? []).map((d) => d.sources.join(","))]) if (!by.has(k)) by.set(k, []);   // not found by itself
    return [...by.entries()];
  }, [rows, added, defs]);
  const logs = files.filter(isMessageLog).map((r) => ({ run: r, types: messageTypes(r.signals) })).filter((x) => x.types.length);
  const toggle = (k: string) => setOpen((o) => (o.includes(k) ? o.filter((x) => x !== k) : [...o, k]));
  const defined = new Set((defs ?? []).map((d) => d.sources.join(",")));
  const found = new Set((rows ?? []).map((r) => r.key));
  const toast = (text: string, undo: boolean) => useApp.getState().toast({ kind: "info", text, ...(undo ? { undoesWs: true, action: { label: t("undo"), run: () => useApp.getState().undo() } } : {}) });

  const listed = new Set(groups.flatMap(([k]) => k.split(",")));
  // CH1 / CH8: two streams that look like one link (names, or replies) - one channel in one click (kept at once)
  const held = new Set((defs ?? []).flatMap((d) => d.sources));            // kept: no longer offered (before the list reloads)
  const fileName = (id: string) => runs.find((r) => r.id === id.slice(0, id.indexOf("/")))?.name ?? "";
  const oneChannel = (tx: string, rx: string) => {
    keepChannel(tx, rx);
    setAdded((a) => a.filter((k) => k !== tx && k !== rx));
    useApp.setState({ msgFocus: { ids: [tx, rx], carries: "pair" } });
    toast(t("chMade", { tx: bare(tx), rx: bare(rx) }), true);
  };
  const formOpen = adding ?? (rows !== null && !groups.length);
  const streamMenu = (e: React.MouseEvent, key: string, ids: string[], title: string) => {
    const isDef = defined.has(key), isFound = found.has(key);
    const made = (defs ?? []).find((d) => d.sources.join(",") === key)?.made ?? [];
    const restart = () => { setGen((g) => ({ ...g, [key]: (g[key] ?? 0) + 1 })); };
    openMenu(e, [
      { label: t(open.includes(key) ? "msgpFold" : "msgpOpen"), run: () => toggle(key) },
      { label: t("msgpStartOver"), disabled: !open.includes(key) && !isDef, run: async () => {
        if (isDef && !await confirmAsk(t("msgpStartOver"), t("msgpStartOverAsk", { name: title }) + (made.length ? " " + t("msgpMadeStays") : ""), t("msgpStartOver"), true)) return;
        forgetStream(ids); restart(); setOpen((o) => (o.includes(key) ? o : [...o, key]));
        if (isDef) toast(t("msgpStartedOver", { name: title }), true);
      } },
      { label: "", run: () => {}, sep: true },
      isFound
        ? { label: t("msgpForget"), danger: true, disabled: !isDef, run: async () => {
            if (!await confirmAsk(t("msgpForget"), t("msgpForgetAsk", { name: title }) + (made.length ? " " + t("msgpMadeStays") : ""), t("msgpForget"), true)) return;
            forgetStream(ids); restart(); setOpen((o) => o.filter((k) => k !== key));
            toast(t("msgpForgot", { name: title }), true);
          } }
        : { label: t("msgpRemove"), danger: true, run: async () => {
            if (isDef && !await confirmAsk(t("msgpRemove"), t("msgpRemoveAsk", { name: title }) + (made.length ? " " + t("msgpMadeStays") : ""), t("msgpRemove"), true)) return;
            forgetStream(ids); restart(); setOpen((o) => o.filter((k) => k !== key)); setAdded((a) => a.filter((k) => k !== key));
            toast(t("msgpRemoved", { name: title }), isDef);
          } },
    ]);
  };

  const page = place === "stage";
  // on the page one stream is worked on at a time (the main column); beside the plots each opens in place
  const current = page ? groups.find(([k]) => k === open[0]) : undefined;
  const pick = (k: string) => { setAdding(false); setOpen(page ? [k] : open.includes(k) ? open.filter((x) => x !== k) : [...open, k]); };
  const editor = (key: string, ids: string[]) => <StreamEditor key={gen[key] ?? 0} ids={ids} carries={carries[key]} library={lib?.items ?? []} onLibrary={loadLib} />;
  const dirLines = (rs: StreamRow[]) => rs.map((r) => (
    <div key={r.name} className="msgp-dir">
      {r.error ? <span className="hint">⚠ {r.error}</span> : <>
        <span className="msgp-dir-line">{dirLabel(r) && <><b dir="ltr">{dirLabel(r)}</b>{" "}</>}
          {t("msgpMsgs", { n: fmtNum(r.count ?? 0, lang, 6) })} · <bdi dir="ltr">{r.header}</bdi>
          {r.checksum ? <> · <bdi dir="ltr">{r.checksum}</bdi>{r.errors ? <span className="msgp-bad"> {t("msgpBad", { n: r.errors })}</span> : null}</> : null}
          {" · "}{t("msgpTypes", { n: r.types?.length ?? 0 })}
          {r.anomalies && (r.anomalies.total
            ? <span className="msgp-anom" title={Object.entries(r.anomalies.counts).map(([k, n]) => `${t(`chK_${k as AnomalyKind}` as never)}: ${n}`).join("\n")}>
                {" · "}⚠ {t("chAnomalies", { n: fmtNum(r.anomalies.total, lang, 6) })}
                {r.anomalies.capture ? <span className="ch-chip-cap"> ({t("chChipCapture", { n: r.anomalies.capture })})</span> : null}</span>
            : <span className="msgp-anom ok">{" · "}✓ {t("chNoAnomalies")}</span>)}</span>
        {r.typed && <span className="msgp-types" dir="ltr">{(r.types ?? []).slice(0, 8).map((x) => (
          <span key={x.type} className="chip-s" title={`${x.count}`}>{hex(x.type)} {x.rate ? `${fmtNum(x.rate, lang, 3)} Hz` : `×${x.count}`}</span>))}</span>}
      </>}
    </div>
  ));
  const fileOf = (ids: string[], rs: StreamRow[]) => {
    const names = [...new Set(ids.map((id) => runs.find((r) => r.id === id.slice(0, id.indexOf("/")))?.name).filter(Boolean))];
    return names.length > 1 ? names.join(" + ") : rs[0]?.file ?? names[0];       // CH8: TX and RX from two files
  };

  const running = (link?.running || mav?.running) && (
    <section className="card info msgp-running">
      <h3 className="card-title">{t("msgpRunning")}</h3>
      {link?.running && <p className="card-meta msgp-link"><span className="live-dot on" /> <bdi dir="ltr">{link.conn}{link.peer ? ` ← ${link.peer}` : ""}</bdi>{" · "}
        {link.sinceData == null ? t("mavWaiting") : t("linkStats", { kb: Math.round((link.bytes ?? 0) / 1024), rate: Math.round(link.rate ?? 0) })}
        {link.error ? ` · ${link.error}` : ""}</p>}
      {mav?.running && <p className="card-meta msgp-mav"><span className="live-dot on" /> MAVLink <bdi dir="ltr">{mav.conn}</bdi>{" · "}
        {mav.sinceData == null ? t("mavWaiting") : t("msgpMavStats", { n: mav.frames ?? 0, kb: Math.round((mav.bytes ?? 0) / 1024) })}</p>}
      <p className="card-meta">{t("msgpRunningHint")}</p>
    </section>
  );
  const addForm = <AddStream files={files} listed={listed} open={formOpen && files.length > 0} onOpen={setAdding}
    onAdd={(ids, c) => { if (c === "pair") keepChannel(ids[0], ids[1]); useApp.setState({ msgFocus: { ids, ...(c ? { carries: c } : {}) } }); }} />;

  const streams = (
    <section className="msgp-sec msgp-streams">
      <div className="msgp-sec-head">
        <h3 className="alist-head">{t("msgpStreams")}</h3>
        <button className="btn outline sm msgp-add" onClick={() => setAdding(!formOpen)} aria-expanded={formOpen} disabled={!files.length}><Icon.Plus /> {t("msgpAdd")}</button>
      </div>
      {!page && <p className="hint">{t("msgpStreamsHint")}</p>}
      {rows === null && !groups.length && <p className="hint">{t("msgpLooking")}</p>}
      {rows !== null && !groups.length && <p className="hint msgp-none">{t("msgpNoStreams")}</p>}
      {!page && addForm}
      {links.filter((l) => !held.has(l.tx) && !held.has(l.rx)).map((l) => (
        <div key={l.tx} className="card info ch-offer" data-tx={l.tx} data-rx={l.rx}>
          <span>{l.why === "clock" ? t("chOfferClock", { tx: bare(l.tx), rx: bare(l.rx), a: fileName(l.tx), b: fileName(l.rx), s: (l.shift ?? 0).toFixed(3) })
            : l.tx.slice(0, l.tx.indexOf("/")) === l.rx.slice(0, l.rx.indexOf("/"))
            ? t(l.why === "replies" ? "chOfferReplies" : "chOffer", { tx: bare(l.tx), rx: bare(l.rx) })
            : t("chOfferFiles", { tx: bare(l.tx), rx: bare(l.rx), a: fileName(l.tx), b: fileName(l.rx) })}</span>
          <button className="btn primary sm ch-make" onClick={() => oneChannel(l.tx, l.rx)}>{t("chMake")}</button>
        </div>))}
      {groups.map(([key, rs]) => {
        const ids = key.split(",");
        const on = page ? current?.[0] === key && !formOpen : open.includes(key);
        const title = streamTitle(ids);
        return (
          <div key={key} className={`msgp-stream${on ? (page ? " chosen" : " open") : ""}`} data-key={key}>
            <div className="msgp-stream-top">
              <button className="msgp-stream-head" aria-expanded={on} aria-current={page && on ? "true" : undefined} onClick={() => pick(key)}>
                <Icon.Chevron className="msgp-chev" />
                <span className="msgp-name"><bdi dir="ltr">{title}</bdi>{defined.has(key) && <span className="tag">{t("msgpDefined")}</span>}
                  {!found.has(key) && <span className="tag">{t("msgpByHand")}</span>}</span>
                <span className="msgp-file">{fileOf(ids, rs)}</span>
              </button>
              <button className="iconbtn msgp-stream-more" aria-label={t("msgpStreamActions", { name: title })} title={t("msgpStreamActions", { name: title })}
                onClick={(e) => streamMenu(e, key, ids, title)}><Icon.More /></button>
            </div>
            {dirLines(rs)}
            {!page && on && editor(key, ids)}
          </div>
        );
      })}
    </section>
  );

  const logList = logs.length > 0 && (
    <section className="msgp-sec msgp-logs">
      <h3 className="alist-head">{t("msgpLogs")}</h3>
      <p className="hint">{t("msgpLogsHint")}</p>
      {logs.map(({ run, types }) => (
        <details key={run.id} className="msgp-log" open={logs.length === 1}>
          <summary><span className="msgp-name">{run.name}</span> <span className="msgp-file">{t("msgpTypes", { n: types.length })}</span></summary>
          <table className="msgp-table">
            <thead><tr><th>{t("msgpType")}</th><th>{t("msgpFields")}</th><th>{t("msgpCount")}</th><th>{t("msgpRate")}</th></tr></thead>
            <tbody>{types.map((x) => (
              <tr key={x.type} tabIndex={0} title={x.ids.map(bare).join("\n")}
                onClick={() => actions.plotsInNewTab([{ title: x.type, ids: x.ids.slice(0, 6) }], x.type)}
                onKeyDown={(e) => { if (e.key === "Enter") actions.plotsInNewTab([{ title: x.type, ids: x.ids.slice(0, 6) }], x.type); }}>
                <td dir="ltr">{x.type}</td><td>{x.ids.length}</td><td>{fmtNum(x.count, lang, 6)}</td><td>{x.rate ? fmtNum(x.rate, lang, 3) : "—"}</td>
              </tr>))}</tbody>
          </table>
        </details>
      ))}
    </section>
  );

  const library = (
    <section className="msgp-sec msgp-lib">
      <h3 className="alist-head">{t("msgpLib")}</h3>
      <p className="hint">{t("msgpLibHint")}</p>
      <ul className="msgp-lib-list">
        {(lib?.items ?? []).map((i) => (
          <li key={i.key} title={i.path ?? ""}>
            <span className="msgp-name" dir="ltr">{i.name}</span>
            <span className="tag">{t(i.source === "builtin" ? "msgpBuiltin" : i.source === "readers" ? "msgpIcd" : "msgpYours")}</span>
            {i.error ? <span className="msgp-bad">⚠ {i.error}</span> : <span className="msgp-file">{t("msgpLibMsgs", { n: i.messages ?? 0 })}</span>}
          </li>
        ))}
      </ul>
      {lib && <p className="hint msgp-folder"><bdi dir="ltr">{lib.folder}</bdi>{" "}
        <button className="linklike" onClick={() => api.messagesLibraryReveal().catch((e) => useApp.getState().toast({ kind: "error", text: String((e as Error).message) }))}>{t("msgpOpenFolder")}</button></p>}
    </section>
  );

  // the page: what there is in the index (streams, the library), the thing worked on in the main column - the form
  // that adds a stream, the stream chosen, or (nothing chosen) what is running and the logs' messages
  const main = page ? <div className="msgp-body" ref={body}>
    {running}
    {formOpen ? addForm : current ? <div className="msgp-stream open msgp-current" data-key={current[0]}>
        <div className="msgp-current-head"><h3><bdi dir="ltr">{streamTitle(current[0].split(","))}</bdi></h3>
          <span className="msgp-file">{fileOf(current[0].split(","), current[1])}</span></div>
        {editor(current[0], current[0].split(","))}
      </div>
      : <>{groups.length > 0 && <p className="hint msgp-choose">{t("msgpChoose")}</p>}{logList}</>}
  </div> : null;
  const index = page ? <>{streams}{library}</> : <div ref={body} className="msgp-side">{running}{streams}{logList}{library}</div>;
  return <PanelFrame id="messages" title={t("msgPanel")} className="messages" bodyClass="msgp-body" main={main} index={index} />;
}
