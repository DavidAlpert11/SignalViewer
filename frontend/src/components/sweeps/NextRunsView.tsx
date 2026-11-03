/* What to run next: new parameter sets, each with its reason - the edge between holding and
   failing, near the best, where scenarios disagree, the emptiest corners, what is missing, and
   whether the best sets are robust - on every map and as a list, written out as a run list.
   Only the parameters to explore move (S06: all of them, those on the maps, or chosen); the others
   stay at the values of the set a suggestion starts from. The choices and the last answer are kept
   with the study (and go into the report). Nothing runs from here. */
import { useState } from "react";
import { pickPath } from "../../store";
import { useT, type TKey } from "../../i18n";
import { openMenu } from "../Overlays";
import { sweepApi, type SuggestKind } from "../../sweeps/api";
import type { NextRuns } from "../../sweeps/model";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import { notify, notifyError } from "../../sweeps/notify";
import { activeParams, mapList } from "../../sweeps/view";
import ColumnPicker from "./ColumnPicker";
import RerunList from "./RerunList";
import MapsView from "./MapView";
import { KINDS, MARK, stamp } from "../../sweeps/next";

const DEFAULT_KINDS: SuggestKind[] = ["edge", "best", "disagree", "missing"];
/** the run list's formats: a file name's ending, its name in the menu */
const FORMATS: [string, TKey][] = [[".csv", "swFmtCsv"], [".tsv", "swFmtTsv"], [".json", "swFmtJson"], [".m", "swFmtMatlab"], [".py", "swFmtPython"]];

/** What the suggestions answered: the question and the parameters explored. */
const keyOf = (s: Study, focus: string[] | null) => JSON.stringify([wireQuestion(s), focus]);

export default function NextRunsView({ study }: { study: Study }) {
  const t = useT();
  const next = study.view.next ?? {};
  const setNext = (p: Partial<NextRuns>) => useSweeps.getState().setView({ next: { ...(useSweeps.getState().studies[useSweeps.getState().active]?.view.next ?? {}), ...p } });
  const params = activeParams(study);
  const focus = next.focus?.filter((p) => params.includes(p));
  const exploring = focus?.length ? focus : params;
  const robustSet = Object.keys(study.question.robust ?? {}).length > 0;
  const kinds = ((next.kinds as SuggestKind[] | undefined) ?? DEFAULT_KINDS).filter((k) => k !== "robust" || robustSet);
  const budget = next.budget ?? 40;
  const res = next.result;
  const [busy, setBusy] = useState(false);
  const combos = study.answer?.counts.combos ?? 1;
  const onMaps = [...new Set(mapList(study).flatMap((m) => [m.x, m.y]))];
  const run = async () => {
    setBusy(true);
    const f = focus?.length && focus.length < params.length ? focus : null;
    try {
      const r = await sweepApi.suggest(study.tableId, wireQuestion(study), kinds, budget, f);
      setNext({ result: { ...r, at: stamp(), focus: f, key: keyOf(study, f) } });
      useSweeps.getState().journal("suggest", { n: r.suggestions.length });
    } catch (e) { notifyError(e); }
    setBusy(false);
  };
  // the run list (every set x every combination) or the sets alone, in the format chosen (S17)
  const exportList = async (ext: string, combos: boolean) => {
    if (!res) return;
    const name = `${combos ? "next_runs" : "next_sets"}${ext}`;
    const p = await pickPath({ mode: "save", title: t("swNextExport"), exts: [ext], defaultName: name });
    if (!p) return;
    try {
      const r = await sweepApi.suggestExport(study.tableId, wireQuestion(study), res.suggestions.map((s) => s.params), p, combos);
      setNext({ exported: r.path });
      notify(t("swExported", { n: r.rows, path: r.path }));
      useSweeps.getState().journal("export", { path: r.path, n: r.rows });
    } catch (e) { notifyError(e); }
  };
  const exportMenu = (e: React.MouseEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const formats = (combos: boolean) => FORMATS.map(([ext, key]) => ({ label: t(key), run: () => { exportList(ext, combos); } }));
    const n = res?.suggestions.length ?? 0;
    openMenu({ clientX: r.left, clientY: r.bottom + 4, preventDefault() {}, stopPropagation() {} } as React.MouseEvent, [
      { label: t("swNextRunList", { n: (n * combos).toLocaleString() }), run: () => {}, items: formats(true) },
      { label: t("swNextSetsAlone", { n }), run: () => {}, items: formats(false) },
      { label: t("swNextCopy"), run: () => copySets() },
    ]);
  };
  // the sets as a table to paste into a spreadsheet (tab-separated)
  const copySets = () => {
    if (!res?.suggestions.length) return;
    const cols = Object.keys(res.suggestions[0].params);
    const text = [cols.join("\t"), ...res.suggestions.map((s) => cols.map((c) => s.params[c] ?? "").join("\t"))].join("\n");
    navigator.clipboard.writeText(text).then(() => notify(t("swNextCopied", { n: res.suggestions.length })), notifyError);
  };
  // compact (S17): a parameter with one value in every suggestion is said once, above the table
  const [everyCol, setEveryCol] = useState(false);
  const allCols = Object.keys(res?.suggestions[0]?.params ?? {});
  const same = res && res.suggestions.length > 1 ? allCols.filter((c) => res.suggestions.every((s) => s.params[c] === res.suggestions[0].params[c])) : [];
  const shownCols = everyCol ? allCols : allCols.filter((c) => !same.includes(c));
  const stale = !!res && res.key !== undefined && res.key !== keyOf(study, res.focus);
  const marks = (res?.suggestions ?? []).map((s) => ({ params: s.params, kind: s.kind, param: s.param }));
  return (
    <div className="sw-next">
      <div className="sw-next-side">
        <RerunList study={study} />
        <h3>{t("swSuggestedRuns")}</h3>
        <div className="sw-field">{t("swExplore")}
          <ColumnPicker options={params.map((p) => ({ id: p, label: p, group: t("swRoleParam") }))} value={exploring}
            onChange={(ids) => setNext({ focus: ids.length && ids.length < params.length ? ids : undefined })}
            presets={[{ label: t("swExploreAll"), ids: params }, ...(onMaps.length ? [{ label: t("swExploreMaps"), ids: onMaps }] : [])]}
            label={exploring.length === params.length ? t("swExploreAllN", { n: params.length }) : t("swExploreN", { n: exploring.length, of: params.length })} />
          <span className="hint">{t("swExploreHint")}</span>
        </div>
        <label className="sw-row">{t("swBudget")}
          <input type="number" min={1} max={2000} value={budget} onChange={(e) => setNext({ budget: Math.max(1, Number(e.target.value) || 1) })} style={{ width: 70 }} />
        </label>
        <span className="hint">{t("swBudgetUpTo", { n: budget, c: combos.toLocaleString(), r: (budget * combos).toLocaleString() })}</span>
        {KINDS.map(({ k, title, hint }) => {
          const off = k === "robust" && !robustSet;
          return (
            <label key={k} className={`sw-kind${off ? " off" : ""}`}>
              <input type="checkbox" disabled={off} checked={kinds.includes(k)}
                onChange={(e) => setNext({ kinds: e.target.checked ? [...kinds, k] : kinds.filter((x) => x !== k) })} />
              <span><b className={`sw-mark-${k}`}>{MARK[k]} {t(title)}</b>
                {res && res.available[k] !== undefined && <span className="hint"> · {t("swFoundTaken", { f: res.available[k], n: res.taken?.[k] ?? 0 })}</span>}<br />
                <span className="hint">{off ? t("swNextRobustOff") : t(hint)}</span></span>
            </label>
          );
        })}
        <span className="hint">{t("swBudgetShare")}</span>
        <button className="btn primary" disabled={busy || !kinds.length} onClick={run}>{t("swSuggest")}</button>
      </div>
      <div className="sw-next-main">
        {stale && <div className="sw-banner" role="status">{t("swNextStale")}<button className="btn primary" onClick={run}>{t("swSuggest")}</button></div>}
        <MapsView study={study} marks={marks} />
        {res && (
          <>
            <div className="sw-row"><b>{t("swSuggested", { n: res.suggestions.length })}</b>
              <span className="hint">= {t("swRunsOf", { n: res.suggestions.length, c: combos.toLocaleString(), r: (res.suggestions.length * combos).toLocaleString() })}</span>
              {res.budget !== undefined && res.suggestions.length < res.budget &&
                <span className="hint sw-fewer">{t("swFewerFound", { n: res.suggestions.length, b: res.budget })}</span>}
              {res.focus && <span className="hint">{t("swExploredOnly", { list: res.focus.join(", ") })}</span>}
              <button className="btn outline" disabled={!res.suggestions.length} onClick={exportMenu}>{t("swNextExport")} ▾</button></div>
            {same.length > 0 && <p className="hint sw-next-same">
              {t("swSameInAll", { n: res.suggestions.length })} <b>{same.map((c) => `${c} = ${res.suggestions[0].params[c] ?? "–"}`).join(", ")}</b>
              {" · "}<button className="linklike" onClick={() => setEveryCol(!everyCol)}>{t(everyCol ? "swNextCompact" : "swNextEveryCol")}</button></p>}
            <div className="sw-table-wrap">
              <table className="sw-table">
                <thead><tr><th>{t("swWhyCol")}</th>{shownCols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>{res.suggestions.map((s, i) => (
                  <tr key={i}><td className={`sw-mark-${s.kind}`}>{MARK[s.kind]} {t(KINDS.find((k) => k.k === s.kind)?.title ?? "swNextGaps")}{s.param ? ` · ${s.param}` : ""}</td>
                    {shownCols.map((c) => { const v = s.params[c]; return <td key={c} className={`${typeof v === "number" ? "num" : ""}${s.param === c ? " sw-moved" : ""}`}>{v === null || v === undefined ? "–" : String(v)}</td>; })}</tr>
                ))}</tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
