/* T21b: the one "Create signal ▸" entry of the signal menus (file list and plot legend): the
   quick operations run at once, "Other operations…" opens Create signals with the signal chosen
   (the panel's own seed - one way to hand signals over). */
import { api } from "./api";
import { translate } from "./i18n";
import { actions, useApp, type MenuItem } from "./store";

const QUICK = [["derivative", "opDerivative"], ["integral", "opIntegral"]] as const;

/** The "Create signal ▸" item for a signal; a quick result goes into `plotId` (default: the active plot). */
export function createSignalItem(sig: string, plotId?: string): MenuItem {
  const L = useApp.getState().lang;
  const make = async (op: string) => {
    try {
      const r = await api.createDerived(op, [sig], {});
      useApp.setState({ runs: r.runs });
      actions.addSignal(r.id, plotId);
    } catch (err) {
      useApp.getState().toast({ kind: "error", text: String((err as Error).message) });
    }
  };
  return {
    label: translate(L, "createSignalMenu"), run: () => {},
    items: [
      ...QUICK.map(([op, key]) => ({ label: translate(L, key), run: () => { void make(op); } })),
      { label: "", run: () => {}, sep: true },
      { label: translate(L, "createSignalMore"), run: () => useApp.setState({ analysisSeed: [sig], panel: "analysis" }) },
    ],
  };
}
