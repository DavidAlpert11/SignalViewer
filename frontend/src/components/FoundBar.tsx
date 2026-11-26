import { useDeferredValue, useMemo, useState } from "react";
import { activeTab, actions, useApp, type Plot } from "../store";
import { useT } from "../i18n";
import { pairOf } from "../relation";
import { detectObjects } from "../objectDetect";
import { addable } from "../objectAdd";
import { addFoundObjects, FIND_LABEL, findIn, foundHidden, hideFound, markFound, onSomeMap, runFind, type Find } from "../found";

/* AU1 (owner, 2026-11-26): what the app can do by itself with the newest file, found from its names - ONE quiet line
   in the file panel, a chip per find (one click each), *Why?* naming the matched signals and the page of the names
   the app recognises. It took over N5's objects line: the objects keep their sentence and Add all / Choose… / Why?
   inside it (same classes), and N7's offer to compare them right after they are added. A chip that was used goes;
   × hides the line for that file, remembered by the file's name (the file's menu *Found in this file ▸* and the
   palette still list everything). */
export default function FoundBar() {
  const t = useT();
  const runs = useDeferredValue(useApp((s) => s.runs));
  const ws = useApp((s) => s.ws);
  const hidden = useApp((s) => s.objSuggestHidden);
  const done = useApp((s) => s.foundDone);
  const offer = useApp((s) => s.compareOffer);
  const [why, setWhy] = useState(false);
  const found = useMemo(() => {
    const gone = new Set(foundHidden());
    for (const r of [...runs].reverse()) {
      if (r.format === "derived" || hidden.includes(r.id) || gone.has(r.name)) continue;
      const finds = findIn(r, runs, onSomeMap).filter((f) => !done.includes(`${r.id}:${f.id}`));
      if (finds.length) return { run: r, finds };
    }
    return null;
    // ws: an object put on a map (or taken off) changes what is offered
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runs, ws, hidden, done]);
  // N7: right after objects were added - the offer opens Compare objects… for this plot
  const offerPlot = offer ? ws.tabs.flatMap((tb) => tb.plots).find((p) => p.id === offer) : undefined;
  const offerP = offerPlot ? offerPlot.objects?.find((o) => o.id === pairOf(offerPlot).primary) : undefined;
  const offerNode = offerPlot && (offerPlot.objects?.length ?? 0) > 1 && offerP ? (
    <span className="obj-compare-offer found-group">
      <span className="obj-suggest-text">{t("relOffer", { p: offerP.name })}</span>
      <button className="linklike obj-compare-make" onClick={() => { useApp.setState({ compareDialog: { plotId: offerPlot.id }, compareOffer: null }); }}>{t("cmpOpen")}</button>
      <button className="iconbtn sm obj-compare-close" onClick={() => useApp.setState({ compareOffer: null })} title={t("close")} aria-label={t("close")}>×</button>
    </span>
  ) : null;
  if (!found) {
    return offerNode ? <div className="found-bar obj-suggest obj-compare-offer" role="region" aria-label={t("relCompare")}>{offerNode}</div> : null;
  }
  const { run, finds } = found;
  const objects = finds.find((f) => f.id === "objects");
  const chips = finds.filter((f) => f.id !== "objects" && !(f.id === "truthnav" && offerNode));
  const go = (f: Find) => { markFound(run.id, f.id); void runFind(f.id, run); };
  const cands = objects ? detectObjects(run).candidates.filter((c) => addable(c) && !onSomeMap(c)) : [];
  const names = cands.map((c) => c.name);
  const mapOf = (): Plot | undefined => activeTab(useApp.getState().ws).plots.find((p) => p.mode === "geo" || p.mode === "3d");
  // Choose… / Why? of the objects: the found list on the tab's map (an empty map first when the tab has none)
  const openObjects = (whyToo: boolean) => {
    const id = mapOf()?.id ?? actions.addObjectsToMaps([]);
    if (id) useApp.setState({ objectDialog: { plotId: id, ...(whyToo ? { why: true } : {}) } });
  };
  return (
    <div className={`found-bar${objects ? " obj-suggest" : ""}`} role="region" aria-label={t("fndMenu")} data-run={run.id}>
      <div className="found-line">
        <span className="found-head" title={run.name}>{t("fndIn", { file: run.name })}</span>
        {objects && (
          <span className="found-group found-objects">
            <span className="obj-suggest-text" title={names.join(", ")}>
              {t(cands.length === 1 ? "objSuggestOne" : "objSuggestN", { n: cands.length, list: names.slice(0, 4).join(", ") + (names.length > 4 ? "…" : "") })}
            </span>
            <button className="linklike obj-suggest-add" onClick={() => void addFoundObjects(cands).then((r) => { if (r.left) markFound(run.id, "objects"); })}>{cands.length === 1 ? t("objAddOne") : t("objAddAll", { n: cands.length })}</button>
            <button className="linklike obj-suggest-choose" onClick={() => openObjects(false)}>{t("objSuggestChoose")}</button>
            <button className="linklike obj-suggest-why" onClick={() => openObjects(true)}>{t("objWhy")}</button>
          </span>
        )}
        {offerNode}
        {chips.map((f) => (
          <button key={f.id} className={`chipbtn found-chip found-${f.id}`} onClick={() => go(f)} title={`${t(`${FIND_LABEL[f.id]}Hint` as Parameters<typeof t>[0])}\n${f.why.slice(0, 6).join("\n")}`}>
            {t(FIND_LABEL[f.id], { n: f.n })}
          </button>
        ))}
        <span className="found-end">
          <button className="linklike found-why" aria-expanded={why} onClick={() => setWhy(!why)}>{t("fndWhy")}</button>
          <button className="iconbtn sm obj-suggest-hide found-hide" onClick={() => hideFound(run)} title={t("fndHide")} aria-label={t("fndHide")}>×</button>
        </span>
      </div>
      {why && (
        <div className="found-why-list" aria-label={t("fndWhyTitle")}>
          {finds.map((f) => (
            <div key={f.id} className={`found-why-row found-why-${f.id}`}>
              <b>{t(FIND_LABEL[f.id], { n: f.n })}</b> <span dir="ltr">{f.why.join(" · ")}</span>
            </div>
          ))}
          <button className="linklike found-names" onClick={() => useApp.setState({ namingOpen: true })}>{t("fndNames")}</button>
        </div>
      )}
    </div>
  );
}
