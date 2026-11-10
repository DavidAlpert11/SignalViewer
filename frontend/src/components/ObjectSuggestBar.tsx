import { useDeferredValue, useMemo, useState } from "react";
import { actions, activeTab, useApp, type Plot } from "../store";
import { translate, useT, type TKey } from "../i18n";
import { compareObjects, pairOf, type CompareFrame } from "../relation";
import { detectObjects, type Candidate } from "../objectDetect";
import { addable, addedSummary, candidateObject, objectColors } from "../objectAdd";

/* N5: "3 objects found: phys, nav, gps · Add all · Choose… · Why?" - a slim, non-blocking suggestion in
   the file panel when an open file has objects not on any map yet. Nothing is added without a click;
   dismissing hides it for that file (this run of the app), the found list stays a click away (a map's
   + Add object, the "Position on the map & 3D" template). */
export default function ObjectSuggestBar() {
  const t = useT();
  const runs = useDeferredValue(useApp((s) => s.runs));
  const ws = useApp((s) => s.ws);
  const hidden = useApp((s) => s.objSuggestHidden);
  const found = useMemo(() => {
    const onMaps = new Set(ws.tabs.flatMap((tb) => tb.plots.flatMap((p) => (p.objects ?? []).map((o) => o.lat))));
    // the newest file with objects not on a map yet
    for (const r of [...runs].reverse()) {
      if (r.format === "derived" || hidden.includes(r.id)) continue;
      const cs = detectObjects(r).candidates.filter((c) => addable(c) && !(c.picks.lat && onMaps.has(c.picks.lat.id)));
      if (cs.length) return { runId: r.id, cands: cs };
    }
    return null;
  }, [runs, ws, hidden]);
  const offer = useApp((s) => s.compareOffer);
  const [frame, setFrame] = useState<CompareFrame>("ned");
  const [busy, setBusy] = useState(false);
  if (!found) {
    // N7: right after objects were added - their comparison in a frame, one click
    const plot = offer ? ws.tabs.flatMap((tb) => tb.plots).find((p) => p.id === offer) : undefined;
    const objs = plot?.objects ?? [];
    const P = plot ? objs.find((o) => o.id === pairOf(plot).primary) : undefined;
    if (!plot || objs.length < 2 || !P) return null;
    const close = () => useApp.setState({ compareOffer: null });
    return (
      <div className="obj-suggest obj-compare-offer" role="region" aria-label={t("relCompare")}>
        <span className="obj-suggest-text">{t("relOffer", { p: P.name })}</span>
        <span className="obj-suggest-btns">
          <select value={frame} aria-label={t("relFrame")} title={t(`relFrameHint_${frame}` as TKey)} onChange={(e) => setFrame(e.target.value as CompareFrame)}>
            {(["ned", "enu", "ecef", "lla", "track"] as const).map((f) => <option key={f} value={f}>{f.toUpperCase()}</option>)}
          </select>
          <button className="linklike obj-compare-make" disabled={busy}
            onClick={async () => { setBusy(true); try { await compareObjects(P, objs, frame); close(); } finally { setBusy(false); } }}>{t("relMakePlots")}</button>
          <button className="iconbtn sm obj-suggest-hide" onClick={close} title={t("close")} aria-label={t("close")}>×</button>
        </span>
      </div>
    );
  }
  const { runId, cands } = found;
  const hide = () => useApp.setState((s) => ({ objSuggestHidden: [...s.objSuggestHidden, runId] }));
  const mapOf = (): Plot | undefined => activeTab(useApp.getState().ws).plots.find((p) => p.mode === "geo" || p.mode === "3d");
  const addAll = async () => {
    const st = useApp.getState();
    try {
      const next = objectColors(mapOf());
      const objs = [];
      for (const c of cands) objs.push(await candidateObject(c, next()));
      if (actions.addObjectsToMaps(objs)) announce(cands);
    } catch (e) { st.toast({ kind: "error", text: String((e as Error).message) }); }
  };
  // Choose… / Why?: the found list on the tab's map (an empty map first when the tab has none)
  const open = (why: boolean) => {
    const id = mapOf()?.id ?? actions.addObjectsToMaps([]);
    if (id) useApp.setState({ objectDialog: { plotId: id, ...(why ? { why: true } : {}) } });
  };
  const names = cands.map((c) => c.name);
  return (
    <div className="obj-suggest" role="region" aria-label={t("objFoundTitle")}>
      <span className="obj-suggest-text" title={names.join(", ")}>
        {t(cands.length === 1 ? "objSuggestOne" : "objSuggestN", { n: cands.length, list: names.slice(0, 4).join(", ") + (names.length > 4 ? "…" : "") })}
      </span>
      <span className="obj-suggest-btns">
        <button className="linklike obj-suggest-add" onClick={() => void addAll()}>{cands.length === 1 ? t("objAddOne") : t("objAddAll", { n: cands.length })}</button>
        <button className="linklike obj-suggest-choose" onClick={() => open(false)}>{t("objSuggestChoose")}</button>
        <button className="linklike obj-suggest-why" onClick={() => open(true)}>{t("objWhy")}</button>
        <button className="iconbtn sm obj-suggest-hide" onClick={hide} title={t("objSuggestHide")} aria-label={t("objSuggestHide")}>×</button>
      </span>
    </div>
  );
}

function announce(cands: Candidate[]) {
  const st = useApp.getState();
  st.toast({ kind: "info", undoesWs: true, text: addedSummary(cands, st.lang),
    action: { label: translate(st.lang, "undo"), run: () => useApp.getState().undo() } });
}
