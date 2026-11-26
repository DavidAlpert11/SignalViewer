/* Owner, 2026-11-23: "defining a signal as messages is reached only by a right-click - there is no clear place".
   The one place is the Messages panel: this form says what can be a byte stream and takes it in one step - one signal
   byte by byte, the two signals of a link (TX and RX), or byte columns with one message per row. Open by itself
   while the panel lists no stream. The signal's right-click (Decode as messages…) stays as the shortcut. */
import { useMemo, useState } from "react";
import type { RunInfo } from "../api";
import { BYTE_COL } from "../messages";
import { useT } from "../i18n";
import { Icon } from "../icons";
import MultiSignalPicker from "./MultiSignalPicker";

type Kind = "one" | "pair" | "columns";
const BYTEISH = /(^|[._ ])(byte|bytes|raw|rx|tx|data|uart|serial|b)([._ \d[\]]|$)/i;
const RX = /(^|[^a-z])rx|recv|receive|down/i;
const bare = (id: string) => id.slice(id.indexOf("/") + 1);

export default function AddStream({ files, listed, open, onOpen, onAdd }: {
  files: RunInfo[]; listed: Set<string>; open: boolean; onOpen: (on: boolean) => void;
  /** the stream's signals (a pair: TX first) and what it carries when the user said so */
  onAdd: (ids: string[], carries?: "pair") => void;
}) {
  const t = useT();
  const [kind, setKind] = useState<Kind>("one");
  // every signal that can carry bytes (not a state with labels), byte-like names first
  const opts = useMemo(() => files.flatMap((r) => r.signals.filter((x) => !x.labels && !x.discrete).map((x) => ({ id: x.id, label: x.name, group: r.name, byte: BYTEISH.test(x.name) })))
    .sort((a, b) => Number(b.byte) - Number(a.byte)), [files]);
  const free = opts.filter((o) => !listed.has(o.id));
  // the first guess: a signal not listed yet; else any (two streams found one by one may well be one link's TX and RX)
  const first = (pred: (o: typeof opts[number]) => boolean) => (free.find(pred) ?? opts.find(pred) ?? free[0] ?? opts[0])?.id ?? "";
  const [one, setOne] = useState("");
  const [tx, setTx] = useState("");
  const [rx, setRx] = useState("");
  const [cols, setCols] = useState<string[]>([]);
  const oneId = one || first((o) => o.byte);
  const txId = tx || first((o) => o.byte && !RX.test(o.label));
  const rxId = rx || first((o) => o.byte && RX.test(o.label) && o.id !== txId);
  // byte columns of one file (byte_0..byte_N, b[0]..., data0...): offered as one click
  const colGroups = useMemo(() => files.map((r) => ({ label: t("msgpAddColsOf", { file: r.name }),
    ids: r.signals.filter((x) => BYTE_COL.test(x.name)).map((x) => x.id) })).filter((g) => g.ids.length >= 2), [files, t]);
  const ok = kind === "one" ? !!oneId : kind === "pair" ? !!txId && !!rxId && txId !== rxId : cols.length >= 2;
  const add = () => {
    if (!ok) return;
    if (kind === "one") onAdd([oneId]);
    else if (kind === "pair") onAdd([txId, rxId], "pair");
    else onAdd(cols);
  };
  const sel = (v: string, set: (v: string) => void, label: string) => (
    <label className="afield"><span>{label}</span>
      <select value={v} onChange={(e) => set(e.target.value)}>
        {opts.map((o) => <option key={o.id} value={o.id}>{`${o.label} · ${o.group}${listed.has(o.id) ? " ✓" : ""}`}</option>)}
      </select></label>
  );

  if (!open) return null;
  return (
    <div className="card msgp-addform" role="group" aria-label={t("msgpAddTitle")}>
      <div className="msgp-addform-head"><h4>{t("msgpAddTitle")}</h4>
        <button className="iconbtn sm" aria-label={t("close")} title={t("close")} onClick={() => onOpen(false)}><Icon.X /></button></div>
      <p className="hint">{t("msgpAddIntro")}</p>
      {!opts.length ? <p className="hint">{t("msgpAddNoFiles")}</p> : <>
        <div className="seg msgp-addkind" role="radiogroup" aria-label={t("msgpAddTitle")}>
          {(["one", "pair", "columns"] as const).map((k) => (
            <button key={k} role="radio" aria-checked={kind === k} className={kind === k ? "on" : ""} data-kind={k} onClick={() => setKind(k)}>
              {t(k === "one" ? "msgpKindOne" : k === "pair" ? "msgpKindPair" : "msgpKindCols")}</button>))}
        </div>
        <p className="hint msgp-addkind-hint">{t(kind === "one" ? "msgpKindOneHint" : kind === "pair" ? "msgpKindPairHint" : "msgpKindColsHint")}</p>
        {kind === "one" && sel(oneId, setOne, t("msgpAddWhich"))}
        {kind === "pair" && <div className="msgp-addpair">{sel(txId, setTx, "TX")}{sel(rxId, setRx, "RX")}</div>}
        {kind === "columns" && <MultiSignalPicker options={opts.map((o) => ({ id: o.id, label: o.label, group: o.group }))} value={cols} onChange={setCols}
          quick={colGroups} />}
        <div className="msgp-addform-foot">
          {kind === "pair" && txId === rxId && <span className="hint msgp-bad">{t("msgpAddSame")}</span>}
          <span className="spacer" />
          <button className="btn primary sm msgp-addgo" disabled={!ok} onClick={add}>{t("msgpAddGo")}</button>
        </div>
      </>}
    </div>
  );
}

/** the stream's title from its signals: one name, "tx + rx", or "byte_0…byte_7" */
export const streamTitle = (ids: string[]) => ids.length === 1 ? bare(ids[0]) : ids.length === 2 ? ids.map(bare).join(" + ") : `${bare(ids[0])}…${bare(ids[ids.length - 1])}`;
