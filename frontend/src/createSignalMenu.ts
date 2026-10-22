/* T21b: the one "Create signal ▸" entry of the signal menus (file list and plot legend): the
   quick operations run at once, "Other operations…" opens Create signals with the signal(s) chosen
   (the panel's own seed - one way to hand signals over). With several signals (a selection),
   every quick operation makes one new signal per source. */
import { api } from "./api";
import { translate } from "./i18n";
import { actions, useApp, type MenuItem } from "./store";

const QUICK = [["derivative", "opDerivative"], ["integral", "opIntegral"]] as const;

/** The "Create signal ▸" item for one signal or several; quick results go into `plotId` (default: the active plot). */
export function createSignalItem(sig: string | string[], plotId?: string): MenuItem {
  const L = useApp.getState().lang;
  const ids = Array.from(new Set(Array.isArray(sig) ? sig : [sig]));
  const make = async (op: string) => {
    const made: string[] = [];
    try {
      for (const id of ids) {
        const r = await api.createDerived(op, [id], {});
        useApp.setState({ runs: r.runs });
        made.push(r.id);
      }
    } catch (err) {
      useApp.getState().toast({ kind: "error", text: String((err as Error).message) });
    }
    if (made.length === 1) actions.addSignal(made[0], plotId);
    else if (made.length) actions.addSignals(made, plotId);      // one undo step for all of them
    if (ids.length > 1) useApp.setState({ listSelUsed: true });
  };
  return {
    label: ids.length > 1 ? translate(L, "createSignalMenuMany", { n: ids.length }) : translate(L, "createSignalMenu"), run: () => {},
    items: [
      ...QUICK.map(([op, key]) => ({ label: translate(L, key), run: () => { void make(op); } })),
      { label: "", run: () => {}, sep: true },
      { label: translate(L, "createSignalMore"), run: () => useApp.setState({ analysisSeed: ids, panel: "analysis" }) },
    ],
  };
}
