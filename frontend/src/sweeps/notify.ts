/* The Sweeps area's messages go where every message of the app goes (the notices, Toasts): what an
   action did - saved, exported, merged - or why it failed. Why a view is empty stays in that view. */
import { useApp } from "../store";
import type { TFn } from "../i18n";
import { useSweeps } from "./state";

/** a file written: long enough to read its path */
const WROTE_MS = 9000;

export function notify(text: string, kind: "info" | "error" = "info", ms?: number) {
  if (text) useApp.getState().toast({ kind, text, ms: ms ?? (kind === "info" && /[\\/]/.test(text) ? WROTE_MS : undefined) });
}
export const notifyError = (e: unknown) => notify(e instanceof Error ? e.message : String(e), "error");
/** an action's message when it is done, or its error */
export const say = (p: Promise<string | void>) => p.then((m) => { if (m) notify(m); }).catch(notifyError);
/** a set added to the re-run list: said, with a way there (its home is the Next runs tab) */
export const addedToNext = (t: TFn) => useApp.getState().toast({ kind: "info", text: t("swAddedToNext"), key: "sw-added-next",
  action: { label: t("swOpenNextRuns"), run: () => useSweeps.getState().setView({ step: "results", center: "next" }) } });
