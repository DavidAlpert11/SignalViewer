import { useMemo } from "react";
import { useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { signalUnit } from "../units";
import type { RunInfo, SignalInfo } from "../api";
import SignalPicker, { type PickOption } from "./SignalPicker";

/** One signal chosen by TYPING its name (the file list's search), from every open file - the place
 *  of the plain lists that showed one file's signals in a long scroll. Beside it: the unit the
 *  signal is in now, and ƒ - change this signal (a unit conversion, a scale, a formula...) right
 *  here, e.g. angles that turn out to be in radians, without looking for it in the file list.
 *  `filter` keeps some signals only (state signals...); `prefer` lists one file's signals first. */
export default function SignalField({ value, onChange, ariaLabel, placeholder, noneLabel, filter, prefer, compact }: {
  value: string | null | undefined;
  onChange: (id: string | null) => void;
  ariaLabel: string;
  placeholder?: string;
  /** shown as a way to clear the choice (optional roles); none: a choice is required */
  noneLabel?: string;
  filter?: (s: SignalInfo, r: RunInfo) => boolean;
  prefer?: string;
  compact?: boolean;
}) {
  const t = useT();
  const runs = useApp((s) => s.runs);
  const options = useMemo(() => {
    const data = runs.filter((r) => r.format !== "derived");
    const ordered = prefer ? [...data.filter((r) => r.id === prefer), ...data.filter((r) => r.id !== prefer)] : data;
    const many = data.length > 1;
    const out: PickOption[] = [];
    for (const r of [...ordered, ...runs.filter((x) => x.format === "derived")]) {
      for (const s of r.signals) {
        if (filter && !filter(s, r)) continue;
        out.push({ id: s.id, label: s.name, group: many || r.format === "derived" ? r.name : undefined,
          tag: many ? r.tag : undefined, color: many ? r.color : undefined });
      }
    }
    return out;
  }, [runs, filter, prefer]);
  const info = useMemo(() => {
    if (!value) return null;
    const rid = value.slice(0, value.indexOf("/"));
    return runs.find((r) => r.id === rid)?.signals.find((s) => s.id === value) ?? null;
  }, [runs, value]);
  const unit = value ? signalUnit(runs, value) : null;
  const canEdit = !!value && !value.startsWith("derived/");

  return (
    <span className="sigfield">
      <SignalPicker value={value ?? null} options={options} onChange={(id) => onChange(id)} ariaLabel={ariaLabel}
        placeholder={placeholder ?? noneLabel} compact={compact} />
      {value && !info && <span className="sigfield-missing" title={t("sigFieldMissing")}>!</span>}
      {unit && <span className="sigfield-unit" title={t("sigFieldUnit")}><bdi>{unit}</bdi></span>}
      {canEdit && (
        <button type="button" className={`iconbtn sm sigfield-edit${info?.transform ? " on" : ""}`}
          title={info?.transform ? t("sigFieldEdited") : t("sigFieldEdit")} aria-label={`${t("sigFieldEdit")}: ${ariaLabel}`}
          onClick={() => useApp.setState({ transformTargets: [value!] })}>ƒ</button>
      )}
      {value && noneLabel && (
        <button type="button" className="iconbtn sm" title={noneLabel} aria-label={`${noneLabel}: ${ariaLabel}`}
          onClick={() => onChange(null)}><Icon.X width={11} height={11} /></button>
      )}
    </span>
  );
}
