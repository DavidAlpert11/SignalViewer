import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { api, type Template } from "../api";
import { tabHasContent, useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { fits as templateFits, tx } from "../templates";
import { openTemplates, saveAsTemplate } from "../templateMenu";
import { openTemplateNow } from "../smartStart";

/* Templates in the file panel, for ANY kind of file (CSV, MAT, flight logs): the few that fit the
   open files best, the whole library, and saving the current plots as a template. */
export default function TemplateStrip() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  // the suggestions are worked out after the file panel is drawn, not in the same frame
  const laterRuns = useDeferredValue(runs);
  const libOpen = useApp((s) => s.templatesOpen);
  const hasPlots = useApp((s) => s.ws.tabs.some(tabHasContent));
  const [all, setAll] = useState<Template[]>([]);
  // re-read the templates when the library closes (one may have been saved or deleted)
  useEffect(() => { if (!libOpen) api.templates().then((r) => setAll([...r.builtin, ...r.templates])).catch(() => {}); }, [libOpen]);
  const data = runs.filter((r) => r.format !== "derived");
  // how well each template fits the open files (backend, the same matching as everywhere)
  const [fitOf, setFitOf] = useState<Map<string, number>>(new Map());
  const runsKey = laterRuns.map((r) => `${r.id}:${r.signals.length}`).join("|");
  useEffect(() => {
    if (!all.length || !data.length) { setFitOf(new Map()); return; }
    let off = false;
    templateFits(all, laterRuns).then((m) => { if (!off) setFitOf(m); }).catch(() => {});
    return () => { off = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [all, runsKey]);

  const picks = useMemo(() => {
    const f = (x: Template) => fitOf.get(x.id) ?? 0;
    // real fits first (own templates and the built-in views); the automatic ones fill the rest
    const fitting = all.filter((x) => !x.generator && !x.broken && f(x) > 0.15).sort((a, b) => f(b) - f(a));
    // the automatic ones: the position on the map when a file has one (first: it is the more telling),
    // the quick look, and comparing when several files are open
    const auto = [...all.filter((x) => x.generator === "objects" && f(x) > 0),
      ...all.filter((x) => x.generator === "quicklook" || (x.generator === "compare" && data.length > 1))];
    return [...fitting, ...auto].slice(0, 3);
  }, [all, fitOf, data.length]);

  if (!data.length) return null;
  return (
    <div className="tpl-strip" role="group" aria-label={t("tplStripTitle")}>
      <div className="tpl-strip-head">
        <Icon.Layout /><h3 title={t("tplStripHint")}>{t("tplStripTitle")}</h3>
        <button className="linkbtn" onClick={() => openTemplates()}>{t("tplAll")}</button>
      </div>
      <div className="tpl-strip-picks">
        {picks.map((x) => (
          // T48: one click opens the template when nothing has to be chosen (else the library, as before);
          // right-click: the library with its details
          <button key={x.id} className="chipbtn" onClick={async () => { if (!(await openTemplateNow(x.id))) openTemplates(x.id); }}
            onContextMenu={(e) => { e.preventDefault(); openTemplates(x.id); }}
            title={`${tx(x.description, lang) || tx(x.name, lang)}\n\n${t("tplChipHint")}`}>
            {tx(x.name, lang)}
          </button>
        ))}
      </div>
      <button className="btn outline tpl-strip-save" disabled={!hasPlots} onClick={saveAsTemplate}>
        <Icon.Save /> {t("tplSaveView")}
      </button>
    </div>
  );
}
