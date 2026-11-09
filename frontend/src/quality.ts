/* 26.U7: a per-signal data-quality summary when a file opens - missing values, gaps, repeated or
   backwards time stamps, rate changes (svcore/quality.py). Checked in the background after opening;
   a file with something to say gets one note (with "Show"), a badge on its name in the file list, and
   its signals a mark; the dialog lists every signal. */
import { api, type RunQuality, type SignalQuality } from "./api";
import { fileLabel, useApp } from "./store";
import { fmtNum, translate, type TKey } from "./i18n";

const KINDS = ["missing", "gaps", "duplicates", "backwards", "rateChanges"] as const;

/** Check the files just opened; announce those with something to say. */
export async function checkQuality(runIds: string[]) {
  const found: string[] = [];
  for (const id of runIds) {
    try {
      const q = await api.runQuality(id);
      if (!useApp.getState().runs.some((r) => r.id === id)) continue;         // closed meanwhile
      useApp.setState((s) => ({ quality: { ...s.quality, [id]: q } }));
      if (q.withIssues) found.push(id);
    } catch { /* not checkable (closed, a derived run) */ }
  }
  const st = useApp.getState();
  for (const id of found.slice(0, 3)) {
    const q = st.quality[id];
    st.toast({ kind: "info", text: translate(st.lang, "dqNote", { name: fileLabel(st.runs, id), n: q.withIssues, of: q.checked, what: kindsText(q, st.lang) }),
      action: { label: translate(st.lang, "dqShow"), run: () => useApp.setState({ qualityFor: id }) } });
  }
}

/** "gaps (3), missing values (2)" - the kinds of problem and how many signals have each. */
export function kindsText(q: RunQuality, lang: "en" | "he"): string {
  return KINDS.filter((k) => q.count[k]).map((k) => `${translate(lang, `dq_${k}` as TKey)} (${q.count[k]})`).join(", ");
}

/** One signal's problems in words (its tooltip, the dialog's rows). */
export function signalLines(s: SignalQuality, lang: "en" | "he"): string[] {
  const t = (k: TKey, p?: Record<string, string | number>) => translate(lang, k, p);
  const n = (x: number, d = 3) => fmtNum(x, lang, d);
  const out: string[] = [];
  if (s.missing) out.push(s.allMissing ? t("dqAllMissing") : t("dqMissing", { n: s.missing.toLocaleString(), pct: n(s.missingPct) }));
  if (s.gaps) out.push(t("dqGaps", { n: s.gaps, s: n(s.gapTime), at: n(s.firstGap ?? 0, 5) }));
  if (s.duplicates) out.push(t("dqDuplicates", { n: s.duplicates.toLocaleString() }));
  if (s.backwards) out.push(t("dqBackwards", { n: s.backwards.toLocaleString() }));
  for (const c of s.rateChanges) out.push(t("dqRate", { at: n(c.t, 5), from: n(c.from), to: n(c.to) }));
  return out;
}
