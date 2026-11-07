import { useMemo, useState } from "react";
import type { Template, TplTab } from "../api";
import { useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { announceOpened, applyTemplate, defaultTabIdx, expand, tx } from "../templates";
import { useEscape } from "./Overlays";

/** U1: a template's tabs with a checkbox each, All / None, and its default tabs marked - the
 *  library's details and the "which tabs?" dialog show the same list. */
export function TabChecklist({ tpl, tabs, chosen, setChosen }: {
  tpl: Template; tabs: (TplTab & { from: string })[]; chosen: Set<number>; setChosen: (s: Set<number>) => void;
}) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const defaults = new Set(tpl.defaultTabs?.length ? defaultTabIdx(tpl, tabs) : []);
  return (
    <>
      {tabs.length > 1 && (
        <div className="tpl-tabs-bulk">
          <button className="linkbtn" onClick={() => setChosen(new Set(tabs.map((_x, i) => i)))}>{t("tplTabsAll")}</button>
          <button className="linkbtn" onClick={() => setChosen(new Set())}>{t("tplTabsNone")}</button>
        </div>
      )}
      <ul className="tpl-tabs">
        {tabs.map((x, i) => (
          <li key={i}><label>
            <input type="checkbox" checked={chosen.has(i)} onChange={(ev) => {
              const n = new Set(chosen); if (ev.target.checked) n.add(i); else n.delete(i); setChosen(n);
            }} />
            <span>{tx(x.name, lang)}</span>
            {defaults.size < tabs.length && defaults.has(i) && <span className="badge tpl-default">{t("tplDefaultMark")}</span>}
            <span className="hint">{(x.plots.length === 1 ? t("tplPlotsOne") : t("tplPlotsN", { n: x.plots.length }))}{x.from !== tpl.name ? ` · ${tx(x.from, lang)}` : ""}</span>
          </label></li>
        ))}
      </ul>
    </>
  );
}

/** U1: a template with several tabs opened from its chip: which tabs? Its default tabs are checked
 *  (all of them when it names none); the rest stay offered by "+N more" beside the tab bar. */
export default function TabChoiceDialog() {
  const d = useApp((s) => s.tabChoice);
  const close = () => useApp.setState({ tabChoice: null });
  useEscape(close, !!d);
  if (!d) return null;
  return <Body key={d.tpl.id} tpl={d.tpl} all={d.all} bind={d.bind} close={close} />;
}

function Body({ tpl, all, bind, close }: { tpl: Template; all: Template[]; bind: Record<string, string>; close: () => void }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const tabs = useMemo(() => expand(tpl, all).tabs, [tpl, all]);
  const [chosen, setChosen] = useState<Set<number>>(() => new Set(defaultTabIdx(tpl, tabs)));
  const [busy, setBusy] = useState(false);
  const open = async () => {
    setBusy(true);
    try {
      const res = await applyTemplate(tpl, all, bind, tabs.map((_x, i) => i).filter((i) => chosen.has(i)));
      if (res.tabs) useApp.setState({ startCard: null });
      announceOpened(tpl, res, true);
      close();
    } catch (err) {
      useApp.getState().toast({ kind: "error", text: String((err as Error).message) });
      setBusy(false);
    }
  };
  const title = t("tabChoiceTitle", { name: tx(tpl.name, lang) });
  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog small tab-choice" role="dialog" aria-label={title} onMouseDown={(e) => e.stopPropagation()}
        onKeyDown={(e) => { if (e.key === "Enter" && chosen.size && !busy) open(); }}>
        <div className="dialog-head"><h2>{title}</h2><button className="iconbtn" onClick={close} aria-label={t("close")}><Icon.X /></button></div>
        <div className="dialog-pad">
          <TabChecklist tpl={tpl} tabs={tabs} chosen={chosen} setChosen={setChosen} />
          <p className="hint tab-choice-hint">{t("tabChoiceHint")}</p>
        </div>
        <div className="dialog-foot"><span className="spacer" />
          <button className="btn outline" onClick={close}>{t("cancel")}</button>
          <button className="btn primary" autoFocus disabled={!chosen.size || busy} onClick={open}>
            {chosen.size === 1 ? t("tabChoiceOpenOne") : t("tabChoiceOpen", { n: chosen.size })}</button></div>
      </div>
    </div>
  );
}
