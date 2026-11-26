import { useEffect, useMemo, useState } from "react";
import { actions, useApp } from "../store";
import { fmtNum, useT } from "../i18n";
import { api, type AnomalyKind, type ChannelInfo } from "../api";
import type { MessageStream } from "../store/model";
import { channelSides } from "../messages";

/* CH3 (owner, 2026-11-26: "recognise the repeating patterns beyond the message content - header, checksum, a
   handshake ... show graphically whether there are anomalies and count them"): the stream's channel at a glance, above
   the four steps - what was found beyond the content (each direction's framing, which request each reply answers and
   how fast, the handshake) and the anomalies (svcore/channel.py): a chip per kind with its count, a time strip with a
   lane per kind and a list. Every anomaly is counted and drawn: several in one column of the strip make one taller
   mark whose tooltip says how many. A click on a mark or a row puts the cursor there on the plots. */
const W = 1000;                                    // the strip's columns (its viewBox; it stretches to the panel)
const hex = (v: number | null) => (v == null ? "" : "0x" + v.toString(16).toUpperCase().padStart(2, "0"));
const LIST_MAX = 500;

const KIND_KEY: Record<AnomalyKind, string> = {
  checksum: "chK_checksum", broken: "chK_broken", length: "chK_length", unknown: "chK_unknown", counter: "chK_counter", gap: "chK_gap",
  unanswered: "chK_unanswered", retry: "chK_retry", late: "chK_late", reconnect: "chK_reconnect", handshake: "chK_handshake" };

export default function ChannelView({ def }: { def: MessageStream }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const sides = useMemo(() => channelSides(def), [def]);
  const key = JSON.stringify(sides);
  const [info, setInfo] = useState<ChannelInfo | null>(null);
  const [err, setErr] = useState("");
  const [only, setOnly] = useState<AnomalyKind | null>(null);
  useEffect(() => {
    let live = true;
    const id = window.setTimeout(() => {
      api.messagesChannel(sides).then((r) => { if (live) { setInfo(r); setErr(""); } }).catch((e) => { if (live) { setInfo(null); setErr(String((e as Error).message)); } });
    }, 300);
    return () => { live = false; window.clearTimeout(id); };
  }, [key]);                                     // eslint-disable-line react-hooks/exhaustive-deps

  if (err) return <section className="ch-view card"><h4>{t("chTitle")}</h4><p className="hint">⚠ {err}</p></section>;
  if (!info) return <section className="ch-view card"><h4>{t("chTitle")}</h4><p className="hint">{t("msgpLooking")}</p></section>;
  const ev = info.events;
  const kinds = info.kinds.filter((k) => info.counts[k] > 0);
  const [t0, t1] = info.span;
  const span = Math.max(t1 - t0, 1e-9);
  const col = (x: number) => Math.min(W - 1, Math.max(0, Math.floor(((x - t0) / span) * W)));
  // per kind: the events in each column of the strip (every one counted)
  const lanes = kinds.map((k) => {
    const bins = new Map<number, number[]>();
    ev.t.forEach((x, i) => { if (ev.kind[i] === k) { const c = col(x); bins.set(c, [...(bins.get(c) ?? []), i]); } });
    return { k, bins: [...bins.entries()] };
  });
  const go = (i: number) => actions.goToTime(ev.t[i]);
  const shown = ev.t.map((_x, i) => i).filter((i) => !only || ev.kind[i] === only);
  const secs = (x: number) => `${x.toFixed(Math.abs(x) < 100 ? 3 : 1)} s`;      // fixed decimals: no 3.000e-4
  const ms = (x: number | null) => (x == null ? "—" : `${fmtNum(x * 1000, lang, 3)} ms`);

  return (
    <section className="ch-view card" data-total={info.total}>
      <h4>{t("chTitle")}</h4>
      <p className="hint">{t("chHint")}</p>
      <ul className="ch-patterns">
        {info.sides.map((s) => (
          <li key={s.name} className="ch-side"><b dir="ltr">{s.name}</b>{" "}
            {t("chSideLine", { n: fmtNum(s.count, lang, 6), h: s.header, types: s.types.length })}
            {" · "}<bdi dir="ltr">{s.framing}</bdi>{s.typeOffset != null ? <> · {t("msgTypeByte", { at: s.typeOffset })}</> : null}
            {" · "}{s.checksum ? <bdi dir="ltr">{s.checksum}</bdi> : t("chNoChecksum")}</li>))}
        {info.pairs.map((p) => (
          <li key={`${p.from}${p.request}`} className="ch-pair" dir="auto">
            <bdi dir="ltr">{p.from} {hex(p.request)} → {p.to} {hex(p.reply)}</bdi>{" · "}
            {t(p.how === "id" ? "chPairById" : "chPairNext")}{" · "}
            {t("chPairLine", { a: fmtNum(p.replies, lang, 6), n: fmtNum(p.requests, lang, 6), mean: ms(p.mean), max: ms(p.max) })}</li>))}
        {info.handshake.length > 0 && (
          <li className="ch-hs">{t("chHandshake")}{" "}<bdi dir="ltr">{info.handshake[0].steps.map((s) => `${s.dir} ${hex(s.type)}`).join(" → ")}</bdi>
            {" · "}{t("chHandshakeAt", { at: info.handshake.map((h) => secs(h.t)).join(", ") })}</li>)}
        {sides.length === 2 && !info.pairs.length && <li className="hint">{t("chNoPairs")}</li>}
      </ul>

      <div className="ch-head">
        <b>{info.total ? t("chAnomalies", { n: fmtNum(info.total, lang, 6) }) : t("chNoAnomalies")}</b>
        <span className="ch-chips">
          {kinds.map((k) => (
            <button key={k} className={`chip-s ch-chip ch-k-${k}${only === k ? " on" : ""}`} data-kind={k} aria-pressed={only === k}
              title={t("chChipTitle")} onClick={() => setOnly(only === k ? null : k)}>
              <i className="ch-dot" />{t(KIND_KEY[k] as never)} <b>{fmtNum(info.counts[k], lang, 6)}</b></button>))}
        </span>
      </div>

      {kinds.length > 0 && (
        <div className="ch-strip" role="img" aria-label={t("chStripLabel")}>
          {lanes.map(({ k, bins }) => (
            <div key={k} className={`ch-lane ch-k-${k}${only && only !== k ? " dim" : ""}`} data-kind={k}>
              <span className="ch-lane-name">{t(KIND_KEY[k] as never)}</span>
              <svg viewBox={`0 0 ${W} 14`} preserveAspectRatio="none" className="ch-lane-svg">
                {bins.map(([c, is]) => (
                  <rect key={c} className="ch-mark" x={c} y={is.length > 1 ? 0 : 3} width={4} height={is.length > 1 ? 14 : 8}
                    onClick={() => go(is[0])}>
                    <title>{`${is.length}× ${t(KIND_KEY[k] as never)} · ${secs(ev.t[is[0]])}${is.length > 1 ? ` – ${secs(ev.t[is[is.length - 1]])}` : ""}`}</title>
                  </rect>))}
              </svg>
            </div>))}
          <div className="ch-lane ch-axis"><span /><span className="ch-axis-ends" dir="ltr"><span>{secs(t0)}</span><span>{secs(t1)}</span></span></div>
        </div>
      )}

      {shown.length > 0 && (
        <details className="ch-list">
          <summary>{t("chList", { n: fmtNum(shown.length, lang, 6) })}</summary>
          <table className="msgp-table ch-table">
            <thead><tr><th>t</th><th>{t("chKind")}</th><th>{t("msgDirOf")}</th><th>{t("msgpType")}</th><th>{t("chDetail")}</th></tr></thead>
            <tbody>{shown.slice(0, LIST_MAX).map((i) => (
              <tr key={i} tabIndex={0} onClick={() => go(i)} onKeyDown={(e) => { if (e.key === "Enter") go(i); }}>
                <td dir="ltr">{fmtNum(ev.t[i], lang, 5)}</td><td>{t(KIND_KEY[ev.kind[i]] as never)}</td><td dir="ltr">{ev.dir[i]}</td>
                <td dir="ltr">{hex(ev.type[i])}</td><td dir="ltr">{ev.detail[i]}</td></tr>))}</tbody>
          </table>
          {shown.length > LIST_MAX && <p className="hint">{t("chListMore", { n: LIST_MAX, all: fmtNum(shown.length, lang, 6) })}</p>}
        </details>
      )}
    </section>
  );
}
