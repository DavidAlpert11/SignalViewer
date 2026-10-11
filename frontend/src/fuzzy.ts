/**
 * Smart search (S-02). Every query word must match the text in one of three ways,
 * best first:
 *   1. substring                 "temp"   -> Temperature   (bonus at a word start)
 *   2. letters in order          "spd"    -> Speed, "eng rpm" -> Engine_RPM
 *   3. one typo (words >= 4)     "sepeed" -> Speed, "temprature" -> Temperature
 * Returns a score (higher = better) or null when it does not match.
 */
const SEP = /[\s._\-/:()[\]·,]+/;

function damerau1(a: string, b: string): boolean {
  // true when edit distance (with transposition) <= 1
  if (a === b) return true;
  const la = a.length, lb = b.length;
  if (Math.abs(la - lb) > 1) return false;
  let i = 0;
  while (i < la && i < lb && a[i] === b[i]) i++;
  if (la === lb) {
    if (a.slice(i + 1) === b.slice(i + 1)) return true;                      // substitution
    return i + 1 < la && a[i] === b[i + 1] && a[i + 1] === b[i] && a.slice(i + 2) === b.slice(i + 2); // swap
  }
  return la > lb ? a.slice(i + 1) === b.slice(i) : a.slice(i) === b.slice(i + 1); // deletion / insertion
}

function subsequence(text: string, tok: string): number | null {
  let pos = -1, gaps = 0;
  for (const ch of tok) {
    const j = text.indexOf(ch, pos + 1);
    if (j < 0) return null;
    if (pos >= 0) gaps += j - pos - 1;
    pos = j;
  }
  return gaps;
}

export function fuzzyScore(text: string, query: string): number | null {
  const toks = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!toks.length) return 0;
  const t = text.toLowerCase();
  const words = t.split(SEP).filter(Boolean);
  let score = 0;
  for (const tok of toks) {
    const i = t.indexOf(tok);
    if (i >= 0) {
      const start = i === 0 || SEP.test(t[i - 1]) || (/[a-z]/.test(text[i] ?? "") && /[A-Z]/.test(text[i] ?? "") );
      score += 100 + (start ? 40 : 0) - Math.min(i, 30) + (tok.length === t.length ? 50 : 0);
      continue;
    }
    if (tok.length >= 2) {
      const g = subsequence(t, tok);
      if (g !== null && g <= tok.length * 3) { score += 50 - Math.min(g, 40); continue; }
    }
    // typo tolerance only for real words: "s123" must not match "s124"
    if (tok.length >= 4 && !/\d/.test(tok) && words.some((w) => damerau1(w, tok) || (w.length > tok.length && damerau1(w.slice(0, tok.length), tok)))) {
      score += 30;
      continue;
    }
    return null;
  }
  return score;
}

/** Filter keeping the original order (lists, trees). */
export const fuzzyMatch = (text: string, q: string) => !q.trim() || fuzzyScore(text, q) !== null;

/** Exact (substring) match for every word. */
export function exactMatch(text: string, q: string): boolean {
  const t = text.toLowerCase();
  return q.toLowerCase().split(/\s+/).filter(Boolean).every((tok) => t.includes(tok));
}

/** For lists that keep their order: exact matches when there are any, otherwise
 *  the approximate ones (letters in order, one typo). */
export function tieredFilter<T>(items: T[], text: (t: T) => string, q: string): T[] {
  if (!q.trim()) return items;
  const exact = items.filter((it) => exactMatch(text(it), q));
  return exact.length ? exact : items.filter((it) => fuzzyScore(text(it), q) !== null);
}

/** Filter and sort best-first (pickers, palette). */
export function fuzzySort<T>(items: T[], text: (t: T) => string, q: string): T[] {
  if (!q.trim()) return items;
  const scored: [T, number][] = [];
  for (const it of items) { const s = fuzzyScore(text(it), q); if (s !== null) scored.push([it, s]); }
  scored.sort((a, b) => b[1] - a[1]);
  return scored.map((x) => x[0]);
}
