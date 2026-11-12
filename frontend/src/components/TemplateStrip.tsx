import { countRender } from "../perf";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { api, type Template } from "../api";
import { tabHasContent, useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { fits as templateFits, tx } from "../templates";
import { openTemplates, saveAsTemplate } from "../templateMenu";
import { openTemplateNow } from "../smartStart";

/** The few templates that fit the open files best (the same matching as everywhere), worked out after the
 *  panel is drawn. One list for both places the chips show (W3): the empty plot, then the file panel. */
export function useTemplatePicks(): Template[] {
  const runs = useApp((s) => s.runs);
  const laterRuns = useDeferredValue(runs);
  const libOpen = useApp((s) => s.templatesOpen);
  const [all, setAll] = useState<Template[]>([]);
  // re-read the templates when the library closes (one may have been saved or deleted)
  useEffect(() => { if (!libOpen) api.templates().then((r) => setAll([...r.builtin, ...r.templates])).catch(() => {}); }, [libOpen]);
  const data = runs.filter((r) => r.format !== "derived");
  const [fitOf, setFitOf] = useState<Map<string, number>>(new Map());
  const runsKey = laterRuns.map((r) => `${r.id}:${r.signals.length}`).join("|");
  useEffect(() => {
    if (!all.length || !data.length) { setFitOf(new Map()); return; }
    let off = false;
    templateFits(all, laterRuns).then((m) => { if (!off) setFitOf(m); }).catch(() => {});
    return () => { off = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [all, runsKey]);
  return useMemo(() => {
    const f = (x: Template) => fitOf.get(x.id) ?? 0;
    // real fits first (own templates and the built-in views); the automatic ones fill the rest
    const fitting = all.filter((x) => !x.generator && !x.broken && f(x) > 0.15).sort((a, b) => f(b) - f(a));
    // the automatic ones: the position on the map when a file has one (first: it is the more telling),
    // the quick look, and comparing when several files are open
    const auto = [...all.filter((x) => x.generator === "objects" && f(x) > 0),
      ...all.filter((x) => x.generator === "quicklook" || (x.generator === "compare" && data.length > 1))];
    return [...fitting, ...auto].slice(0, 3);
  }, [all, fitOf, data.length]);
}

/** The chips: T48 one click opens the template when nothing has to be chosen (else the library);
 *  right-click: the library with its details. */
export function TemplateChips({ picks }: { picks: Template[] }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  return (
    <div className="tpl-strip-picks tpl-chips">
      {picks.map((x) => (
        <button key={x.id} className="chipbtn" onClick={async () => { if (!(await openTemplateNow(x.id))) openTemplates(x.id); }}
          onContextMenu={(e) => { e.preventDefault(); openTemplates(x.id); }}
          title={`${tx(x.description, lang) || tx(x.name, lang)}\n\n${t("tplChipHint")}`}>
          {tx(x.name, lang)}
        </button>
      ))}
    </div>
  );
}

/** W3: the suggestions inside the empty plot - its sentence, the chips, the whole library. Shown while the
 *  tab is empty and files are open; the file panel's strip takes over once something is plotted. */
export function EmptyPlotSuggestions() {
  const t = useT();
  const picks = useTemplatePicks();
  return (
    <div className="plot-empty plot-empty-start" data-tour="templates">
      <p>{t("emptyPlotStart")}</p>
      {picks.length > 0 && <TemplateChips picks={picks} />}
      <button className="linkbtn" onClick={() => openTemplates()}>{t("tplAll")}</button>
    </div>
  );
}

/* Templates in the file panel, for ANY kind of file (CSV, MAT, flight logs): the few that fit the open
   files best, the whole library, and saving the current plots as a template. W3: only once something is
   plotted - before that the suggestions are in the empty plot itself (one place at a time). */
export default function TemplateStrip() {
  countRender("TemplateStrip");
  const t = useT();
  const runs = useApp((s) => s.runs);
  const hasPlots = useApp((s) => s.ws.tabs.some(tabHasContent));
  // U7: once something is plotted the suggestions fold away (a click on the title shows them)
  const [unfold, setUnfold] = useState(false);
  const picks = useTemplatePicks();
  if (!runs.some((r) => r.format !== "derived") || !hasPlots) return null;
  return (
    <div className="tpl-strip" role="group" aria-label={t("tplStripTitle")}>
      <div className="tpl-strip-head">
        <Icon.Layout />
        <h3><button className="linklike tpl-strip-fold" aria-expanded={unfold} title={t("tplStripHint")}
          onClick={() => setUnfold(!unfold)}>{unfold ? "▾" : "▸"} {t("tplStripTitle")} <span className="muted">({picks.length})</span></button></h3>
        {/* 26.U3: folded, the strip is one line - the library and "save" are in the views menu (+ ▾) and
            Templates ▾, and here again when unfolded */}
        {unfold && <button className="linkbtn" onClick={() => openTemplates()}>{t("tplAll")}</button>}
      </div>
      {unfold && <TemplateChips picks={picks} />}
      {unfold && <button className="btn outline tpl-strip-save" onClick={saveAsTemplate}>
        <Icon.Save /> {t("tplSaveView")}
      </button>}
    </div>
  );
}
