/* What to run next: new parameter sets, each with its reason - the edge between holding and
   failing, near the best, where scenarios disagree, the emptiest corners, and what is missing -
   on the map of two parameters and as a list, written out as a run list. Nothing runs from here. */
import { useState } from "react";
import { pickPath } from "../../store";
import { useT, type TKey } from "../../i18n";
import { sweepApi, type Suggestion, type SuggestKind } from "../../sweeps/api";
import { wireQuestion, type Study } from "../../sweeps/state";
import MapView, { MARK } from "./MapView";

const KINDS: { k: SuggestKind; title: TKey; hint: TKey }[] = [
  { k: "edge", title: "swNextEdge", hint: "swNextEdgeHint" },
  { k: "best", title: "swNextBest", hint: "swNextBestHint" },
  { k: "disagree", title: "swNextDisagree", hint: "swNextDisagreeHint" },
  { k: "gaps", title: "swNextGaps", hint: "swNextGapsHint" },
  { k: "missing", title: "swNextMissing", hint: "swNextMissingHint" },
];

export default function NextRunsView({ study }: { study: Study }) {
  const t = useT();
  const [kinds, setKinds] = useState<SuggestKind[]>(["edge", "best", "disagree", "missing"]);
  const [budget, setBudget] = useState(40);
  const [res, setRes] = useState<{ suggestions: Suggestion[]; available: Record<string, number> } | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const combos = study.answer?.counts.combos ?? 1;
  const run = async () => {
    setBusy(true); setNote("");
    try { setRes(await sweepApi.suggest(study.tableId, wireQuestion(study), kinds, budget)); }
    catch (e) { setNote((e as Error).message); }
    setBusy(false);
  };
  const exportList = async () => {
    if (!res) return;
    const p = await pickPath({ mode: "save", title: t("swNextExport"), exts: [".csv"], defaultName: "next_runs.csv" });
    if (!p) return;
    try { const r = await sweepApi.suggestExport(study.tableId, wireQuestion(study), res.suggestions.map((s) => s.params), p); setNote(t("swExported", { n: r.rows, path: r.path })); }
    catch (e) { setNote((e as Error).message); }
  };
  const x = study.view.mapX ?? study.columns.find((c) => c.role === "param")?.name;
  const y = study.view.mapY ?? study.columns.filter((c) => c.role === "param").map((c) => c.name).find((n) => n !== x);
  const marks = (res?.suggestions ?? []).filter((s) => x && y && s.params[x] !== undefined && s.params[y] !== undefined)
    .map((s) => ({ x: s.params[x!] as number | string, y: s.params[y!] as number | string, kind: s.kind }));
  return (
    <div className="sw-next">
      <div className="sw-next-side">
        <label className="sw-row">{t("swBudget")}
          <input type="number" min={1} max={2000} value={budget} onChange={(e) => setBudget(Math.max(1, Number(e.target.value) || 1))} style={{ width: 70 }} />
          <span className="hint">{t("swBudgetRuns", { n: (budget * combos).toLocaleString() })}</span></label>
        {KINDS.map(({ k, title, hint }) => (
          <label key={k} className="sw-kind">
            <input type="checkbox" checked={kinds.includes(k)} onChange={(e) => setKinds(e.target.checked ? [...kinds, k] : kinds.filter((x) => x !== k))} />
            <span><b className={`sw-mark-${k}`}>{MARK[k]} {t(title)}</b>{res && <span className="hint"> · {res.available[k] ?? 0}</span>}<br /><span className="hint">{t(hint)}</span></span>
          </label>
        ))}
        <button className="btn primary" disabled={busy || !kinds.length} onClick={run}>{t("swSuggest")}</button>
        {note && <p className="hint">{note}</p>}
      </div>
      <div className="sw-next-main">
        <MapView study={study} marks={marks} />
        {res && (
          <>
            <div className="sw-row"><b>{t("swSuggested", { n: res.suggestions.length })}</b>
              <button className="btn outline" disabled={!res.suggestions.length} onClick={exportList}>{t("swNextExport")}</button></div>
            <div className="sw-table-wrap">
              <table className="sw-table">
                <thead><tr><th>{t("swWhyCol")}</th>{Object.keys(res.suggestions[0]?.params ?? {}).map((c) => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>{res.suggestions.map((s, i) => (
                  <tr key={i}><td className={`sw-mark-${s.kind}`}>{MARK[s.kind]} {t(KINDS.find((k) => k.k === s.kind)!.title)}{s.param ? ` · ${s.param}` : ""}</td>
                    {Object.values(s.params).map((v, j) => <td key={j} className={typeof v === "number" ? "num" : ""}>{v === null ? "–" : String(v)}</td>)}</tr>
                ))}</tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
