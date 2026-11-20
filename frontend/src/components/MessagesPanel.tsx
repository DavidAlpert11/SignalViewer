import { useEffect, useMemo, useRef, useState } from "react";
import { actions, useApp } from "../store";
import { fmtNum, useT } from "../i18n";
import { api, type LibraryItem, type StreamRow } from "../api";
import { isMessageLog, messageTypes } from "../messages";
import StreamEditor from "./StreamEditor";

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
  const [lib, setLib] = useState<{ folder: string; items: LibraryItem[] } | null>(null);
  const [open, setOpen] = useState<string[]>([]);
  const body = useRef<HTMLDivElement>(null);
  const files = runs.filter((r) => r.format !== "derived");
  const scan = files.filter((r) => !isMessageLog(r) || r.importSettings?.format === "svraw");     // logs are decoded already
  const seen = scan.map((r) => `${r.id}:${r.version ?? ""}`).join("|") + JSON.stringify(defs ?? []);
  useEffect(() => {
    let live = true;
    if (!scan.length) { setRows([]); return; }
    setRows((r) => r ?? null);
    api.messagesStreams(defs ?? [], scan.map((r) => r.id)).then((r) => { if (live) setRows(r.streams); }).catch(() => { if (live) setRows([]); });
    return () => { live = false; };
  }, [seen]);                                  // eslint-disable-line react-hooks/exhaustive-deps
  const loadLib = () => { api.messagesLibrary().then(setLib).catch(() => {}); };
  useEffect(loadLib, []);
  // a signal's right-click: its editor open, at the top of the view
  useEffect(() => {
    if (!focus) return;
    const key = focus.ids.join(",");
    setOpen((o) => [key, ...o.filter((k) => k !== key)]);
    useApp.setState({ msgFocus: null });
    window.setTimeout(() => body.current?.querySelector(`[data-key="${CSS.escape(key)}"]`)?.scrollIntoView({ block: "start" }), 50);
  }, [focus]);

  const groups = useMemo(() => {
    const by = new Map<string, StreamRow[]>();
    for (const r of rows ?? []) by.set(r.key, [...(by.get(r.key) ?? []), r]);
    for (const k of open) if (!by.has(k)) by.set(k, []);      // opened on a signal not found by itself
    return [...by.entries()];
  }, [rows, open]);
  const logs = files.filter(isMessageLog).map((r) => ({ run: r, types: messageTypes(r.signals) })).filter((x) => x.types.length);
  const toggle = (k: string) => setOpen((o) => (o.includes(k) ? o.filter((x) => x !== k) : [...o, k]));
  const defined = new Set((defs ?? []).map((d) => d.sources.join(",")));

  return (
    <aside className="side messages" aria-label={t("msgPanel")}>
      <div className="side-head"><h2>{t("msgPanel")}</h2></div>
      <div className="msgp-body" ref={body}>
        {(link?.running || mav?.running) && (
          <section className="card info msgp-running">
            <h3 className="card-title">{t("msgpRunning")}</h3>
            {link?.running && <p className="card-meta msgp-link"><span className="live-dot on" /> <bdi dir="ltr">{link.conn}{link.peer ? ` ← ${link.peer}` : ""}</bdi>{" · "}
              {link.sinceData == null ? t("mavWaiting") : t("linkStats", { kb: Math.round((link.bytes ?? 0) / 1024), rate: Math.round(link.rate ?? 0) })}
              {link.error ? ` · ${link.error}` : ""}</p>}
            {mav?.running && <p className="card-meta msgp-mav"><span className="live-dot on" /> MAVLink <bdi dir="ltr">{mav.conn}</bdi>{" · "}
              {mav.sinceData == null ? t("mavWaiting") : t("msgpMavStats", { n: mav.frames ?? 0, kb: Math.round((mav.bytes ?? 0) / 1024) })}</p>}
            <p className="card-meta">{t("msgpRunningHint")}</p>
          </section>
        )}

        <section className="msgp-sec msgp-streams">
          <h3 className="alist-head">{t("msgpStreams")}</h3>
          <p className="hint">{t("msgpStreamsHint")}</p>
          {rows === null && !groups.length && <p className="hint">{t("msgpLooking")}</p>}
          {rows !== null && !groups.length && <p className="hint msgp-none">{t("msgpNoStreams")}</p>}
          {groups.map(([key, rs]) => {
            const ids = key.split(",");
            const on = open.includes(key);
            const title = ids.length === 1 ? bare(ids[0]) : ids.length === 2 ? ids.map(bare).join(" + ") : `${bare(ids[0])}…${bare(ids[ids.length - 1])}`;
            const file = rs[0]?.file ?? runs.find((r) => r.id === ids[0].slice(0, ids[0].indexOf("/")))?.name;
            return (
              <div key={key} className={`msgp-stream${on ? " open" : ""}`} data-key={key}>
                <button className="msgp-stream-head" aria-expanded={on} onClick={() => toggle(key)}>
                  <span className="msgp-name"><bdi dir="ltr">{title}</bdi>{defined.has(key) && <span className="tag">{t("msgpDefined")}</span>}</span>
                  <span className="msgp-file">{file}</span>
                </button>
                {rs.map((r) => (
                  <div key={r.name} className="msgp-dir">
                    {r.error ? <span className="hint">⚠ {r.error}</span> : <>
                      <span className="msgp-dir-line">{dirLabel(r) && <><b dir="ltr">{dirLabel(r)}</b>{" "}</>}
                        {t("msgpMsgs", { n: fmtNum(r.count ?? 0, lang, 6) })} · <bdi dir="ltr">{r.header}</bdi>
                        {r.checksum ? <> · <bdi dir="ltr">{r.checksum}</bdi>{r.errors ? <span className="msgp-bad"> {t("msgpBad", { n: r.errors })}</span> : null}</> : null}
                        {" · "}{t("msgpTypes", { n: r.types?.length ?? 0 })}</span>
                      {r.typed && <span className="msgp-types" dir="ltr">{(r.types ?? []).slice(0, 8).map((x) => (
                        <span key={x.type} className="chip-s" title={`${x.count}`}>{hex(x.type)} {x.rate ? `${fmtNum(x.rate, lang, 3)} Hz` : `×${x.count}`}</span>))}</span>}
                    </>}
                  </div>
                ))}
                {on && <StreamEditor ids={ids} library={lib?.items ?? []} onLibrary={loadLib} />}
              </div>
            );
          })}
        </section>

        {logs.length > 0 && (
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
        )}

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
      </div>
    </aside>
  );
}
