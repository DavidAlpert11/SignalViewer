/* Owner (2026-11-13): "at the end, the report must make the process clear at its key points, with no gaps".
   The report's first section, built from what is open: the data, what was checked (Compare's verdict, the flight
   log's own check, the investigation), what the report shows, and the conclusion - or that none is written yet. */
import { translate, type TKey } from "./i18n";
import { fileLabel, useApp, type ReportMeta } from "./store";

const fmt = (n: number, digits = 1) => (Math.round(n * 10 ** digits) / 10 ** digits).toLocaleString("en-US");

export function processSection(lang: "en" | "he", meta: ReportMeta, shown: { name: string; plots: { title?: string }[] }[],
  withVerdict: boolean, withInvestigation: boolean): { kind: "process"; title: string; items: string[] } {
  const t = (k: TKey, p?: Record<string, string | number>) => translate(lang, k, p);
  const st = useApp.getState();
  const files = st.runs.filter((r) => r.format !== "derived");
  const items: string[] = [];
  // 1. the data
  for (const f of files) {
    const dur = Math.max(0, f.end - f.start);
    const label = fileLabel(st.runs, f.id);
    items.push(t("rpData", { file: label === f.name ? f.name : `${label} (${f.name})`, format: f.format.toUpperCase(), s: fmt(dur), n: f.signals.length.toLocaleString("en-US") }));
  }
  // 2. what was checked
  for (const f of files.filter((x) => x.log)) items.push(t("rpLog", { file: fileLabel(st.runs, f.id), e: f.log!.errors, w: f.log!.warnings }));
  if (withVerdict && meta.verdict) items.push(t("rpVerdict", { what: meta.verdict.title, first: meta.verdict.summary[0] ?? "" }).replace(/ – $/, ""));
  if (withInvestigation) {
    const notes = st.ws.notes ?? [];
    const n = (s: string) => notes.filter((x) => x.status === s).length;
    const steps = st.journal.filter((j) => j.include).length;
    items.push(t("rpInvestigated", { faults: n("fault"), explained: n("explained"), open: n("open"), rejected: n("rejected"), steps }));
  }
  // 3. what the report shows
  const plots = shown.reduce((a, x) => a + x.plots.length, 0);
  if (plots) items.push(t("rpShows", { plots, tabs: shown.map((x) => x.name).join(", ") }));
  // 4. the conclusion
  const end = (meta.summary ?? "").trim();
  items.push(end ? t("rpConclusion", { text: end.split(/\n/)[0] }) : t("rpNoConclusion"));
  return { kind: "process", title: t("rpTitle"), items };
}
