import { useT } from "../i18n";
import type { MessagesInspect } from "../api";
import type { MenuItem } from "../store/types";
import { openMenu } from "./Overlays";

/* MSG4 (owner, 2026-11-21: "the app should recognise identical patterns that can be the header or the footer and
   propose the message's template - and it must be clear to the user how he defines it"): the first messages of a
   byte stream, byte by byte, each byte coloured by its role in the structure (header, length, type, a field,
   checksum, footer; grey = not described yet). A click on a byte says what it is - the structure changes and the
   view (and the values in step 3) follow at once. Text sentences: their parts between the separators. */

export type ByteRole = { kind: "header"; upto: number } | { kind: "length"; at: number } | { kind: "type"; at: number }
  | { kind: "footer"; from: number } | { kind: "field"; at: number; type: string; endian: "le" | "be" } | { kind: "nofield"; at: number }
  | { kind: "text"; index: number; type: string } | { kind: "start"; at: number };

export const ROLES = ["header", "length", "type", "field", "checksum", "footer", "payload"] as const;
const hex2 = (v: number) => v.toString(16).toUpperCase().padStart(2, "0");

export default function ByteView({ info, onRole }: { info: MessagesInspect; onRole: (frame: number, role: ByteRole) => void }) {
  const t = useT();
  const roleName = (r: string) => t(`msgRole_${r}` as never);
  const fieldTypes: [string, "le" | "be", string][] = [["u8", "le", t("msgFt8")], ["i8", "le", t("msgFt8s")],
    ["u16", "le", t("msgFt16le")], ["i16", "le", t("msgFt16les")], ["u16", "be", t("msgFt16be")], ["i16", "be", t("msgFt16bes")],
    ["u32", "le", t("msgFt32le")], ["i32", "le", t("msgFt32les")], ["f32", "le", t("msgFtF32le")], ["f32", "be", t("msgFtF32be")]];

  const byteMenu = (e: React.MouseEvent, fi: number, i: number) => {
    const f = info.frames[fi];
    const b = f.bytes ?? [];
    const items: MenuItem[] = [];
    if (i <= 5) items.push({ label: t("msgSetHeader", { hex: b.slice(0, i + 1).map(hex2).join(" ") }), run: () => onRole(fi, { kind: "header", upto: i }) });
    items.push({ label: t("msgSetLength", { v: b[i], n: f.len ?? b.length }), run: () => onRole(fi, { kind: "length", at: i }) });
    items.push({ label: t("msgSetType", { v: "0x" + hex2(b[i]) }), run: () => onRole(fi, { kind: "type", at: i }) });
    items.push({ label: t("msgSetField"), run: () => {}, items: fieldTypes.map(([ty, en, label]) => ({ label, run: () => onRole(fi, { kind: "field", at: i, type: ty, endian: en }) })) });
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
      </p>
      {info.frames.length === 0 && info.head.length > 0 && (
        <div className="bv-head">
          <p className="hint">{t("msgHeadHint")}</p>
          <div className="bv-bytes" dir="ltr">
            {info.head.map((v, i) => (
              <button key={i} className="bv-b role-payload" title={`#${i} = ${v}`}
                onClick={(e) => openMenu(e, [{ label: t("msgStartsHere", { hex: `${hex2(v)} ${hex2(info.head[i + 1] ?? 0)}` }), run: () => onRole(-1, { kind: "start", at: i }) }])}>{hex2(v)}</button>
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
                  <button key={i} className={`bv-b role-${role}${fj != null ? ` fld-${fj % 2}` : ""}`}
                    title={`#${i} = 0x${hex2(v)} (${v}) · ${roleName(role)}${fj != null && f.fieldNames ? " · " + f.fieldNames[fj] : ""}`}
                    onClick={(e) => byteMenu(e, fi, i)}>{hex2(v)}</button>
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
