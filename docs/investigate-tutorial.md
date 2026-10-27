# Tutorial: find out what went wrong

Ten minutes with the **Investigate** tools on two runs made for it, with a known answer.

The welcome screen → **find out what went wrong (Investigate)** opens them (or open
`examples/investigate/heavy_payload.csv` and `light_payload.csv`). The same quadcopter mission
flown twice through three wind gusts: with a **2.4 kg** payload and with **1.2 kg**. In the heavy run
the roll leaves its set point three times; in the light one it holds. Why?

(The files were built so the answer is known - see the end.)

## 1. See it

1. Look at the strip above the plots: the run's four phases and **three red flags** - *Motor3 flat
   at its limit*, in AUTO. Hover one; the light run (pick it in the strip) has none.
   Put **Roll** and **DesRoll** of the heavy run in a plot. Three bumps, around 38, 63 and 91 s.
2. Right-click **Mode** in the signal list → *Lane on every plot of this tab*: the flight mode under
   every plot. Hover the lane: the mode there and its stretch. All three bumps are in *AUTO*.

## 2. Name it

3. Press `d` (two cursors) and put them around the first bump (about 38.4 – 39.3 s).
4. On the bar above the span: **Find similar**. The Investigate panel opens with a condition
   already written from your selection. Write it plainly instead:
   `abs(Roll - DesRoll) > 5`, name it *Roll error*. The count shows while you type:
   **3 stretches** (all in the heavy run - hover the count: 0 in the light one).
5. **Save**. The stretches are shaded on the plots. Click the name, or press `]` / `[`, to go from one
   to the next.

## 3. Look at all of them

6. Under the list: **Stretches of Roll error** - a table, one row per stretch. Pick *Roll*, *max*:
   about the same each time.
7. **Together in a new tab**: the three stretches of the signal on top of each other, lined up at
   their start. Switch to *Motor3* in the table first, then press it again: motor 3 sits at 2000
   (its limit) in every one.
8. **What differs inside**: Roll, Vibe_Z, Motor3 and Wind are far from their usual level inside the
   stretches. Different, not yet cause.

## 4. What came first

9. Click the first stretch's row (both cursors on it), then **What changed?** on the bar.
10. Choose *All signals of the files*. The order: **Wind** (about −0.44 s), **Vibe_Z** (−0.3 s),
    **Motor3** (−0.22 s), Motor1, **Roll** (−0.02 s). The dashed lines on the plots are those moments.
    (Battery_V moves with the motors' current.)
11. Tick **Motor3** and **Roll** → **Lag between the two picked**: *Roll follows Motor3 by about
    120 ms*. **Show aligned** shifts Roll on the active plot so the two shapes meet.

## 5. Check it against the other run

12. Open the light run's Motor3 next to the heavy one's: the same gusts, but motor 3 stays below
    2000 - it has headroom. `Motor3 > 1990` as a condition: 3 stretches heavy, 0 light.
13. **Runs × conditions** (under the conditions): a row per run - *Payload_kg* (2.4 / 1.2, found
    by itself: it holds one value the whole run) - and a column per condition: Roll error 3 / 0,
    Motor3 saturated 3 / 0. Click the 3: the heavy run at its first stretch.

## 6. Write it up

14. In the Inspector, give your notes a status: the saturation *Fault*, a guess that did not hold
    (say "the battery sags first") *Rejected hypothesis*. Each keeps the view it was found in (⌖).
15. Investigate panel → **Steps so far**: what you did, in order. Untick what the report does not need.
16. Report panel → *Include the investigation* → **Preview**: findings with their plots, the rejected
    hypothesis, the steps, the conditions per run, and how to reproduce it - then your plots.

**The answer:** the gust needs more thrust from motor 3; with the heavy payload it is already near
its limit, saturates, and the roll cannot be held - about 0.1–0.15 s later. The light payload leaves
room, so the same gusts do nothing. What the tools gave: where (the condition), how often (3 of 3
gusts, heavy only), what was different (motor 3 at its limit), and in what order (wind → vibration
→ saturation → roll).

## How the files were made

`python tools/make_investigation_demo.py` writes them again. It builds each gust in this order:
wind, then vibration 0.1 s later, then motor 3 saturating 0.1 s after that (heavy only), and the
roll answering what the motor could not give 0.15 s later. Nothing else in the files is related to
the roll error.
