import { useEffect, useMemo, useState } from "react";
import { pickPath, useApp } from "../store";
import { fmtNum, useT } from "../i18n";
import { api, type LibraryItem, type MessagesInspect } from "../api";
import type { MessageStream, Structure } from "../store/model";
import { addStreamToReport, applyRole, decodeAsMessages, directionCandidates, guessDirections, makeRecording, plotMessage, saveToLibrary, streamFor, streamsOf, withFieldNames } from "../messages";
import StructureEditor from "./StructureEditor";
import ByteView, { type ByteRole } from "./ByteView";
import { openMenu } from "./Overlays";

/* MSG1 (owner, 2026-11-19: "how is a signal defined as a kind of message - only TX, only RX, or both with another
   column that says the direction each time"): what the byte signal carries, its direction column and which of its
   values is TX. MSG2: each direction's structure -> a recording. MSG3: in the Messages panel, the structure taken
   from the library. MSG4 (owner, 2026-11-21: "alone it was not clear how to go from the raw signal to the variables
   of the recording and the message's definition"): four numbered steps, each saying what to do -
   1 what the signal carries, 2 the messages in the bytes (the patterns that recur, the first messages byte by byte,
   a click on a byte says what it is), 3 the variables (each field's value in the first messages, the form / JSON),
   4 the recording (made, saved as CSV / Parquet / MAT / HDF5, plotted, in the report). */
const CHECKSUMS = ["", "none", "sum8", "xor8", "negsum8", "notsum8", "crc16ccitt", "crc16modbus", "fletcher16"];
const hex2 = (v: number) => v.toString(16).toUpperCase().padStart(2, "0");

export default function StreamEditor({ ids, library, onLibrary }: { ids: string[]; library: LibraryItem[]; onLibrary: () => void }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const [def, setDef] = useState<MessageStream>(() => streamFor(ids));
  const [busy, setBusy] = useState(false);
  const [side, setSide] = useState<string>("");
  const [info, setInfo] = useState<MessagesInspect | null>(null);
  const [looking, setLooking] = useState(false);
  // the definition kept in the session changed elsewhere (Undo, a recording made): start from it again
  const kept = useApp((s) => (s.ws.messageStreams ?? []).find((m) => m.sources.join(",") === ids.join(",")));
  useEffect(() => { if (kept) setDef(kept); }, [kept]);
  const one = def.sources.length === 1;
  const dirs = one ? directionCandidates(def.sources[0]) : [];
  const dirSig = runs.flatMap((r) => r.signals).find((s) => s.id === def.dir);
  const labels = dirSig?.labels ?? {};
  const set = (p: Partial<MessageStream>) => setDef((d) => ({ ...d, ...p }));
  const both = def.carries === "both";
  // MSG5: the direction column's values (any column: 2..32 of them), asked for when it is chosen; TX and RX guessed
  // when not said yet (older sessions with a text column keep "every other value is RX")
  const [dirVals, setDirVals] = useState<{ values: { v: number; n: number; label: string | null }[]; distinct: number; most: number } | null>(null);
  useEffect(() => {
    if (!both || !def.dir) { setDirVals(null); return; }
    let live = true;
    api.directionValues(def.dir).then((r) => {
      if (!live) return;
      setDirVals(r);
      setDef((d) => {
        if (d.dir !== def.dir || !r.values.length) return d;
        const has = (v: number | null | undefined) => v != null && r.values.some((x) => x.v === v);
        const g = guessDirections(r.values);
        const tx = has(d.txValue) ? d.txValue! : g.tx;
        const legacy = d.rxValue === undefined && Object.keys(labels).length > 0 && has(d.txValue);
        const rx = legacy ? undefined : has(d.rxValue) && d.rxValue !== tx ? d.rxValue! : r.values.find((x) => x.v !== tx)?.v ?? null;
        return tx === d.txValue && rx === d.rxValue ? d : { ...d, txValue: tx, rxValue: rx };
      });
    }, () => live && setDirVals(null));
    return () => { live = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [both, def.dir]);
  const valName = (x: { v: number; label: string | null }) => x.label ? `${x.label} (${fmtNum(x.v, lang)})` : fmtNum(x.v, lang);
  const leftOut = dirVals && def.rxValue != null ? dirVals.values.filter((x) => x.v !== def.txValue && x.v !== def.rxValue).reduce((a, x) => a + x.n, 0) : 0;
  const can = !both || !!def.dir;
  const eff = { ...def, dir: both ? def.dir : null, header: def.header?.trim() || undefined, checksum: def.checksum || undefined };
  const sides = streamsOf(eff).map((x) => x.label);
  const cur = sides.includes(side) ? side : sides[0];
  const stream = streamsOf(eff).find((x) => x.label === cur);
  const structure = def.structures?.[cur];
  const setStructure = (st: Structure | null) => setDef((d) => {
    const all = { ...(d.structures ?? {}) };
    if (st) all[cur] = st; else delete all[cur];
    return { ...d, structures: all };
  });
  const toast = (e: unknown) => useApp.getState().toast({ kind: "error", text: String((e as Error).message) });

  // steps 2 and 3 follow the definition: the stream looked at again a moment after anything changes; with no
  // structure yet the app proposes one (and it becomes the one being edited)
  const look = JSON.stringify([stream?.sources, stream?.params, structure ?? null, can]);
  useEffect(() => {
    if (!can || !stream) { setInfo(null); return; }
    let live = true;
    const id = window.setTimeout(async () => {
      setLooking(true);
      try {
        const r = withFieldNames(await api.messagesInspect(stream.sources, stream.params, structure ?? null, 12));
        if (!live) return;
        setInfo(r);
        if (!structure && r.suggested && r.structure) setStructure(r.structure);
      } catch (e) {
        if (live) setInfo({ bytes: 0, head: [], text: false, patterns: [], frames: [], summary: null, error: String((e as Error).message) });
      } finally { if (live) setLooking(false); }
    }, 350);
    return () => { live = false; window.clearTimeout(id); };
  }, [look]);                                   // eslint-disable-line react-hooks/exhaustive-deps

  const onRole = (fi: number, role: ByteRole) => {
    if (role.kind === "start") {               // a message starts at this byte: its 2 bytes are the header, proposed again
      const h = info?.head ?? [];
      set({ header: hex2(h[role.at]) + hex2(h[role.at + 1] ?? 0) });
      setStructure(null);
      return;
    }
    if (!structure || !info?.frames[fi]) return;
    setStructure(applyRole(structure, info.frames[fi], role));
  };
  const usePattern = (e: React.MouseEvent, hex: string, bytes: number) => openMenu(e, [
    { label: t("msgUseHeader"), run: () => {
      if (bytes === 2) { set({ header: hex.replace(/ /g, "") }); setStructure(null); }       // proposed again around it
      else if (structure) setStructure({ ...structure, header: hex.replace(/ /g, "") });
    } },
    { label: t("msgUseFooter"), disabled: !structure || structure.kind !== "binary", run: () => { if (structure) setStructure({ ...structure, footer: hex.replace(/ /g, "") }); } },
  ]);
  const fromLibrary = async (key: string) => {
    if (!key) return;
    if (key === "file") {
      const p = await pickPath({ mode: "open", title: t("msgStructFile"), exts: [".json"] });
      if (!p) return;
      try { setStructure((await api.messagesStructure(p)).structure); } catch (e) { toast(e); }
      return;
    }
    try { setStructure((await api.messagesLibraryGet(key)).structure); } catch (e) { toast(e); }
  };
  const run = async (f: () => Promise<unknown>) => { setBusy(true); try { await f(); } finally { setBusy(false); } };
  const made = def.made?.find((m) => m.label === cur);
  const madeRun = made ? runs.find((r) => r.id === made.run) : undefined;
  const saveFile = async () => {
    if (!madeRun) return;
    const path = await pickPath({ mode: "save", title: t("msgSaveFile"), exts: [".csv", ".parquet", ".mat", ".h5"], defaultName: madeRun.name.replace(/[\\/:*?"<>|]+/g, "_") + ".csv" });
    if (!path) return;
    await run(async () => {
      try {
        const r = await api.exportRecording({ path, signals: madeRun.signals.map((s) => ({ id: s.id, label: s.name })) });
        useApp.getState().toast({ kind: "info", text: t("msgSavedFile", { path: r.path, n: r.rows }) });
      } catch (e) { toast(e); }
    });
  };
  // step 3: each message's first shown frames, value by value
  const byMsg = useMemo(() => (structure?.messages ?? []).map((m) => ({ m, frames: (info?.frames ?? []).filter((f) => f.message === m.name && f.status === "ok").slice(0, 4) })), [structure, info]);
  const sum = info?.summary;
  const unknownN = sum ? Object.values(sum.unknown).reduce((a, b) => a + b, 0) : 0;
  const fmtV = (v: number | string | null) => (v === null || v === undefined ? "—" : typeof v === "string" ? v : fmtNum(v, lang, 6));

  return (
    <div className="msgp-edit">
      <ol className="msg-steps">
        <li className="msg-step msg-step-1">
          <h4><span className="msg-n">1</span>{t("msgStep1")}</h4>
          <p className="hint">{t("msgStep1Hint")}</p>
          {def.carries === "pair" && <p className="hint msg-pair-order">TX: <bdi dir="ltr">{bare(def.sources[0])}</bdi> · RX: <bdi dir="ltr">{bare(def.sources[1])}</bdi>{" "}
            <button className="linklike" onClick={() => set({ sources: [def.sources[1], def.sources[0]] })}>{t("msgDlgSwap")}</button></p>}
          <fieldset className="msg-carries">
            <legend>{t("msgDlgCarries")}</legend>
            {(["tx", "rx", "both", ...(def.sources.length === 2 ? ["pair" as const] : [])] as const).map((c) => (
              <label key={c}><input type="radio" name={`msg-carries-${ids.join(",")}`} value={c} checked={def.carries === c} disabled={c === "both" && !one}
                onChange={() => set({ carries: c, dir: c === "both" ? def.dir ?? dirs[0]?.id ?? null : def.dir })} /> {t(c === "tx" ? "msgDlgTx" : c === "rx" ? "msgDlgRx" : c === "pair" ? "msgDlgPair" : "msgDlgBoth")}</label>
            ))}
          </fieldset>
          {both && (
            <div className="cmpobj-grid">
              <label className="cmpobj-label" htmlFor="msg-dir">{t("msgDlgDir")}</label>
              {dirs.length ? (
                <select id="msg-dir" className="msg-dir" value={def.dir ?? ""} onChange={(e) => set({ dir: e.target.value, txValue: null, rxValue: null })}>
                  {dirs.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              ) : <span className="hint msg-nodir">{t("msgDlgNoDir")}</span>}
              {dirSig && dirVals && !dirVals.values.length && (
                <span className="hint msg-dirbad" style={{ gridColumn: "1 / -1" }}>{t("msgDlgDirBad", { n: dirVals.distinct, most: dirVals.most })}</span>)}
              {dirSig && dirVals && dirVals.values.length > 0 && <>
                <label className="cmpobj-label" htmlFor="msg-txv">{t("msgDlgTxIs")}</label>
                <select id="msg-txv" className="msg-txv" value={String(def.txValue ?? "")}
                  onChange={(e) => { const tx = Number(e.target.value); set({ txValue: tx, ...(def.rxValue === tx ? { rxValue: dirVals.values.find((x) => x.v !== tx)?.v ?? null } : {}) }); }}>
                  {dirVals.values.map((x) => <option key={x.v} value={String(x.v)}>{valName(x)} · {fmtNum(x.n, lang)}</option>)}
                </select>
                <label className="cmpobj-label" htmlFor="msg-rxv">{t("msgDlgRxIs")}</label>
                <select id="msg-rxv" className="msg-rxv" value={def.rxValue == null ? "" : String(def.rxValue)}
                  onChange={(e) => set({ rxValue: e.target.value === "" ? undefined : Number(e.target.value) })}>
                  {Object.keys(labels).length > 0 && def.rxValue == null && <option value="">{t("msgDlgRxOthers")}</option>}
                  {dirVals.values.filter((x) => x.v !== def.txValue).map((x) => <option key={x.v} value={String(x.v)}>{valName(x)} · {fmtNum(x.n, lang)}</option>)}
                </select>
                {leftOut > 0 && <span className="hint msg-dirleft" style={{ gridColumn: "1 / -1" }}>{t("msgDlgDirLeft", { n: fmtNum(leftOut, lang), k: dirVals.values.length - 2 })}</span>}
              </>}
            </div>
          )}
        </li>

        <li className="msg-step msg-step-2">
          <h4><span className="msg-n">2</span>{t("msgStep2")}</h4>
          <p className="hint">{t("msgStep2Hint")}</p>
          {sides.length > 1 && (
            <div className="seg msg-sides" role="group" aria-label={t("msgDirOf")}>
              {sides.map((l) => <button key={l} className={l === cur ? "on" : ""} aria-pressed={l === cur} onClick={() => setSide(l)}>{l}</button>)}
            </div>
          )}
          {!can ? <p className="hint">{t("msgNeedDir")}</p> : <>
            {info?.patterns?.length ? (
              <div className="msg-pats">
                <span className="hint">{t("msgPatterns")}</span>
                {info.patterns.map((p) => (
                  <button key={p.hex} className={`chip-s msg-pat${p.role ? ` role-${p.role === "start" ? "header" : p.role}` : ""}`} dir="ltr"
                    title={t("msgPatternTitle", { n: p.count, every: p.every, pc: Math.round(p.regular * 100) })
                      + (p.afterPause != null ? "\n" + t("msgPatPauses", { a: Math.round(p.afterPause * 100), b: Math.round((p.beforePause ?? 0) * 100) }) : "")}
                    onClick={(e) => usePattern(e, p.hex, p.bytes)}>
                    {p.hex}{p.role ? ` · ${t(p.role === "header" ? "msgRole_header" : p.role === "footer" ? "msgRole_footer" : "msgPatStart")}`
                      : p.time ? ` · ${t(p.time === "start" ? "msgPatTimeStart" : "msgPatTimeEnd")}` : ""} <span className="msg-pat-n">×{fmtNum(p.count, lang, 6)}</span>
                  </button>
                ))}
              </div>
            ) : null}
            {info?.pauses && <p className="hint msg-bytime">{t("msgByTime")}</p>}
            {structure && structure.kind === "binary" && (
              <p className="hint msg-framing-line" dir="auto">{t("msgFramingLine", {
                h: structure.header ?? "—",
                len: structure.length ? t("msgLenByte", { at: structure.length.offset, add: structure.length.add }) : structure.size ? t("msgFixedSize", { n: structure.size }) : structure.footer ? t("msgToFooter") : t("msgSizePerType"),
                type: structure.type ? t("msgTypeByte", { at: structure.type.offset }) : t("msgOneType"),
                cs: typeof structure.checksum === "object" && structure.checksum ? structure.checksum.scheme : t("msgNone2"),
                f: structure.footer || "—" })}</p>
            )}
            {looking && !info && <p className="hint">{t("msgpLooking")}</p>}
            {info?.error && <p className="hint msg-inspect-err">⚠ {info.error}</p>}
            {info && <ByteView info={info} onRole={onRole} />}
            {sum && (
              <p className="hint msg-summary">{t("msgSummary", { n: fmtNum(sum.messages, lang, 6), bad: sum.bad, unknown: unknownN, outside: sum.outside })}</p>
            )}
            <details className="msg-framing">
              <summary>{t("msgDlgFraming")}</summary>
              <div className="cmpobj-grid">
                <label className="cmpobj-label" htmlFor="msg-header">{t("msgDlgHeader")}</label>
                <input id="msg-header" className="msg-header" dir="ltr" placeholder={t("msgDlgAuto")} value={def.header ?? ""} onChange={(e) => set({ header: e.target.value })} />
                <label className="cmpobj-label" htmlFor="msg-cs">{t("msgDlgChecksum")}</label>
                <select id="msg-cs" className="msg-cs" value={def.checksum ?? ""} onChange={(e) => set({ checksum: e.target.value })}>
                  {CHECKSUMS.map((c) => <option key={c} value={c}>{c ? c : t("msgDlgAuto")}</option>)}
                </select>
              </div>
            </details>
          </>}
        </li>

        <li className="msg-step msg-step-3 msg-structure">
          <h4><span className="msg-n">3</span>{t("msgStep3")}</h4>
          <p className="hint">{t("msgStep3Hint")}</p>
          <div className="msg-struct-tools">
            <button className="btn outline sm msg-propose" disabled={busy || !can} onClick={() => { setStructure(null); }}>{t("msgProposeAgain")}</button>
            <select className="msg-lib" aria-label={t("msgpFromLib")} value="" onChange={(e) => void fromLibrary(e.target.value)}>
              <option value="">{t("msgpFromLib")}</option>
              {library.filter((i) => !i.error).map((i) => <option key={i.key} value={i.key}>{i.name}</option>)}
              <option value="file">{t("msgpFile")}</option>
            </select>
            <button className="btn outline sm msg-save" disabled={!structure} onClick={async () => { if (structure && await saveToLibrary(structure)) onLibrary(); }}>{t("msgpSaveLib")}</button>
          </div>
          {structure && byMsg.some((x) => x.frames.length) && (
            <div className="msg-values">
              {byMsg.filter((x) => x.frames.length).map(({ m, frames }) => (
                <table key={m.name} className="msg-values-t" dir="ltr">
                  <caption>{m.name}{sum?.byMessage[m.name] ? ` · ×${fmtNum(sum.byMessage[m.name], lang, 6)}` : ""}</caption>
                  <thead><tr><th>t (s)</th>{m.fields.map((f) => <th key={f.name}>{f.name}{f.unit ? ` [${f.unit}]` : ""}</th>)}</tr></thead>
                  <tbody>{frames.map((f, k) => (
                    <tr key={k}><td>{f.t.toFixed(3)}</td>{m.fields.map((x, j) => <td key={x.name}>{fmtV(f.values[j])}</td>)}</tr>
                  ))}</tbody>
                </table>
              ))}
              {byMsg.some((x) => x.frames.length && !x.m.fields.length) && <p className="hint">{t("msgNoFieldsYet")}</p>}
            </div>
          )}
          {structure && <StructureEditor key={cur + (structure.name ?? "")} value={structure} onChange={setStructure} />}
        </li>

        <li className="msg-step msg-step-4">
          <h4><span className="msg-n">4</span>{t("msgStep4")}</h4>
          <p className="hint">{t("msgStep4Hint")}</p>
          {/* MSG7 (owner, 2026-11-22): what passed and how often - each message with its count and share; ticked ones go
              into the recording, Plot shows one message's values; types the structure does not describe, said */}
          {sum && sum.messages > 0 && structure && (
            <div className="msg-list">
              <span className="hint">{t("msgListTitle", { n: fmtNum(sum.messages + unknownN, lang, 6) })}</span>
              <table className="msg-list-t">
                <tbody>
                  {[...structure.messages.map((m) => ({ name: m.name, n: sum.byMessage[m.name] ?? 0, known: true })),
                    ...Object.entries(sum.unknown).map(([k, n]) => ({ name: k, n, known: false }))]
                    .filter((x) => x.n > 0).sort((a, b) => b.n - a.n).map((x) => {
                      const skipped = !!def.skip?.[cur]?.includes(x.name);
                      const pc = (100 * x.n) / Math.max(1, sum.messages + unknownN);
                      return (
                        <tr key={x.name} className={`msg-list-row${x.known ? "" : " unknown"}${skipped ? " off" : ""}`}>
                          <td>{x.known
                            ? <input type="checkbox" className="msg-list-in" checked={!skipped} aria-label={t("msgListIn", { msg: x.name })} title={t("msgListIn", { msg: x.name })}
                                onChange={(e) => setDef((d) => {
                                  const cur0 = new Set(d.skip?.[cur] ?? []);
                                  if (e.target.checked) cur0.delete(x.name); else cur0.add(x.name);
                                  return { ...d, skip: { ...(d.skip ?? {}), [cur]: [...cur0] } };
                                })} />
                            : null}</td>
                          <th scope="row" dir="ltr">{x.known ? x.name : t("msgListUnknown", { id: x.name })}</th>
                          <td className="msg-list-bar"><span style={{ width: `${Math.max(1, pc)}%` }} /></td>
                          <td className="msg-list-n">{fmtNum(x.n, lang, 6)} · {pc < 1 ? pc.toFixed(1) : Math.round(pc)}%</td>
                          <td>{x.known
                            ? <button className="btn outline sm msg-list-plot" disabled={busy || skipped || !can}
                                title={skipped ? t("msgListPlotOff") : t("msgListPlotHint", { msg: x.name })}
                                onClick={() => run(() => plotMessage(eff, cur, x.name))}>{t("msgListPlot")}</button>
                            : <span className="hint">{t("msgListDescribe")}</span>}</td>
                        </tr>);
                    })}
                </tbody>
              </table>
              <p className="hint">{t("msgListHint")}</p>
            </div>
          )}
          <div className="msgp-actions">
            <button className="btn primary sm msg-make" disabled={busy || !can || !structure} onClick={() => run(() => makeRecording(eff, cur))}>{made ? t("msgMakeAgain") : t("msgMake")}</button>
            <button className="btn outline sm msg-savefile" disabled={busy || !madeRun} title={madeRun ? "" : t("msgSaveFileFirst")} onClick={saveFile}>{t("msgSaveFile")}</button>
            <button className="btn outline sm msg-go" disabled={busy || !can} onClick={() => run(() => decodeAsMessages(eff))}>{t("msgpPlot")}</button>
            <button className="btn outline sm msg-report" disabled={busy || !can} onClick={() => addStreamToReport(eff)}>{t("msgpAddReport")}</button>
          </div>
          {madeRun && <p className="hint msg-made">✓ {t("msgMadeLine", { name: madeRun.name, k: madeRun.signals.length })}</p>}
          <p className="hint">{t("msgDlgHint")}</p>
        </li>
      </ol>
    </div>
  );
}

const bare = (id: string) => id.slice(id.indexOf("/") + 1);
