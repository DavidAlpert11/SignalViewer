/* State lanes: where one is shown (this plot, every plot of the tab, every time plot of every tab)
   and whether its signal is "always a state" - the same menu from the lane itself (right-click on
   it), its legend chip and the signal list. */
import { translate, type TKey } from "./i18n";
import { actions, activeTab, alwaysState, laneScope, useApp, type LaneScope, type MenuItem } from "./store";

const mark = (on: boolean, label: string) => (on ? `✓ ${label}` : label);

/** For a lane (or a would-be lane) of this signal in this plot. `remove`: the lane's own menu. */
export function laneMenuItems(plotId: string, sig: string, remove = false): MenuItem[] {
  const st = useApp.getState();
  const t = (k: TKey) => translate(st.lang, k);
  const tab = st.ws.tabs.find((x) => x.plots.some((p) => p.id === plotId));
  const plot = tab?.plots.find((p) => p.id === plotId);
  if (!tab || !plot) return [];
  const now = laneScope(st.ws, tab, plot, sig);
  const to = (s: LaneScope) => () => actions.setLaneScope(plotId, sig, now === s && s !== "plot" ? null : s);
  const always = alwaysState(st.ws, sig);
  return [
    { label: mark(now === "plot", t("laneOnPlot")), run: to("plot") },
    { label: mark(now === "tab", t("laneOnTab")), run: to("tab") },
    { label: mark(now === "all", t("laneOnAll")), run: to("all") },
    ...(remove && now ? [{ label: t("laneRemove"), run: () => actions.setLaneScope(plotId, sig, null) }] : []),
    { label: "", run: () => {}, sep: true },
    { label: mark(always, t("alwaysState")), run: () => actions.setAlwaysState(sig, !always) },
  ];
}

/** The signal list has no plot: the active plot of the active tab stands for "here". */
export function laneMenuForSignal(sig: string): MenuItem[] {
  const tab = activeTab(useApp.getState().ws);
  const p = tab.plots[tab.active] ?? tab.plots[0];
  return p ? laneMenuItems(p.id, sig) : [];
}
