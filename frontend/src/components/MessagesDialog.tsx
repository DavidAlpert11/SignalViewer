import { useState } from "react";
import { useEscape } from "./Overlays";
import { useApp } from "../store";
import { useT } from "../i18n";
import type { MessageStream } from "../store/model";
import { decodeAsMessages, directionCandidates, streamFor } from "../messages";

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
  const go = async () => {
    setBusy(true);
    const ok = await decodeAsMessages({ ...def, dir: both ? def.dir : null, header: def.header?.trim() || undefined, checksum: def.checksum || undefined });
    setBusy(false);
    if (ok) close();
  };
  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog msgdlg" role="dialog" aria-modal="true" aria-label={t("msgDlgTitle")} onMouseDown={(e) => e.stopPropagation()}>
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
        </div>
        <div className="dialog-foot">
          <button className="btn" onClick={close}>{t("cancel")}</button>
          <button className="btn primary msg-go" disabled={busy || !can} onClick={go}>{busy ? t("loading") : t("msgDlgGo")}</button>
        </div>
      </div>
    </div>
  );
}
