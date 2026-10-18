/* The app's one store, made of slices by area (store/slices/*). Components read it with
   useApp(selector); actions (store/actions/*) change it - the workspace only through `commit`. */
import { create } from "zustand";
import { dataSlice, type DataSlice } from "./slices/data";
import { liveSlice, type LiveSlice } from "./slices/live";
import { uiSlice, type UiSlice } from "./slices/ui";
import { viewSlice, type ViewSlice } from "./slices/view";
import { workspaceSlice, type WorkspaceSlice } from "./slices/workspace";

export type AppState = WorkspaceSlice & DataSlice & ViewSlice & LiveSlice & UiSlice;

export const useApp = create<AppState>((set, get) => ({
  ...workspaceSlice(set, get),
  ...dataSlice(),
  ...viewSlice(),
  ...liveSlice(),
  ...uiSlice(set, get),
}));
