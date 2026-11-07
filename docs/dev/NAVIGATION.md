# Navigation: areas, view tabs and the rail (U8, design only)

Owner's request (2026-11-07): sketches for unifying the Recordings / Sweeps tabs, the view tabs and the
left rail - no code. This note is for choosing; nothing here is built.

## Today (1.21 + this round)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ ◈ Signal Viewer │ Recordings │ Sweeps │            [ Commands and signals  Ctrl K ]  ⚙ ☾ 🌐 Help │  top row (all areas)
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ 📂 💾 │ Attitude × │ Flight │ + │ +8 more ▾ │ Templates ▾ │        Live ▾ │ ↶ ↷ │ Clear ▾ │ ▤   │  the area's bar
├────┬──────────────┬──────────────────────────────────────────────────────────────────────────┤
│Data│ Files        │ 3×1 │ 🔗X 🔗Y │ Zoom: X │ Reset │ ⋯ │                       Cursor  Two    │  stage bar
│Crea│  …           │ copter_flight.bin · 246 s · Auto flags ○ ○        MODE.Mode ███████████  │  overview strip
│Comp│              │ MODE.Mode ███ STABILIZE ███ AUTO ███ RTL ███                             │  tab band (U3)
│Inv │              │ ┌ Roll ────────────────────────────────────────────────────────────────┐ │
│Rep │              │ │                                                                      │ │
│Log │              │ └──────────────────────────────────────────────────────────────────────┘ │
│Flt │              │ ! 3 findings ×  ⏮ ▶ ───────────────●──────────────  140.4 / 246.4 ×1    │  timeline
└────┴──────────────┴──────────────────────────────────────────────────────────────────────────┘
```

What a first-time user sees, as an engineer opening the app:

1. **Two rows of tabs that are not the same kind of thing.** *Recordings | Sweeps* (top row) switch the
   whole activity; *Attitude | Flight* (the row under it) switch views inside Recordings. They look
   alike and sit 40 px apart, so "Sweeps" reads as one more view. In Sweeps the second row holds its
   result tables as tabs - the same look a third time.
2. **The rail mixes tools and places.** Data, Create, Compare, Investigate, Report and Log are panels
   that work on what is open; **Fleet** is a different activity (a folder of logs, its own list and
   trend) that happens to live in a panel. **Log** appears only with a flight log open, so the rail
   moves under the pointer.
3. **Where things are opened.** Views come from the tab row (+, +N more, Templates ▾), from the file
   panel's template strip and from the start card - three places for one idea (open a view), plus the
   command palette.
4. In Hebrew everything mirrors except the plots, which is right, but the two tab rows then sit on the
   opposite side from the rail, which makes the "two kinds of tabs" problem stronger.

## Option A - the areas become a switch, Fleet becomes an area (smallest change)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ ◈ Signal Viewer  ⟦ Recordings ▪ Sweeps ▪ Fleet ⟧      [ Commands and signals  Ctrl K ]  ⚙ ☾ 🌐 ? │  a segmented switch,
├──────────────────────────────────────────────────────────────────────────────────────────────┤  not tabs
│ 📂 💾 ┊ VIEWS: Attitude × │ Flight │ + ▾ (new view · from a template · 8 more from Full review) │  one "+ ▾" for views
├────┬─────────────────────────────────────────────────────────────────────────────────────────┤
│Data│ …                                                                                       │
│Crea│                                                                                         │  the rail: tools only,
│Comp│                                                                                         │  always the same six;
│Inv │                                                                                         │  Log shown greyed (with
│Rep │                                                                                         │  "no flight log open")
│Log │                                                                                         │  instead of vanishing
└────┴─────────────────────────────────────────────────────────────────────────────────────────┘
```

- The top row's area choice is drawn as a **segmented switch** (one pill, three parts), clearly not a
  tab strip; the view tabs keep the tab look and get a small "Views" label.
- **Fleet moves from the rail to the switch** - it already has its own list, search and trend; as an
  area it gets the whole width.
- **One "+ ▾"** beside the view tabs: New view, From a template…, and the template's left-out tabs
  (U1's "+N more" folded into it); the file panel's template strip keeps only its suggestions.
- The rail always shows the same tools; Log is disabled with a tooltip when no flight log is open.
- Cost: S/M. Sessions unaffected (areas are UI state); `areas.ts` gains `fleet`; Fleet panel code moves
  to an area body. Risk: users who know Fleet in the rail (a tooltip on the old place for a release).

## Option B - an activity bar on the left (VS Code / MATLAB style)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ ◈ Signal Viewer │ 📂 💾 │ Attitude × │ Flight │ + ▾ │      [ Commands and signals ]  ⚙ ☾ 🌐 ?  │  one row less
├────┬────┬────────────────────────────────────────────────────────────────────────────────────┤
│ ▣  │Data│ …                                                                                  │
│Rec │Crea│                                                                                    │
│ ▦  │Comp│                                                                                    │
│Swp │Inv │                                                                                    │
│ ▥  │Rep │                                                                                    │
│Flt │Log │                                                                                    │
└────┴────┴────────────────────────────────────────────────────────────────────────────────────┘
  areas  tools of the area
```

- A narrow **activity column** (areas: Recordings, Sweeps, Fleet) left of the tool rail; the top row
  loses the area tabs and the area bar merges into it (one row of chrome less: ~40 px more for plots).
- Each area shows its own tool column (Sweeps: its four steps, today a separate step panel).
- Cost: M/L - the area bar and the top row merge (Live, Undo, Clear, Inspector find new places), the
  Sweeps step panel becomes its rail. Most familiar to engineers who use VS Code or MATLAB; the most
  moving of controls this round has avoided (owner's F35 placed them).

## Option C - one tab strip for everything (rejected)

Views of Recordings and Sweeps studies in one strip, each tab with its kind's icon. It removes a row
but mixes a 2 s plot switch with loading a whole study, and Undo / Live / Clear would have to know
which kind of tab is active. Listed only so it is not proposed again.

## Recommendation

**Option A now** (it fixes 1-3 with little movement and keeps the owner's F35 bar), and keep B as the
direction if a third area (e.g. Live as its own area, or Reports) comes. Questions for the owner:

1. Fleet as an area (A) - yes / no?
2. One "+ ▾" for views (folding U1's "+N more" and Templates ▾'s "open" into it) - yes / no?
3. Log in the rail: greyed when not available, or hidden as today?
