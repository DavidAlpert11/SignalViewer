/* 26.U6: a trust badge - a result that rests on an assumption says so where it is shown: missing values
   skipped or bridged, values interpolated between samples, a filter run on each stretch between gaps or
   on an even grid. Amber: something about missing data; quiet: how values were read. The tooltip says
   exactly what was done. */
import { useEffect, useState } from "react";
import { api, type DerivedQuality } from "../api";
import { useT, type TKey } from "../i18n";
import type { MapObject } from "../store";
import { attitudeOf } from "../mapObjects";

const fmt = (x: number) => (Math.abs(x) >= 100 ? x.toFixed(0) : x.toPrecision(3));
const span = (s: [number, number][]) => s.slice(0, 5).map(([a, b]) => (a === b ? fmt(a) : `${fmt(a)}–${fmt(b)}`)).join(", ") + (s.length > 5 ? " …" : "");

type T = ReturnType<typeof useT>;

/** What a derived signal's `quality` says: the short mark, the lines of its tooltip, how loud. */
export function trustNotes(q: DerivedQuality | undefined, t: T): { short: string; lines: string[]; level: "warn" | "info" } | null {
  if (!q) return null;
  const warn: [string, string][] = [];
  if (q.skipped) warn.push([t("qSkippedShort"), t("qSkipped", { n: q.skipped.toLocaleString() })]);
  if (q.bridged?.length) warn.push([t("qBridgedShort"), t("qBridged", { n: q.bridged.length, at: span(q.bridged) })]);
  if (q.missing?.length) warn.push([t("qMissingShort"), t("qMissing", { at: span(q.missing) })]);
  if (q.infinite) warn.push([t("qInfiniteShort"), t("qInfinite", { n: q.infinite.toLocaleString() })]);
  const info: [string, string][] = [];
  const f = q.filter;
  if (f?.gaps) info.push([t("qFilterShort"), t("qFilterGaps", { n: f.gaps + 1 })]);
  if (f?.resampled) info.push([t("qFilterShort"), t("qFilterGrid", { fs: f.fs ? fmt(f.fs) : "?" })]);
  const ip = q.interpolated;
  if (ip?.sources.length) info.push([t("qInterpShort"), t(ip.method === "nearest" ? "qInterpNearest" : "qInterpLinear", { n: ip.sources.length })]);
  const all = [...warn, ...info];
  if (!all.length) return null;
  return { short: all[0][0], lines: all.map((x) => x[1]), level: warn.length ? "warn" : "info" };
}

/** The badge: `compact` (a legend chip) is a mark alone; otherwise the short words too. */
export default function TrustBadge({ q, compact, className = "" }: { q?: DerivedQuality; compact?: boolean; className?: string }) {
  const t = useT();
  const n = trustNotes(q, t);
  if (!n) return null;
  const title = `${t("trustHead")}\n${n.lines.map((l) => `• ${l}`).join("\n")}`;
  return (
    <span className={`trust ${n.level}${compact ? " compact" : ""} ${className}`.trim()} role="note" tabIndex={compact ? undefined : 0}
      title={title} aria-label={compact ? `${n.short}: ${n.lines.join("; ")}` : undefined}>
      {compact ? "≈" : n.short}
    </span>
  );
}

/** 26.U6: a map / 3D object whose angle unit is "Automatic" - the guess (26.A5), on its chip. */
export function AngleGuessBadge({ o }: { o: { angleUnit?: string; yaw?: string | null; pitch?: string | null; roll?: string | null; qw?: string | null } }) {
  const t = useT();
  const [g, setG] = useState<{ unit: "deg" | "rad"; why: string } | null>(null);
  const auto = (o.angleUnit ?? "auto") === "auto" && !o.qw && !!(o.yaw || o.pitch || o.roll);
  useEffect(() => {
    if (!auto) { setG(null); return; }
    let gone = false;
    api.angleUnits({ yaw: o.yaw, pitch: o.pitch, roll: o.roll })
      .then((r) => { if (!gone) setG(Object.values(r.units)[0] ?? null); }).catch(() => { if (!gone) setG(null); });
    return () => { gone = true; };
  }, [auto, o.yaw, o.pitch, o.roll]);
  if (!auto || !g) return null;
  const line = t("trustAngles", { unit: t(g.unit === "deg" ? "objUnitDeg" : "objUnitRad"), why: t(("objUnitWhy_" + g.why) as TKey) });
  return <span className="trust info compact" role="note" title={`${t("trustHead")}\n• ${line}`} aria-label={line}>≈</span>;
}

/** N5: an attitude that is not the object's own - from its motion, or borrowed from another object. */
export function AttitudeSourceBadge({ o, all }: { o: MapObject; all: MapObject[] }) {
  const t = useT();
  const a = attitudeOf(o, all);
  if (a.kind !== "motion" && a.kind !== "borrowed") return null;
  const line = a.kind === "motion" ? t("objAttFromMotion") : t("objAttBorrowed", { name: a.from.name });
  return <span className="trust info compact obj-att-badge" role="note" title={`${t("trustHead")}\n• ${line}`} aria-label={line}>≈</span>;
}
