/* What to run next: new parameter sets, each with its reason - the edge between holding and
   failing, near the best, where scenarios disagree, the emptiest corners, what is missing, and
   whether the best sets are robust - on every map and as a list, written out as a run list.
   Only the parameters to explore move (S06: all of them, those on the maps, or chosen); the others
   stay at the values of the set a suggestion starts from. The choices and the last answer are kept
   with the study (and go into the report). Nothing runs from here. */
import { useState } from "react";
import { pickPath } from "../../store";
import { useT } from "../../i18n";
import { sweepApi, type SuggestKind } from "../../sweeps/api";
import type { NextRuns } from "../../sweeps/model";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import { notify, notifyError } from "../../sweeps/notify";
import { activeParams, mapList } from "../../sweeps/view";
import ColumnPicker from "./ColumnPicker";
import MapsView from "./MapView";
import { KINDS, MARK, stamp } from "../../sweeps/next";

const DEFAULT_KINDS: SuggestKind[] = ["edge", "best", "disagree", "missing"];

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
    } catch (e) { notifyError(e); }
    setBusy(false);
  };
  const exportList = async () => {
    if (!res) return;
    const p = await pickPath({ mode: "save", title: t("swNextExport"), exts: [".csv"], defaultName: "next_runs.csv" });
    if (!p) return;
    try {
      const r = await sweepApi.suggestExport(study.tableId, wireQuestion(study), res.suggestions.map((s) => s.params), p);
      setNext({ exported: r.path });
      notify(t("swExported", { n: r.rows, path: r.path }));
    } catch (e) { notifyError(e); }
  };
  const stale = !!res && res.key !== undefined && res.key !== keyOf(study, res.focus);
  const marks = (res?.suggestions ?? []).map((s) => ({ params: s.params, kind: s.kind, param: s.param }));
  return (
    <div className="sw-next">
      <div className="sw-next-side">
        <div className="sw-field">{t("swExplore")}
          <ColumnPicker options={params.map((p) => ({ id: p, label: p, group: t("swRoleParam") }))} value={exploring}
            onChange={(ids) => setNext({ focus: ids.length && ids.length < params.length ? ids : undefined })}
            presets={[{ label: t("swExploreAll"), ids: params }, ...(onMaps.length ? [{ label: t("swExploreMaps"), ids: onMaps }] : [])]}
            label={exploring.length === params.length ? t("swExploreAllN", { n: params.length }) : t("swExploreN", { n: exploring.length, of: params.length })} />
          <span className="hint">{t("swExploreHint")}</span>
        </div>
        <label className="sw-row">{t("swBudget")}
          <input type="number" min={1} max={2000} value={budget} onChange={(e) => setNext({ budget: Math.max(1, Number(e.target.value) || 1) })} style={{ width: 70 }} />
          <span className="hint">{t("swBudgetRuns", { n: (budget * combos).toLocaleString() })}</span></label>
        {KINDS.map(({ k, title, hint }) => {
          const off = k === "robust" && !robustSet;
          return (
            <label key={k} className={`sw-kind${off ? " off" : ""}`}>
              <input type="checkbox" disabled={off} checked={kinds.includes(k)}
                onChange={(e) => setNext({ kinds: e.target.checked ? [...kinds, k] : kinds.filter((x) => x !== k) })} />
              <span><b className={`sw-mark-${k}`}>{MARK[k]} {t(title)}</b>{res && <span className="hint"> · {res.available[k] ?? 0}</span>}<br />
                <span className="hint">{off ? t("swNextRobustOff") : t(hint)}</span></span>
            </label>
          );
        })}
        <button className="btn primary" disabled={busy || !kinds.length} onClick={run}>{t("swSuggest")}</button>
      </div>
      <div className="sw-next-main">
        {stale && <div className="sw-banner" role="status">{t("swNextStale")}<button className="btn primary" onClick={run}>{t("swSuggest")}</button></div>}
        <MapsView study={study} marks={marks} />
        {res && (
          <>
            <div className="sw-row"><b>{t("swSuggested", { n: res.suggestions.length })}</b>
              {res.focus && <span className="hint">{t("swExploredOnly", { list: res.focus.join(", ") })}</span>}
              <button className="btn outline" disabled={!res.suggestions.length} onClick={exportList}>{t("swNextExport")}</button></div>
            <div className="sw-table-wrap">
              <table className="sw-table">
                <thead><tr><th>{t("swWhyCol")}</th>{Object.keys(res.suggestions[0]?.params ?? {}).map((c) => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>{res.suggestions.map((s, i) => (
                  <tr key={i}><td className={`sw-mark-${s.kind}`}>{MARK[s.kind]} {t(KINDS.find((k) => k.k === s.kind)?.title ?? "swNextGaps")}{s.param ? ` · ${s.param}` : ""}</td>
                    {Object.entries(s.params).map(([c, v]) => <td key={c} className={`${typeof v === "number" ? "num" : ""}${s.param === c ? " sw-moved" : ""}`}>{v === null ? "–" : String(v)}</td>)}</tr>
                ))}</tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
