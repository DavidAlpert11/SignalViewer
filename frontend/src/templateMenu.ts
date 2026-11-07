import { tabHasContent, useApp, type MenuItem } from "./store";
import type { TKey } from "./i18n";

/* One set of template actions for every place that offers them (the Templates ▾ menu, file panel, palette),
   so opening / saving a template or a collection works the same for any kind of file. */

export const openTemplates = (select?: string | null) =>
  useApp.setState({ templatesOpen: true, templatesSelect: select ?? null });
export const saveAsTemplate = () => useApp.setState({ templatesOpen: true, templatesNew: "tab" });
export const newCollection = () => useApp.setState({ templatesOpen: true, templatesNew: "collection" });

export function templateMenuItems(t: (k: TKey) => string): MenuItem[] {
  const hasPlots = useApp.getState().ws.tabs.some(tabHasContent);
  return [
    // U9: opening a template is in the views menu ("+ ▾" beside the tabs); here: making one
    { label: t("tplMenuSave"), run: saveAsTemplate, disabled: !hasPlots },
    { label: t("tplMenuCollection"), run: newCollection },
  ];
}
