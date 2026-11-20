import { useState } from "react";
import { useT } from "../i18n";
import type { StructField, StructMessage, Structure } from "../store/model";

/* MSG2 (owner, 2026-11-20: "propose structures and give the user freedom to define"): a message structure edited as a
   form - the framing (binary: header, length byte, type byte, checksum; text: the start, the separator, *HH) and
   each message with its fields (binary: byte, type, LSB / MSB first, scale, add, unit; text: place, type, unit) - or
   as its JSON, the same thing written out (a field's bits, labels, hemisphere live there too). */
const BIN = ["u8", "i8", "u16", "i16", "u24", "i24", "u32", "i32", "f32", "f64"];
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
    const sizes: Record<string, number> = { u8: 1, i8: 1, u16: 2, i16: 2, u24: 3, i24: 3, u32: 4, i32: 4, f32: 4, f64: 8 };
    return m.fields.reduce((a, f) => Math.max(a, (f.offset ?? 0) + (sizes[f.type ?? "u8"] ?? 1)), 4);
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
          {value.messages.map((m, i) => (
            <fieldset key={i} className="msg-msg" dir="ltr">
              <legend>
                <input className="msg-id" size={6} title={t("msgMsgId")} value={bin ? hex(m.id) : String(m.id)}
                  onChange={(e) => setMsg(i, { id: bin ? (parseInt(e.target.value, e.target.value.toLowerCase().startsWith("0x") ? 16 : 10) || 0) : e.target.value })} />
                <input className="msg-name" size={14} title={t("msgMsgName")} value={m.name} onChange={(e) => setMsg(i, { name: e.target.value })} />
                <button className="linklike" onClick={() => set({ messages: value.messages.filter((_x, k) => k !== i) })}>{t("msgDel")}</button>
              </legend>
              <table className="msg-fields">
                <thead><tr><th>{t("msgFName")}</th><th>{bin ? t("msgFAt") : t("msgFIndex")}</th><th>{t("msgFType")}</th>{bin && <th>{t("msgFEndian")}</th>}
                  <th>{t("msgFScale")}</th><th>{t("msgFAdd")}</th><th>{t("msgFUnit")}</th><th /></tr></thead>
                <tbody>{m.fields.map((f, j) => (
                  <tr key={j}>
                    <td><input size={12} className="msg-f-name" value={f.name} onChange={(e) => setField(i, j, { name: e.target.value })} /></td>
                    <td><input type="number" min={0} className="msg-f-at" value={(bin ? f.offset : f.index) ?? 0}
                      onChange={(e) => setField(i, j, bin ? { offset: num(e.target.value) } : { index: num(e.target.value) })} /></td>
                    <td><select className="msg-f-type" value={f.type ?? (bin ? "u8" : "number")} onChange={(e) => setField(i, j, { type: e.target.value })}>
                      {(bin ? BIN : TXT).map((x) => <option key={x} value={x}>{x}</option>)}</select></td>
                    {bin && <td><select className="msg-f-endian" value={f.endian ?? "le"} disabled={/8$/.test(f.type ?? "u8")}
                      onChange={(e) => setField(i, j, { endian: e.target.value as "le" | "be" })}>
                      <option value="le">{t("msgLe")}</option><option value="be">{t("msgBe")}</option></select></td>}
                    <td><input size={5} value={f.scale ?? 1} onChange={(e) => setField(i, j, { scale: num(e.target.value, 1) })} /></td>
                    <td><input size={4} value={f.add ?? 0} onChange={(e) => setField(i, j, { add: num(e.target.value) })} /></td>
                    <td><input size={5} value={f.unit ?? ""} onChange={(e) => setField(i, j, { unit: e.target.value })} /></td>
                    <td><button className="linklike" aria-label={t("msgDel")} onClick={() => setMsg(i, { fields: m.fields.filter((_x, k) => k !== j) })}>✕</button></td>
                  </tr>
                ))}</tbody>
              </table>
              <button className="linklike msg-add-field" onClick={() => setMsg(i, { fields: [...m.fields,
                bin ? { name: `b${nextOffset(m)}`, offset: nextOffset(m), type: "u8" } : { name: `f${m.fields.length + 1}`, index: m.fields.length + 1, type: "number" }] })}>{t("msgAddField")}</button>
            </fieldset>
          ))}
          <button className="linklike msg-add-msg" onClick={() => set({ messages: [...value.messages,
            { id: bin ? 0 : "XXX", name: `MSG${value.messages.length + 1}`, fields: [] }] })}>{t("msgAddMsg")}</button>
        </>
      )}
    </div>
  );
}
