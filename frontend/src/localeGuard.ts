/* Runs before anything else (first import in main.tsx).
   Some systems report a locale the browser's Intl cannot use - e.g. "en-US@posix" on Linux
   with a POSIX / C locale. uPlot builds an Intl.NumberFormat from navigator.language while it
   loads, so such a tag would stop the whole app with a blank window. Normalise it here. */
function usable(tag: string): boolean {
  try { new Intl.NumberFormat(tag); return true; } catch { return false; }
}
try {
  const raw = navigator.language || "";
  if (!usable(raw)) {
    const clean = raw.split(/[@.]/)[0].replace(/_/g, "-");
    const tag = clean && clean.toLowerCase() !== "c" && clean.toLowerCase() !== "posix" && usable(clean) ? clean : "en-US";
    const list = [tag, ...(navigator.languages || []).filter((l) => l !== raw && usable(l))];
    Object.defineProperty(navigator, "language", { value: tag, configurable: true });
    Object.defineProperty(navigator, "languages", { value: Object.freeze(list), configurable: true });
  }
} catch { /* never block the app over this */ }
export {};
