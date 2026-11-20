import { useState } from "react";
import { useEscape } from "./Overlays";
import { pickPath, useApp } from "../store";
import { useT } from "../i18n";
import { api } from "../api";
import type { MessageStream, Structure } from "../store/model";
import { decodeAsMessages, directionCandidates, makeRecording, streamFor, streamsOf } from "../messages";
import StructureEditor from "./StructureEditor";

/* MSG1 (owner, 2026-11-19: "how is a signal defined as a kind of message - only TX, only RX, or both with another
   column that says the direction each time"): what the byte signal carries, its direction column and which of its
   values is TX; the framing found by itself unless a header / checksum is given. Kept in the session. */
const CHECKSUMS = ["", "none", "sum8", "xor8", "negsum8", "notsum8", "crc16ccitt", "crc16modbus", "fletcher16"];

export default function MessagesDialog() {
  const t = useT();
  const req = useApp((s) => s.messagesDialog);
  const runs = useApp((s) => s.runs);
  const close = () => useApp.setState({ messagesDialog: null });
  useEscape(close, true);
  const [def, setDef] = useState<MessageStream | null>(() => (req ? streamFor(req.ids) : null));
  const [busy, setBusy] = useState(false);
  if (!req || !def) return null;
  const one = def.sources.length === 1;
  const dirs = one ? directionCandidates(def.sources[0]) : [];
  const dirSig = runs.flatMap((r) => r.signals).find((s) => s.id === def.dir);
  const labels = dirSig?.labels ?? {};
  const name = (id: string) => id.slice(id.indexOf("/") + 1);
  const set = (p: Partial<MessageStream>) => setDef({ ...def, ...p });
  const both = def.carries === "both";
  const can = !both || !!def.dir;
  // MSG2: the messages' structure of each direction -> a recording
  const labels2 = streamsOf({ ...def, dir: both ? def.dir : null }).map((x) => x.label);
  const [side, setSide] = useState<string>(labels2[0]);
  const cur = labels2.includes(side) ? side : labels2[0];
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
      const s0 = streamsOf({ ...def, dir: both ? def.dir : null }).find((x) => x.label === cur)!;
      setStructure((await api.messagesSuggest(s0.sources, s0.params)).structure);
    } catch (e) { toast(e); } finally { setBusy(false); }
  };
  const load = async () => {
    const p = await pickPath({ mode: "open", title: t("msgStructFile"), exts: [".json"] });
    if (!p) return;
    try { setStructure((await api.messagesStructure(p)).structure); } catch (e) { toast(e); }
  };
  const save = async () => {
    if (!structure) return;
    const p = await pickPath({ mode: "save", title: t("msgStructFile"), exts: [".json"], defaultName: `${(structure.name || "messages").replace(/[^\w-]+/g, "_")}.svmsg.json` });
    if (!p) return;
    try { await api.saveText(p, JSON.stringify(structure, null, 1) + "\n", ".json", false); } catch (e) { toast(e); }
  };
  const make = async () => {
    setBusy(true);
    const ok = await makeRecording({ ...def, dir: both ? def.dir : null }, cur);
    setBusy(false);
    if (ok) close();
  };
  const go = async () => {
    setBusy(true);
    const ok = await decodeAsMessages({ ...def, dir: both ? def.dir : null, header: def.header?.trim() || undefined, checksum: def.checksum || undefined });
    setBusy(false);
    if (ok) close();
  };
  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog cmpobj msgdlg" role="dialog" aria-modal="true" aria-label={t("msgDlgTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("msgDlgTitle")}</h2></div>
        <div className="dialog-body">
          <p className="hint"><bdi dir="ltr">{one ? name(def.sources[0]) : `${name(def.sources[0])} … ${name(def.sources[def.sources.length - 1])} (${def.sources.length})`}</bdi>
            {" - "}{t(one ? "msgDlgOne" : def.carries === "pair" ? "msgDlgTwo" : "msgDlgCols")}</p>
          {def.carries === "pair" && <p className="hint msg-pair-order">TX: <bdi dir="ltr">{name(def.sources[0])}</bdi> · RX: <bdi dir="ltr">{name(def.sources[1])}</bdi>{" "}
            <button className="linklike" onClick={() => set({ sources: [def.sources[1], def.sources[0]] })}>{t("msgDlgSwap")}</button></p>}
          <fieldset className="msg-carries">
            <legend>{t("msgDlgCarries")}</legend>
            {(["tx", "rx", "both", ...(def.sources.length === 2 ? ["pair" as const] : [])] as const).map((c) => (
              <label key={c}><input type="radio" name="msg-carries" value={c} checked={def.carries === c} disabled={c === "both" && !one}
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
          <p className="hint">{t("msgDlgHint")}</p>
          <section className="msg-structure">
            <h3>{t("msgStruct")}</h3>
            <p className="hint">{t("msgStructHint")}</p>
            {labels2.length > 1 && (
              <div className="seg msg-sides" role="group" aria-label={t("msgDirOf")}>
                {labels2.map((l) => <button key={l} className={l === cur ? "on" : ""} aria-pressed={l === cur} onClick={() => setSide(l)}>{l}</button>)}
              </div>
            )}
            <div className="msg-struct-tools">
              <button className="btn outline sm msg-propose" disabled={busy || !can} onClick={propose}>{t("msgPropose")}</button>
              <button className="btn outline sm msg-nmea" onClick={async () => { try { setStructure((await api.messagesNmea()).structure); } catch (e) { toast(e); } }}>{t("msgNmea")}</button>
              <button className="btn outline sm msg-load" onClick={load}>{t("msgLoad")}</button>
              <button className="btn outline sm msg-save" disabled={!structure} onClick={save}>{t("msgSave")}</button>
            </div>
            {structure && <StructureEditor key={cur + (structure.name ?? "")} value={structure} onChange={setStructure} />}
          </section>
        </div>
        <div className="dialog-foot">
          <button className="btn" onClick={close}>{t("cancel")}</button>
          <button className={`btn ${structure ? "outline" : "primary"} msg-go`} disabled={busy || !can} onClick={go}>{busy ? t("loading") : t("msgDlgGo")}</button>
          {structure && <button className="btn primary msg-make" disabled={busy || !can} onClick={make}>{busy ? t("loading") : t("msgMake")}</button>}
        </div>
      </div>
    </div>
  );
}
