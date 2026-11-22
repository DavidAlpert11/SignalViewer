import { useT } from "../i18n";
import { useApp } from "../store";
import type { MessagesInspect } from "../api";
import type { MenuItem } from "../store/types";
import { openMenu } from "./Overlays";

/* MSG4 (owner, 2026-11-21: "the app should recognise identical patterns that can be the header or the footer and
   propose the message's template - and it must be clear to the user how he defines it"): the first messages of a
   byte stream, byte by byte, each byte coloured by its role in the structure (header, length, type, a field,
   checksum, footer; grey = not described yet). A click on a byte says what it is - the structure changes and the
   view (and the values in step 3) follow at once. Text sentences: their parts between the separators. */

export type ByteRole = { kind: "header"; upto: number } | { kind: "length"; at: number } | { kind: "type"; at: number }
  | { kind: "footer"; from: number } | { kind: "field"; at: number; type: string; endian: "le" | "be"; size?: number } | { kind: "nofield"; at: number }
  | { kind: "text"; index: number; type: string } | { kind: "start"; at: number };

export const ROLES = ["header", "length", "type", "field", "checksum", "footer", "payload"] as const;
const hex2 = (v: number) => v.toString(16).toUpperCase().padStart(2, "0");
/** MSG8: a byte as a character (a dot when it is not a printable one) */
export const chr = (v: number) => (v >= 32 && v < 127) || v >= 160 ? String.fromCharCode(v) : "·";

/** MSG8 (owner, 2026-11-22: "convert the data from hex to double and to ascii"): what the bytes from `i` read as -
 *  integers and floats LSB / MSB first, and as text - shown on the byte, before anything is defined. */
export function readsAs(b: number[], i: number): string[] {
  const out: string[] = [];
  const take = (n: number, be: boolean) => {
    if (i + n > b.length) return null;
    const s = b.slice(i, i + n);
    return new DataView(Uint8Array.from(be ? s.slice().reverse() : s).buffer);
  };
  const num = (v: number) => (Number.isInteger(v) ? String(v) : Number(v.toPrecision(7)).toString());
  for (const [n, label] of [[2, "16"], [4, "32"]] as const) {
    const le = take(n, false), be = take(n, true);
    if (!le || !be) break;
    const u = (d: DataView) => (n === 2 ? d.getUint16(0, true) : d.getUint32(0, true));
    const s = (d: DataView) => (n === 2 ? d.getInt16(0, true) : d.getInt32(0, true));
    out.push(`${label}-bit LSB first: ${u(le)} / ${s(le)} · MSB first: ${u(be)} / ${s(be)}`);
  }
  const f4 = take(4, false), f4b = take(4, true);
  if (f4 && f4b) out.push(`float LSB first: ${num(f4.getFloat32(0, true))} · MSB first: ${num(f4b.getFloat32(0, true))}`);
  const f8 = take(8, false), f8b = take(8, true);
  if (f8 && f8b) out.push(`double LSB first: ${num(f8.getFloat64(0, true))} · MSB first: ${num(f8b.getFloat64(0, true))}`);
  out.push(`ASCII: "${b.slice(i, i + 16).map(chr).join("")}"`);
  return out;
}

/** The value a field of this type would read at `i`, for the menu ("= 1234") */
function preview(b: number[], i: number, ty: string, en: "le" | "be"): string {
  const n = { u8: 1, i8: 1, u16: 2, i16: 2, u32: 4, i32: 4, f32: 4, f64: 8 }[ty as "u8"] ?? 1;
  if (i + n > b.length) return "";
  const s = b.slice(i, i + n);
  const d = new DataView(Uint8Array.from(en === "be" ? s.slice().reverse() : s).buffer);
  const v = ty === "u8" ? d.getUint8(0) : ty === "i8" ? d.getInt8(0) : ty === "u16" ? d.getUint16(0, true) : ty === "i16" ? d.getInt16(0, true)
    : ty === "u32" ? d.getUint32(0, true) : ty === "i32" ? d.getInt32(0, true) : ty === "f32" ? d.getFloat32(0, true) : d.getFloat64(0, true);
  return `  = ${Number.isInteger(v) ? v : Number(v.toPrecision(7))}`;
}

export default function ByteView({ info, onRole }: { info: MessagesInspect; onRole: (frame: number, role: ByteRole) => void }) {
  const t = useT();
  const show = useApp((s) => s.byteShow);
  const cell = (v: number) => show === "dec" ? String(v) : show === "ascii" ? chr(v)
    : show === "both" ? <>{hex2(v)}<small className="bv-chr">{chr(v)}</small></> : hex2(v);
  const roleName = (r: string) => t(`msgRole_${r}` as never);
  const fieldTypes: [string, "le" | "be", string][] = [["u8", "le", t("msgFt8")], ["i8", "le", t("msgFt8s")],
    ["u16", "le", t("msgFt16le")], ["i16", "le", t("msgFt16les")], ["u16", "be", t("msgFt16be")], ["i16", "be", t("msgFt16bes")],
    ["u32", "le", t("msgFt32le")], ["i32", "le", t("msgFt32les")], ["u32", "be", t("msgFt32be")], ["i32", "be", t("msgFt32bes")],
    ["f32", "le", t("msgFtF32le")], ["f32", "be", t("msgFtF32be")], ["f64", "le", t("msgFtF64le")], ["f64", "be", t("msgFtF64be")]];

  const byteMenu = (e: React.MouseEvent, fi: number, i: number) => {
    const f = info.frames[fi];
    const b = f.bytes ?? [];
    const items: MenuItem[] = [];
    if (i <= 5) items.push({ label: t("msgSetHeader", { hex: b.slice(0, i + 1).map(hex2).join(" ") }), run: () => onRole(fi, { kind: "header", upto: i }) });
    items.push({ label: t("msgSetLength", { v: b[i], n: f.len ?? b.length }), run: () => onRole(fi, { kind: "length", at: i }) });
    items.push({ label: t("msgSetType", { v: "0x" + hex2(b[i]) }), run: () => onRole(fi, { kind: "type", at: i }) });
    // what the bytes from here read as: shown beside each choice, so the right one is seen before it is chosen
    items.push({ label: t("msgSetField"), run: () => {}, items: fieldTypes.map(([ty, en, label]) => ({ label: `${label}${preview(b, i, ty, en)}`, run: () => onRole(fi, { kind: "field", at: i, type: ty, endian: en }) })) });
    // MSG8: text inside a binary message - to the end of the values (before the checksum / footer), or a length
    const tail = (f.roles ?? []).reduce((a, r, k) => (k > i && (r === "checksum" || r === "footer") ? Math.min(a, k) : a), b.length) - i;
    items.push({ label: t("msgSetText"), run: () => {}, items: [...new Set([tail, 4, 8, 16].filter((n) => n >= 1 && i + n <= b.length))].map((n) => ({
      label: t(n === tail ? "msgSetTextToEnd" : "msgSetTextN", { n, text: b.slice(i, i + n).map(chr).join("") }),
      run: () => onRole(fi, { kind: "field", at: i, type: "ascii", endian: "le", size: n }) })) });

    if (f.roles?.[i] === "field") items.push({ label: t("msgSetNoField"), run: () => onRole(fi, { kind: "nofield", at: i }) });
    if (i > 2) items.push({ label: t("msgSetFooter", { hex: b.slice(i).map(hex2).join(" ") }), run: () => onRole(fi, { kind: "footer", from: i }) });
    openMenu(e, items);
  };
  const partMenu = (e: React.MouseEvent, fi: number, index: number) => {
    openMenu(e, [["number", t("msgTtNumber")], ["int", t("msgTtInt")], ["text", t("msgTtText")], ["lat", t("msgTtLat")], ["lon", t("msgTtLon")], ["hhmmss", t("msgTtTime")]]
      .map(([ty, label]) => ({ label, run: () => onRole(fi, { kind: "text", index, type: ty }) })));
  };

  return (
    <div className="bv">
      <p className="bv-legend" aria-label={t("msgLegend")}>
        {ROLES.map((r) => <span key={r} className={`bv-chip role-${r}`}>{roleName(r)}</span>)}
        {/* MSG8: the bytes as hex, numbers, characters - or hex with the character under it */}
        <span className="seg bv-show" role="radiogroup" aria-label={t("msgShowAs")} title={t("msgShowAsHint")}>
          {(["hex", "dec", "ascii", "both"] as const).map((k) => (
            <button key={k} role="radio" aria-checked={show === k} className={show === k ? "on" : ""}
              onClick={() => useApp.setState({ byteShow: k })}>{t(`msgShow_${k}` as never)}</button>))}
        </span>
      </p>
      {info.frames.length === 0 && info.head.length > 0 && (
        <div className="bv-head">
          <p className="hint">{t("msgHeadHint")}</p>
          <div className="bv-bytes" dir="ltr">
            {info.head.map((v, i) => (
              <button key={i} className="bv-b role-payload" title={`#${i} = 0x${hex2(v)} (${v}) '${chr(v)}'\n${readsAs(info.head, i).join("\n")}`}
                onClick={(e) => openMenu(e, [{ label: t("msgStartsHere", { hex: `${hex2(v)} ${hex2(info.head[i + 1] ?? 0)}` }), run: () => onRole(-1, { kind: "start", at: i }) }])}>{cell(v)}</button>
            ))}
          </div>
        </div>
      )}
      <div className="bv-frames" dir="ltr">
        {info.frames.map((f, fi) => (
          <div key={fi} className={`bv-frame st-${f.status}`}>
            <span className="bv-meta" title={t("msgFrameAt", { t: f.t.toFixed(4) })}>
              <b>{f.message || (f.id !== undefined && typeof f.id === "number" ? "0x" + hex2(f.id) : String(f.id ?? "?"))}</b>
              {f.status !== "ok" && <span className="bv-bad">{t(f.status === "bad" ? "msgFrameBad" : "msgFrameUnknown")}</span>}
            </span>
            <span className="bv-bytes">
              {f.bytes ? f.bytes.map((v, i) => {
                const role = f.roles?.[i] ?? "payload";
                const fj = f.fields?.[i];
                return (
                  <button key={i} className={`bv-b role-${role}${fj != null ? ` fld-${fj % 2}` : ""}${show === "both" ? " bv-two" : ""}`}
                    title={`#${i} = 0x${hex2(v)} (${v}) '${chr(v)}' · ${roleName(role)}${fj != null && f.fieldNames ? " · " + f.fieldNames[fj] : ""}\n${t("msgReadsAs")}\n${readsAs(f.bytes ?? [], i).join("\n")}`}
                    onClick={(e) => byteMenu(e, fi, i)}>{cell(v)}</button>
                );
              }) : (f.parts ?? []).map((p, i) => (
                <button key={i} className={`bv-b bv-part ${i === 0 ? "role-type" : f.fieldAt?.[i] != null ? "role-field" : "role-payload"}`}
                  title={`${t("msgFIndex")} ${i}`} disabled={i === 0} onClick={(e) => partMenu(e, fi, i)}>{p || "∅"}</button>
              ))}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
