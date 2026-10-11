import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { api, type Template } from "../api";
import { tabHasContent, useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { BUILTIN_TEMPLATES, fit, tx } from "../templates";
import { openTemplates, saveAsTemplate } from "../templateMenu";

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
  const [mine, setMine] = useState<Template[]>([]);
  // re-read the user's templates when the library closes (one may have been saved or deleted)
  useEffect(() => { if (!libOpen) api.templates().then((r) => setMine(r.templates)).catch(() => {}); }, [libOpen]);
  const data = runs.filter((r) => r.format !== "derived");

  const picks = useMemo(() => {
    const all = [...BUILTIN_TEMPLATES, ...mine];
    // real fits first (own templates and the built-in views); the automatic ones fill the rest
    const fitting = all.filter((x) => !x.generator && !x.broken)
      .map((x) => ({ x, f: fit(x, all, laterRuns) })).filter((e) => e.f > 0.15)
      .sort((a, b) => b.f - a.f).map((e) => e.x);
    // the automatic ones: the position on the map when a file has one (first: it is the more telling),
    // the quick look, and comparing when several files are open
    const auto = [...all.filter((x) => x.generator === "objects" && fit(x, all, laterRuns) > 0),
      ...all.filter((x) => x.generator === "quicklook" || (x.generator === "compare" && data.length > 1))];
    return [...fitting, ...auto].slice(0, 3);
  }, [mine, laterRuns, data.length]);

  if (!data.length) return null;
  return (
    <div className="tpl-strip" role="group" aria-label={t("tplStripTitle")}>
      <div className="tpl-strip-head">
        <Icon.Layout /><h3 title={t("tplStripHint")}>{t("tplStripTitle")}</h3>
        <button className="linkbtn" onClick={() => openTemplates()}>{t("tplAll")}</button>
      </div>
      <div className="tpl-strip-picks">
        {picks.map((x) => (
          <button key={x.id} className="chipbtn" onClick={() => openTemplates(x.id)} title={tx(x.description, lang) || tx(x.name, lang)}>
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
