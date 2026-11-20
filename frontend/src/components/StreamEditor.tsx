import { useEffect, useState } from "react";
import { pickPath, useApp } from "../store";
import { useT } from "../i18n";
import { api, type LibraryItem } from "../api";
import type { MessageStream, Structure } from "../store/model";
import { addStreamToReport, decodeAsMessages, directionCandidates, makeRecording, saveToLibrary, streamFor, streamsOf } from "../messages";
import StructureEditor from "./StructureEditor";

/* MSG1 (owner, 2026-11-19: "how is a signal defined as a kind of message - only TX, only RX, or both with another
   column that says the direction each time"): what the byte signal carries, its direction column and which of its
   values is TX; the framing found by itself unless a header / checksum is given. MSG2: each direction's structure
   -> a recording. MSG3: in the Messages panel (it was a dialog), the structure taken from the library. */
const CHECKSUMS = ["", "none", "sum8", "xor8", "negsum8", "notsum8", "crc16ccitt", "crc16modbus", "fletcher16"];

export default function StreamEditor({ ids, library, onLibrary }: { ids: string[]; library: LibraryItem[]; onLibrary: () => void }) {
  const t = useT();
  const runs = useApp((s) => s.runs);
  const [def, setDef] = useState<MessageStream>(() => streamFor(ids));
  const [busy, setBusy] = useState(false);
  const [side, setSide] = useState<string>("");
  // the definition kept in the session changed elsewhere (Undo, a recording made): start from it again
  const kept = useApp((s) => (s.ws.messageStreams ?? []).find((m) => m.sources.join(",") === ids.join(",")));
  useEffect(() => { if (kept) setDef(kept); }, [kept]);
  const one = def.sources.length === 1;
  const dirs = one ? directionCandidates(def.sources[0]) : [];
  const dirSig = runs.flatMap((r) => r.signals).find((s) => s.id === def.dir);
  const labels = dirSig?.labels ?? {};
  const set = (p: Partial<MessageStream>) => setDef({ ...def, ...p });
  const both = def.carries === "both";
  const can = !both || !!def.dir;
  const eff = { ...def, dir: both ? def.dir : null, header: def.header?.trim() || undefined, checksum: def.checksum || undefined };
  // MSG2: the messages' structure of each direction -> a recording
  const sides = streamsOf(eff).map((x) => x.label);
  const cur = sides.includes(side) ? side : sides[0];
  const structure = def.structures?.[cur];
  const setStructure = (st: Structure | null) => {
    const all = { ...(def.structures ?? {}) };
    if (st) all[cur] = st; else delete all[cur];
    set({ structures: all });
  };
  const toast = (e: unknown) => useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
  const propose = async () => {
    setBusy(true);
    try {
      const s0 = streamsOf(eff).find((x) => x.label === cur)!;
      setStructure((await api.messagesSuggest(s0.sources, s0.params)).structure);
    } catch (e) { toast(e); } finally { setBusy(false); }
  };
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
  return (
    <div className="msgp-edit">
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
            <select id="msg-dir" className="msg-dir" value={def.dir ?? ""} onChange={(e) => set({ dir: e.target.value, txValue: null })}>
              {dirs.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          ) : <span className="hint msg-nodir">{t("msgDlgNoDir")}</span>}
          {dirSig && <>
            <label className="cmpobj-label" htmlFor="msg-txv">{t("msgDlgTxIs")}</label>
            <select id="msg-txv" className="msg-txv" value={String(def.txValue ?? Object.keys(labels)[0] ?? "")} onChange={(e) => set({ txValue: Number(e.target.value) })}>
              {Object.entries(labels).map(([code, text]) => <option key={code} value={code}>{text}</option>)}
            </select>
          </>}
        </div>
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
      <section className="msg-structure">
        <h3>{t("msgStruct")}</h3>
        <p className="hint">{t("msgStructHint")}</p>
        {sides.length > 1 && (
          <div className="seg msg-sides" role="group" aria-label={t("msgDirOf")}>
            {sides.map((l) => <button key={l} className={l === cur ? "on" : ""} aria-pressed={l === cur} onClick={() => setSide(l)}>{l}</button>)}
          </div>
        )}
        <div className="msg-struct-tools">
          <button className="btn outline sm msg-propose" disabled={busy || !can} onClick={propose}>{t("msgPropose")}</button>
          <select className="msg-lib" aria-label={t("msgpFromLib")} value="" onChange={(e) => void fromLibrary(e.target.value)}>
            <option value="">{t("msgpFromLib")}</option>
            {library.filter((i) => !i.error).map((i) => <option key={i.key} value={i.key}>{i.name}</option>)}
            <option value="file">{t("msgpFile")}</option>
          </select>
          <button className="btn outline sm msg-save" disabled={!structure} onClick={async () => { if (structure && await saveToLibrary(structure)) onLibrary(); }}>{t("msgpSaveLib")}</button>
        </div>
        {structure && <StructureEditor key={cur + (structure.name ?? "")} value={structure} onChange={setStructure} />}
      </section>
      <div className="msgp-actions">
        <button className={`btn ${structure ? "outline" : "primary"} sm msg-go`} disabled={busy || !can} onClick={() => run(() => decodeAsMessages(eff))}>{t("msgpPlot")}</button>
        {structure && <button className="btn primary sm msg-make" disabled={busy || !can} onClick={() => run(() => makeRecording(eff, cur))}>{t("msgMake")}</button>}
        <button className="btn outline sm msg-report" disabled={busy || !can} onClick={() => addStreamToReport(eff)}>{t("msgpAddReport")}</button>
      </div>
      <p className="hint">{t("msgDlgHint")}</p>
    </div>
  );
}

const bare = (id: string) => id.slice(id.indexOf("/") + 1);
