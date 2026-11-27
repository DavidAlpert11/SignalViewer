import { useEffect, useState } from "react";
import { useApp } from "../store";
import { fmtNum, useT } from "../i18n";
import { api, type AnomalyKind, type ChannelCompare as Cmp, type ChannelSide, type RunInfo } from "../api";

/* CH4 / CH10 (owner, 2026-11-27: "a comparison with other similar files - whether there are anomalies between them -
   with graphical indications, and on the whole automatically"): the same channel in every other open file with the
   same signals, read the same way, by itself (up to AUTO files; more: a button). A row per file: its anomalies over
   its own time (a small strip, every one drawn), a bar per count, each count against this file's (more red, fewer
   green), a count that stands out against the other files marked ⚠; under it what differs between the files - the
   one that stands out, the patterns that changed (svcore/channel.compare_files; the report says the same). */
const AUTO = 8;
const STRIP = 200;                             // the small strip's columns
const hex = (v: number | null | undefined) => (v == null ? "" : "0x" + v.toString(16).toUpperCase().padStart(2, "0"));

/** The same channel's sides in another open file - its signals of the same names (else null). */
function sidesIn(sides: ChannelSide[], run: RunInfo): ChannelSide[] | null {
  const names = new Set(run.signals.map((x) => x.name));
  const bare = (id: string) => id.slice(id.indexOf("/") + 1);
  if (!sides.every((s) => s.sources.every((id) => names.has(bare(id))))) return null;
  return sides.map((s) => ({ ...s, sources: s.sources.map((id) => `${run.id}/${bare(id)}`) }));
}

export default function ChannelCompare({ sides, home, reread, kindKey }: {
  sides: ChannelSide[]; home: string; reread: string; kindKey: Record<AnomalyKind, string>;
}) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const self = runs.find((r) => r.id === home);
  const similar = runs.filter((r) => r.format !== "derived" && r.id !== home).map((r) => ({ run: r, sides: sidesIn(sides, r) }))
    .filter((x): x is { run: RunInfo; sides: ChannelSide[] } => !!x.sides);
  const key = reread + "|" + similar.map((x) => x.run.id).join(",");
  const [res, setRes] = useState<{ key: string; r: Cmp } | null>(null);
  const [busy, setBusy] = useState(false);
  const go = () => {
    if (!self) return;
    setBusy(true);
    api.messagesChannelCompare([{ name: self.name, sides }, ...similar.map((x) => ({ name: x.run.name, sides: x.sides }))])
      .then((r) => setRes({ key, r })).catch(() => setRes(null)).finally(() => setBusy(false));
  };
  useEffect(() => {
    if (!similar.length || similar.length > AUTO) return;
    const id = window.setTimeout(go, 400);           // by itself: the same channel in the similar files
    return () => window.clearTimeout(id);
  }, [key]);                                     // eslint-disable-line react-hooks/exhaustive-deps

  if (!similar.length) return null;
  const r = res?.key === key ? res.r : null;
  if (!r) return (
    <div className="ch-compare">
      {similar.length > AUTO || !busy
        ? <button className="btn outline sm ch-compare-go" disabled={busy} onClick={go}>{t("chCompare", { n: similar.length })}</button>
        : <p className="hint">{t("chComparing", { n: similar.length })}</p>}
    </div>);
  const rows = r.files;
  const base = rows[0];
  const kinds = (Object.keys(kindKey) as AnomalyKind[]).filter((k) => rows.some((x) => (x.counts?.[k] ?? 0) > 0));
  const out = new Set(r.standsOut.map((x) => `${x.file}|${x.kind}`));
  const cols: { id: string; label: string; v: (x: Cmp["files"][number]) => number }[] = [
    { id: "all", label: t("chAll"), v: (x) => x.total ?? 0 },
    ...(["link", "capture", "none"] as const).map((c) => ({ id: `cause-${c}`, label: t(`chCause_${c}` as never), v: (x: Cmp["files"][number]) => x.byCause?.[c] ?? 0 })),
    ...kinds.map((k) => ({ id: k, label: t(kindKey[k] as never), v: (x: Cmp["files"][number]) => x.counts?.[k] ?? 0 })),
  ];
  const most = Object.fromEntries(cols.map((c) => [c.id, Math.max(1, ...rows.map((x) => (x.error ? 0 : c.v(x))))]));
  const cell = (x: Cmp["files"][number], i: number, c: typeof cols[number]) => {
    const v = c.v(x), b = base.error ? v : c.v(base);
    const flag = out.has(`${x.name}|${c.id}`);
    return (
      <td key={c.id} data-kind={c.id} className={`ch-cell${flag ? " ch-out" : ""}`} title={flag ? t("chStandsOut") : undefined}>
        <span className="ch-bar" style={{ width: `${(100 * v) / most[c.id]}%` }} />
        <span className="ch-num">{flag ? "⚠ " : ""}{i === 0 || v === b ? fmtNum(v, lang, 6)
          : <span className={v > b ? "ch-more" : "ch-less"}>{fmtNum(v, lang, 6)} <bdi dir="ltr">({v > b ? "+" : "−"}{fmtNum(Math.abs(v - b), lang, 6)})</bdi></span>}</span>
      </td>);
  };
  // each file's anomalies over its own time - every one drawn (several in a column: one mark), the cause by its look
  const strip = (x: Cmp["files"][number]) => {
    if (!x.events || !x.span) return null;
    const [a, b] = x.span, w = Math.max(b - a, 1e-9);
    const by = new Map<number, { k: AnomalyKind; c: string }>();
    x.events.t.forEach((tt, i) => {
      const c = Math.min(STRIP - 1, Math.max(0, Math.floor(((tt - a) / w) * STRIP)));
      const had = by.get(c);
      if (!had || x.events!.cause[i] === "link") by.set(c, { k: x.events!.kind[i], c: x.events!.cause[i] });
    });
    return (
      <svg viewBox={`0 0 ${STRIP} 12`} preserveAspectRatio="none" className="ch-mini" role="img" aria-label={t("chStripLabel")}>
        {[...by.entries()].map(([c, m]) => <rect key={c} x={c} y={1} width={1.6} height={10} className={`ch-mark ch-k-${m.k} ch-c-${m.c}`} />)}
      </svg>);
  };
  const diffLine = (p: Cmp["patterns"][number]) => {
    const a = { file: p.file, dir: p.dir, t: hex(p.type), r: hex(p.reply), n: p.count ?? 0, v: "", o: "" };
    if (p.what === "rate") Object.assign(a, { v: fmtNum(Number(p.value), lang, 3), o: fmtNum(Number(p.others), lang, 3) });
    else if (p.what === "latency") Object.assign(a, { v: fmtNum(Number(p.value) * 1000, lang, 3), o: fmtNum(Number(p.others) * 1000, lang, 3) });
    else Object.assign(a, { v: String(p.value ?? ""), o: String(p.others ?? "") });
    return t(`chDiff_${p.what}` as never, a as never);
  };
  return (
    <div className="ch-compare">
      <h5>{t("chCompareTitle", { n: rows.length })}</h5>
      <div className="ch-compare-wrap">
        <table className="msgp-table ch-compare-t">
          <thead><tr><th>{t("chFile")}</th><th>{t("chOverTime")}</th>{cols.map((c) => <th key={c.id} data-kind={c.id}>{c.label}</th>)}</tr></thead>
          <tbody>{rows.map((x, i) => (
            <tr key={x.name + i} className={i === 0 ? "ch-this" : ""} data-file={x.name}>
              <th scope="row">{x.name}</th>
              {x.error ? <td colSpan={cols.length + 1} className="hint">⚠ {x.error}</td> : <>
                <td className="ch-mini-cell">{strip(x)}</td>
                {cols.map((c) => cell(x, i, c))}
              </>}
            </tr>))}</tbody>
        </table>
      </div>
      {(r.standsOut.length > 0 || r.patterns.length > 0) ? (
        <div className="ch-diffs">
          <b>{t("chDiffs")}</b>
          <ul>
            {r.standsOut.map((x, i) => <li key={`o${i}`} className="ch-diff-out">⚠ {t("chDiff_out", { file: x.file, n: x.value, kind: t(kindKey[x.kind] as never), o: fmtNum(x.others, lang, 3) })}</li>)}
            {r.patterns.map((p, i) => <li key={`p${i}`} dir="auto">{diffLine(p)}</li>)}
          </ul>
        </div>
      ) : <p className="hint ch-nodiff">{t("chNoDiffs")}</p>}
      <p className="hint">{t("chCompareHint")}</p>
    </div>
  );
}
