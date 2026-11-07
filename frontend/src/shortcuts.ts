/* The app's keyboard shortcuts in one listener (A3: moved out of App.tsx). Help > Keyboard shortcuts
   lists them; a key is handled here only when nothing being typed into has it. */
import { useEffect } from "react";
import { actions, recordingExtent, useApp } from "./store";
import { areaKey } from "./areaCommands";
import { stepOccurrence } from "./conditions";
import { openSession, saveSession } from "./files";
import { refreshAll } from "./live";
import { escapeTaken } from "./components/Overlays";

export function useShortcuts() {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const st = useApp.getState();
      const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement || e.target instanceof HTMLTextAreaElement;
      const mod = e.ctrlKey || e.metaKey;
      const rec = st.area === "recordings";        // files, sessions, tabs and refresh are the Recordings area's
      if (mod && e.key.toLowerCase() === "k") { e.preventDefault(); useApp.setState({ paletteOpen: true, paletteMode: "all" }); return; }
      // T24: quick open - recent files and folders, favourites (Ctrl+P is the editors' "go to file")
      if (rec && mod && e.key.toLowerCase() === "p" && !e.shiftKey) { e.preventDefault(); useApp.setState({ paletteOpen: true, paletteMode: "open" }); return; }
      if (rec && mod && e.key.toLowerCase() === "o" && e.shiftKey) { e.preventDefault(); openSession(); return; }
      if (rec && mod && e.key.toLowerCase() === "o") { e.preventDefault(); useApp.setState({ browserOpen: true }); return; }
      if (rec && mod && e.key.toLowerCase() === "s") { e.preventDefault(); saveSession(); return; }
      const SCALES = [1, 1.12, 1.25] as const;
      if (mod && (e.key === "=" || e.key === "+")) { e.preventDefault(); const i = SCALES.indexOf(st.uiScale); useApp.setState({ uiScale: SCALES[Math.min(2, i + 1)] }); return; }
      if (mod && e.key === "-") { e.preventDefault(); const i = SCALES.indexOf(st.uiScale); useApp.setState({ uiScale: SCALES[Math.max(0, i - 1)] }); return; }
      if (mod && e.key === "0") { e.preventDefault(); useApp.setState({ uiScale: 1 }); return; }
      // F22: next / previous tab (Ctrl+Tab too where the window lets it through - a browser keeps it)
      if (rec && mod && (e.key === "PageDown" || e.key === "PageUp")) { e.preventDefault(); actions.cycleTab(e.key === "PageDown" ? 1 : -1); return; }
      if (rec && e.ctrlKey && e.key === "Tab") { e.preventDefault(); actions.cycleTab(e.shiftKey ? -1 : 1); return; }
      if (rec && (e.key === "F5" || (mod && e.key.toLowerCase() === "r"))) { e.preventDefault(); refreshAll(); return; }   // not a page reload
      if (typing || st.paletteOpen || st.browserOpen || st.picker || st.importPaths || st.helpOpen || st.guideOpen || st.settingsOpen) return;
      if (e.key === "?") { useApp.setState({ helpOpen: true }); return; }
      if (e.key === "F1") { e.preventDefault(); useApp.setState({ guideOpen: true }); return; }   // T55
      if (mod && e.key === ",") { e.preventDefault(); useApp.setState({ settingsOpen: true }); return; }   // T18
      if (!rec) { if (areaKey(st.area, e)) e.preventDefault(); return; }   // another area's own keys (areaCommands.ts)
      // the keys below act on the Recordings area (undo, cursor, plots, timeline)
      if (mod && e.key.toLowerCase() === "z" && !e.shiftKey) { e.preventDefault(); st.undo(); return; }
      if (mod && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) { e.preventDefault(); st.redo(); return; }
      if (mod) return;
      if (e.key === " ") { e.preventDefault(); actions.toggleCursor(); }
      else if (e.key.toLowerCase() === "d") actions.toggleDual();
      else if (e.key.toLowerCase() === "r") actions.resetZoom();
      else if (e.key.toLowerCase() === "z") actions.cycleZoomMode();
      else if (e.key.toLowerCase() === "n") { e.preventDefault(); actions.addNoteAtCursor(); }
      else if ((e.key === "]" || e.key === "[") && st.condFocus) { e.preventDefault(); stepOccurrence(st.condFocus, e.key === "]" ? 1 : -1); }
      else if (e.key === "Backspace" || (e.altKey && e.key === "ArrowLeft")) { e.preventDefault(); actions.zoomBack(); }
      else if (e.key === "Home" || e.key === "End") {          // the timeline: start / end of the recording
        const r = recordingExtent(st.runs);
        if (r) { e.preventDefault(); const tt = e.key === "Home" ? r[0] : r[1]; actions.setTime(tt); actions.followTime(tt); }
      }
      else if (e.key.toLowerCase() === "p") actions.togglePlay();
      else if (/^[1-9]$/.test(e.key)) actions.setActivePlot(Number(e.key) - 1);
      else if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && st.cursor.on && st.cursor.t1 !== null) {
        // jump from recorded value to recorded value (no interpolation); Shift = 10 samples
        e.preventDefault();
        actions.stepCursor((e.key === "ArrowRight" ? 1 : -1) * (e.shiftKey ? 10 : 1));
      } else if (e.key === "Delete" && st.selected) actions.removeSignal(st.selected.plotId, st.selected.sig);
      else if (e.key === "Escape" && !escapeTaken() && !st.menu) {
        // one step back per press: the selection, then the newest message, then the start card
        // (the start card used to stay over the plots until its × was clicked)
        if (st.selected) useApp.setState({ selected: null });
        else if (st.toasts.length) st.dismiss(st.toasts[st.toasts.length - 1].id);
        else if (st.startCard) useApp.setState({ startCard: null });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

}
