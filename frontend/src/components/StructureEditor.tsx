import { useRef, useState } from "react";
import { fieldSize } from "../messages";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { useApp } from "../store";
import { confirmAsk } from "./Overlays";
import type { StructField, StructMessage, Structure } from "../store/model";

/* MSG2 (owner, 2026-11-20: "propose structures and give the user freedom to define"): a message structure edited as a
   form - the framing (binary: header, length byte, type byte, checksum; text: the start, the separator, *HH) and
   each message with its fields (binary: byte, type, LSB / MSB first, scale, add, unit; text: place, type, unit) - or
   as its JSON, the same thing written out (a field's bits, labels, hemisphere live there too). */
const BIN = ["u8", "i8", "u16", "i16", "u24", "i24", "u32", "i32", "f32", "f64", "ascii"];
const TXT = ["number", "int", "text", "lat", "lon", "hhmmss", "ddmmyy"];
const SCHEMES = ["sum8", "xor8", "negsum8", "notsum8", "crc16ccitt", "crc16modbus", "fletcher16"];
const hex = (v: number | string) => (typeof v === "number" ? "0x" + v.toString(16).toUpperCase().padStart(2, "0") : v);
const num = (s: string, d = 0) => { const v = Number(s); return Number.isFinite(v) ? v : d; };

export default function StructureEditor({ value, onChange }: { value: Structure; onChange: (s: Structure) => void }) {
  const t = useT();
  const [mode, setMode] = useState<"form" | "json">("form");
  const [text, setText] = useState(() => JSON.stringify(value, null, 1));
  const [bad, setBad] = useState<string | null>(null);
  const bin = value.kind === "binary";
  const set = (p: Partial<Structure>) => onChange({ ...value, ...p });
  const setMsg = (i: number, p: Partial<StructMessage>) => set({ messages: value.messages.map((m, k) => (k === i ? { ...m, ...p } : m)) });
  const setField = (i: number, j: number, p: Partial<StructField>) =>
    setMsg(i, { fields: value.messages[i].fields.map((f, k) => (k === j ? { ...f, ...p } : f)) });
  const cs = typeof value.checksum === "object" ? value.checksum : null;
  const show = (m: "form" | "json") => {
    if (m === "json") { setText(JSON.stringify(value, null, 1)); setBad(null); }
    setMode(m);
  };
  const nextOffset = (m: StructMessage) => {
    return m.fields.reduce((a, f) => Math.max(a, (f.offset ?? 0) + fieldSize(f)), 4);
  };
  // fields are removed one by one, at once, with Undo in the notice; a whole message only from its menu, asked first
  // (owner, 2026-11-23: removing one variable took the whole group - the field's ✕ was off to the side of a wide
  // table and the message's "Remove" was the button in sight)
  const latest = useRef(value);
  latest.current = value;
  const [closed, setClosed] = useState<string[]>([]);          // messages folded (by id and name)
  const [openF, setOpenF] = useState<string[]>([]);            // fields with their conversion open ("i:j")
  const msgKey = (m: StructMessage) => `${m.id}|${m.name}`;
  const putBack = (fn: (s: Structure) => Structure | null) => { const v = fn(latest.current); if (v) onChange(v); };
  const removeField = (i: number, j: number) => {
    const m = value.messages[i], f = m.fields[j];
    setMsg(i, { fields: m.fields.filter((_x, k) => k !== j) });
    setOpenF([]);
    useApp.getState().toast({ kind: "info", key: "msg-removed", text: t("msgFieldRemoved", { name: f.name, msg: m.name }), action: { label: t("undo"), run: () => putBack((s) => {
      const k = s.messages.findIndex((x) => msgKey(x) === msgKey(m));
      if (k < 0) return null;
      const fs = [...s.messages[k].fields];
      fs.splice(Math.min(j, fs.length), 0, f);
      return { ...s, messages: s.messages.map((x, q) => (q === k ? { ...x, fields: fs } : x)) };
    }) } });
  };
  const removeMsg = async (i: number) => {
    const m = value.messages[i];
    if (m.fields.length && !await confirmAsk(t("msgMsgRemove"), t("msgMsgRemoveAsk", { msg: m.name, n: m.fields.length }), t("msgMsgRemove"), true)) return;
    const s0 = latest.current, k = s0.messages.findIndex((x) => msgKey(x) === msgKey(m));
    if (k < 0) return;
    onChange({ ...s0, messages: s0.messages.filter((_x, q) => q !== k) });
    setOpenF([]);
    useApp.getState().toast({ kind: "info", key: "msg-removed", text: t("msgMsgRemoved", { msg: m.name }), action: { label: t("undo"), run: () => putBack((s) => {
      const ms = [...s.messages];
      ms.splice(Math.min(k, ms.length), 0, m);
      return { ...s, messages: ms };
    }) } });
  };
  return (
    <div className="msg-struct">
      <div className="seg" role="group">
        <button className={mode === "form" ? "on" : ""} aria-pressed={mode === "form"} onClick={() => show("form")}>{t("msgForm")}</button>
        <button className={mode === "json" ? "on" : ""} aria-pressed={mode === "json"} onClick={() => show("json")}>{t("msgJson")}</button>
      </div>
      {mode === "json" ? (
        <>
          <textarea className="msg-json" dir="ltr" spellCheck={false} value={text} rows={16}
            onChange={(e) => {
              setText(e.target.value);
              try { const v = JSON.parse(e.target.value); setBad(null); onChange(v); } catch (err) { setBad(String((err as Error).message)); }
            }} />
          {bad && <p className="hint msg-json-bad">⚠ {t("msgJsonBad", { msg: bad })}</p>}
        </>
      ) : (
        <>
          <div className="msg-frame" dir="ltr">
            <label>{t("msgKind")}{" "}
              <select className="msg-kind" value={value.kind} onChange={(e) => set({ kind: e.target.value as Structure["kind"] })}>
                <option value="binary">{t("msgBinary")}</option><option value="text">{t("msgText")}</option>
              </select></label>
            {bin ? <>
              <label>{t("msgHeader")} <input className="msg-hdr" size={8} value={value.header ?? ""} onChange={(e) => set({ header: e.target.value })} /></label>
              <label>{t("msgLenAt")} <input type="number" min={0} className="msg-len-at" value={value.length?.offset ?? ""} placeholder="—"
                onChange={(e) => set({ length: e.target.value === "" ? null : { offset: num(e.target.value), add: value.length?.add ?? 0 } })} /></label>
              {value.length && <label>{t("msgLenAdd")} <input type="number" className="msg-len-add" value={value.length.add}
                onChange={(e) => set({ length: { offset: value.length!.offset, add: num(e.target.value) } })} /></label>}
              {!value.length && <label>{t("msgSize")} <input type="number" min={1} value={value.size ?? ""} onChange={(e) => set({ size: e.target.value === "" ? null : num(e.target.value) })} /></label>}
              <label>{t("msgTypeAt")} <input type="number" min={0} className="msg-type-at" value={value.type?.offset ?? ""} placeholder="—"
                onChange={(e) => set({ type: e.target.value === "" ? null : { offset: num(e.target.value) } })} /></label>
              <label>{t("msgCs")} <select className="msg-cs2" value={cs?.scheme ?? ""}
                onChange={(e) => set({ checksum: e.target.value ? { scheme: e.target.value, from: cs?.from ?? 2 } : null })}>
                <option value="">{t("msgNone2")}</option>{SCHEMES.map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
              <label>{t("msgFooter")} <input className="msg-footer" size={6} placeholder="—" value={value.footer ?? ""}
                onChange={(e) => set({ footer: e.target.value || null })} /></label>
              {cs && <label>{t("msgCsFrom")} <input type="number" min={0} value={cs.from} onChange={(e) => set({ checksum: { scheme: cs.scheme, from: num(e.target.value) } })} /></label>}
            </> : <>
              <label>{t("msgStart")} <input size={2} value={value.start ?? "$"} onChange={(e) => set({ start: e.target.value })} /></label>
              <label>{t("msgSep")} <input size={2} value={value.sep ?? ","} onChange={(e) => set({ sep: e.target.value })} /></label>
              <label>{t("msgEnd")} <input size={3} placeholder={t("msgEndLine")} value={value.end ?? ""} onChange={(e) => set({ end: e.target.value || null })} /></label>
              <label>{t("msgCs")} <select value={value.checksum === "nmea" ? "nmea" : ""} onChange={(e) => set({ checksum: e.target.value || null })}>
                <option value="">{t("msgNone2")}</option><option value="nmea">{t("msgCsNmea")}</option></select></label>
            </>}
          </div>
          {value.messages.map((m, i) => {
            const shut = closed.includes(msgKey(m));
            return (
            <section key={i} className={`msg-msg${shut ? " shut" : ""}`} dir="ltr">
              <header className="msg-msg-head">
                <button className="iconbtn msg-msg-chev" aria-expanded={!shut} aria-label={t(shut ? "msgShowFields" : "msgHideFields")}
                  title={t(shut ? "msgShowFields" : "msgHideFields")}
                  onClick={() => setClosed((c) => (shut ? c.filter((k) => k !== msgKey(m)) : [...c, msgKey(m)]))}><Icon.Chevron /></button>
                <input className="msg-id" size={6} title={t("msgMsgId")} aria-label={t("msgMsgId")} value={bin ? hex(m.id) : String(m.id)}
                  onChange={(e) => setMsg(i, { id: bin ? (parseInt(e.target.value, e.target.value.toLowerCase().startsWith("0x") ? 16 : 10) || 0) : e.target.value })} />
                <input className="msg-name" size={14} title={t("msgMsgName")} aria-label={t("msgMsgName")} value={m.name} onChange={(e) => setMsg(i, { name: e.target.value })} />
                <span className="msg-msg-count" dir="auto">{m.fields.length === 1 ? t("msgNFieldsOne") : t("msgNFields", { n: m.fields.length })}</span>
                <button className="iconbtn msg-msg-del" aria-label={t("msgMsgRemoveN", { msg: m.name })} title={t("msgMsgRemoveN", { msg: m.name })}
                  onClick={() => void removeMsg(i)}><Icon.Trash /></button>
              </header>
              {!shut && <>
                {m.fields.length > 0 ? (
                  <div className="msg-fields" role="table" aria-label={m.name}>
                    <div className="msg-f-head" role="row">
                      <span role="columnheader" dir="auto">{t("msgFName")}</span><span role="columnheader">{bin ? t("msgFAt") : t("msgFIndex")}</span>
                      <span role="columnheader">{t("msgFType")}</span><span role="columnheader">{bin ? t("msgFEndian") : ""}</span>
                      <span role="columnheader">{t("msgFUnit")}</span><span /><span />
                    </div>
                    {m.fields.map((f, j) => {
                      const fk = `${i}:${j}`;
                      const more = openF.includes(fk);
                      const plain = f.type === "ascii" || f.type === "text";
                      const conv = plain ? "" : f.formula ? f.formula : [f.scale != null && f.scale !== 1 ? `×${f.scale}` : "", f.add ? (f.add > 0 ? `+${f.add}` : `${f.add}`) : ""].join(" ").trim();
                      return (
                        <div key={j} className={`msg-f${more ? " more" : ""}`} role="row">
                          <input className="msg-f-name" aria-label={t("msgFName")} value={f.name} onChange={(e) => setField(i, j, { name: e.target.value })} />
                          <input type="number" min={0} className="msg-f-at" aria-label={bin ? t("msgFAt") : t("msgFIndex")} value={(bin ? f.offset : f.index) ?? 0}
                            onChange={(e) => setField(i, j, bin ? { offset: num(e.target.value) } : { index: num(e.target.value) })} />
                          <select className="msg-f-type" aria-label={t("msgFType")} value={f.type ?? (bin ? "u8" : "number")} title={t(`msgTy_${f.type ?? (bin ? "u8" : "number")}` as never)}
                            onChange={(e) => setField(i, j, { type: e.target.value, ...(e.target.value === "ascii" && !f.size ? { size: 8 } : {}) })}>
                            {(bin ? BIN : TXT).map((x) => <option key={x} value={x} title={t(`msgTy_${x}` as never)}>{x}</option>)}</select>
                          {bin ? (f.type === "ascii"
                            ? <label className="msg-f-size" title={t("msgFSizeHint")}><input type="number" min={1} max={255} value={f.size ?? 8}
                                onChange={(e) => setField(i, j, { size: Math.max(1, Math.min(255, num(e.target.value, 8))) })} /> {t("msgFBytes")}</label>
                            : <select className="msg-f-endian" dir="auto" aria-label={t("msgFEndian")} value={f.endian ?? "le"} disabled={/8$/.test(f.type ?? "u8")}
                                onChange={(e) => setField(i, j, { endian: e.target.value as "le" | "be" })}>
                                <option value="le">{t("msgLe")}</option><option value="be">{t("msgBe")}</option></select>) : <span />}
                          <input className="msg-f-unit" aria-label={t("msgFUnit")} value={f.unit ?? ""} onChange={(e) => setField(i, j, { unit: e.target.value })} />
                          <button className={`msg-f-conv${conv ? " set" : ""}`} aria-expanded={more} disabled={plain}
                            title={t("msgFConvHint")} onClick={() => setOpenF((o) => (more ? o.filter((k) => k !== fk) : [...o, fk]))}>
                            {conv || "ƒ"}</button>
                          <button className="iconbtn msg-f-del" aria-label={t("msgFieldRemove", { name: f.name })} title={t("msgFieldRemove", { name: f.name })}
                            onClick={() => removeField(i, j)}><Icon.X /></button>
                          {more && (
                            <div className="msg-f-more">
                              <label>{t("msgFScale")} <input size={5} className="msg-f-scale" value={f.scale ?? 1} disabled={!!f.formula} onChange={(e) => setField(i, j, { scale: num(e.target.value, 1) })} /></label>
                              <label>{t("msgFAdd")} <input size={4} className="msg-f-add" value={f.add ?? 0} disabled={!!f.formula} onChange={(e) => setField(i, j, { add: num(e.target.value) })} /></label>
                              <label title={t("msgFFormulaHint")}>{t("msgFFormula")} <input size={14} className="msg-f-formula" dir="ltr" placeholder="x*0.01-40" value={f.formula ?? ""}
                                onChange={(e) => setField(i, j, { formula: e.target.value || undefined })} /></label>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : <p className="hint msg-f-none">{t("msgNoFields")}</p>}
                <button className="msg-add msg-add-field" onClick={() => setMsg(i, { fields: [...m.fields,
                  bin ? { name: `b${nextOffset(m)}`, offset: nextOffset(m), type: "u8" } : { name: `f${m.fields.length + 1}`, index: m.fields.length + 1, type: "number" }] })}>
                  <Icon.Plus /> {t("msgAddField")}</button>
              </>}
            </section>
          ); })}
          <button className="msg-add msg-add-msg" onClick={() => set({ messages: [...value.messages,
            { id: bin ? 0 : "XXX", name: `MSG${value.messages.length + 1}`, fields: [] }] })}><Icon.Plus /> {t("msgAddMsg")}</button>
        </>
      )}
    </div>
  );
}
