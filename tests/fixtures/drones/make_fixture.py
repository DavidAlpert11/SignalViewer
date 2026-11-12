"""How the tiny W14 fixture tables were made, and the expected answer by plain loops (W0 contract).

Run once: python tests/fixtures/drones/make_fixture.py. The CSVs and expected.json are committed; the
vectorised engine (svcore/sweeps_common.py) must give exactly expected.json for fixture.svstudy.json.
Formulas are a made-up toy, not the drone model of tools/make_drone_sweeps.py."""
import csv
import itertools
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
KP, KI = [1.0, 2.0, 3.0], [0.5, 1.0]


def r3(x):
    return round(x, 3)


def write(name, cols, rows):
    with open(os.path.join(HERE, name), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)


a = [[kp, ki, wind, r3(2 + 3 * kp - 2 * ki + 0.4 * wind), r3(4 / kp + 1 / ki + 0.1 * wind)]
     for kp, ki, wind in itertools.product(KP + [4.0], KI, [0, 5])]           # Kp = 4 only in A: "not run" in B, C
write("drone_a.csv", ["Kp", "Ki", "wind", "overshoot", "settling_time"], a)
b = [[kp, ki, m, r3(1 + 2.5 * kp + 1.2 * m - ki), r3(0.075 * kp * m + 0.1 * ki), r3(10 + 2 * kp * m + 3 * ki)]
     for kp, ki, m in itertools.product(KP, KI, [2, 4])]
write("drone_b.csv", ["Kp", "Ki", "mass", "overshoot", "motor_sat", "energy"], b)
MISSING = {(1.0, 1.0, 20, 5), (3.0, 0.5, 10, 0)}
c = [[kp, ki, fh, wind, r3(70 - 8 * kp - 5 * ki + 0.5 * fh - wind), r3(3 / kp + 1 / ki + 10 / fh + 0.05 * wind)]
     for kp, ki, fh, wind in itertools.product(KP, KI, [10, 20], [0, 5]) if (kp, ki, fh, wind) not in MISSING]
write("drone_c.csv", ["P_gain", "I_gain", "filter_hz", "wind", "phase_margin", "settling_time"], c)

# ---- the expected answer, by plain loops
A = {(r[0], r[1], r[2]): {"overshoot": r[3], "settling_time": r[4]} for r in a}
B = {(r[0], r[1], r[2]): {"overshoot": r[3], "motor_sat": r[4], "energy": r[5]} for r in b}
C = {(r[0], r[1], r[2], r[3]): {"phase_margin": r[4], "settling_time": r[5]} for r in c}


def table_a(kp, ki):
    worst, scen = None, None
    for wind in (0, 5):
        row = A.get((kp, ki, wind))
        if row is None:
            return {"status": "not_run"}
        if not row["overshoot"] < 10:
            return {"status": "fail", "scenario": {"wind": wind}, "constraint": "overshoot < 10", "by": r3(row["overshoot"] - 10)}
        if worst is None or row["settling_time"] > worst:
            worst, scen = row["settling_time"], {"wind": wind}
    return {"status": "pass", "score": worst, "worst": scen, "local": None}


def table_b(kp, ki):
    worst, scen = None, None
    if not any((kp, ki, m) in B for m in (2, 4)):
        return {"status": "not_run"}
    for m in (2, 4):
        row = B.get((kp, ki, m))
        if row is None:
            return {"status": "fail", "scenario": {"mass": m}, "constraint": "not run"}
        if not (row["overshoot"] < 12 and row["motor_sat"] < 0.9):
            return {"status": "fail", "scenario": {"mass": m}, "constraint": "overshoot < 12 and motor_sat < 0.9"}
        if worst is None or row["energy"] > worst:
            worst, scen = row["energy"], {"mass": m}
    return {"status": "pass", "score": worst, "worst": scen, "local": None}


def table_c(kp, ki):
    if not any(k[:2] == (kp, ki) for k in C):
        return {"status": "not_run"}
    best = None
    for fh in (10, 20):
        worst, scen, ok = None, None, True
        for wind in (0, 5):
            row = C.get((kp, ki, fh, wind))
            if row is None or not row["phase_margin"] > 45:
                ok = False
                break
            if worst is None or row["settling_time"] > worst:
                worst, scen = row["settling_time"], {"wind": wind}
        if ok and (best is None or worst < best["score"]):
            best = {"status": "pass", "score": worst, "worst": scen, "local": {"filter_hz": fh}}
    return best or {"status": "fail"}


values = sorted({(r[0], r[1]) for r in a} | {(r[0], r[1]) for r in b} | {(r[0], r[1]) for r in c})
per = []
for kp, ki in values:
    ts = {"A": table_a(kp, ki), "B": table_b(kp, ki), "C": table_c(kp, ki)}
    per.append({"values": {"Kp": kp, "Ki": ki}, "feasible": all(t["status"] == "pass" for t in ts.values()), "tables": ts})
feas = [p for p in per if p["feasible"]]


def dominated(p, q):            # q dominates p (all scores minimised)
    sp = [p["tables"][t]["score"] for t in "ABC"]
    sq = [q["tables"][t]["score"] for t in "ABC"]
    return all(y <= x for x, y in zip(sp, sq)) and any(y < x for x, y in zip(sp, sq))


pareto = [p["values"] for p in feas if not any(dominated(p, q) for q in feas if q is not p)]
json.dump({"mode": "pareto", "values": per, "feasible": [p["values"] for p in feas], "pareto": pareto,
           "mapping": [{"table": "C", "column": "P_gain", "name": "Kp"}, {"table": "C", "column": "I_gain", "name": "Ki"}]},
          open(os.path.join(HERE, "expected.json"), "w"), indent=1)
print(len(feas), "feasible;", "pareto", pareto)
