"""S2 (PLAN_2026-11-17 §2b, §2c): the table's own tools as steps of the study (the file never changes) -
fixed values, keep runs where a condition holds, display names and units - and the table exported as
edited (CSV, Parquet, Excel) with its recipe beside it."""
import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from svcore import sweep  # noqa: E402


def _grid():
    rows = [{"p": p, "wind": w, "out": 10 * p - w, "crashed": int(p == 3 and w == 10), "note": "x"}
            for w in (2.0, 6.0, 10.0) for p in (1.0, 2.0, 3.0)]
    return pd.DataFrame(rows)


Q = {"roles": {"p": "param", "wind": "hold", "out": "output", "crashed": "ignore", "note": "ignore"}}


def test_cells_and_row_filter_are_steps_not_changes_of_the_table():
    t = _grid()
    q = {**Q, "cells": [{"row": 0, "column": "out", "value": "99"}], "rowFilter": "crashed == 0"}
    p = sweep.prepare(t, q)
    assert len(p.df) == 8 and 99.0 in set(p.df["out"])
    assert t.loc[0, "out"] == 8.0                                  # the table as read
    with pytest.raises(sweep.QuestionError, match="not a number"):
        sweep.prepare(t, {**Q, "cells": [{"row": 0, "column": "out", "value": "abc"}]})
    with pytest.raises(sweep.QuestionError, match="Keep runs where"):
        sweep.prepare(t, {**Q, "rowFilter": "nope > 1"})
    with pytest.raises(sweep.QuestionError, match="gives text"):
        sweep.prepare(t, {**Q, "rowFilter": "note"})


def test_table_as_edited():
    q = {**Q, "removed": ["note"], "labels": {"out": "range"}, "units": {"out": "km"}, "exclude": [1],
         "derived": [{"name": "twice", "kind": "row", "expr": "out * 2"}], "rowFilter": "crashed == 0",
         "cells": [{"row": 0, "column": "out", "value": 50}]}
    df = sweep.table_as_edited(_grid(), q)
    assert list(df.columns) == ["p", "wind", "range [km]", "crashed", "twice"]
    assert len(df) == 7 and df["range [km]"].iloc[0] == 50 and df["twice"].iloc[0] == 100


@pytest.mark.parametrize("fmt", ["csv", "parquet", "xlsx"])
def test_export_as_edited_round_trip(tmp_path, fmt):
    from fastapi.testclient import TestClient
    from app.main import app
    f = tmp_path / "t.csv"
    _grid().to_csv(f, index=False)
    c = TestClient(app)
    tid = c.post("/api/sweep/open", json={"path": str(f)}).json()["id"]
    q = {**Q, "removed": ["note"], "rowFilter": "crashed == 0", "labels": {"out": "range"}}
    out = tmp_path / "edited"
    r = c.post("/api/sweep/export-table", json={"id": tid, "path": str(out), "format": fmt, "question": q,
                                                 "recipe": {"source": str(f), "question": q}})
    assert r.status_code == 200, r.text
    path = r.json()["path"]
    assert path.endswith("." + fmt) and r.json()["rows"] == 8
    back = {"csv": pd.read_csv, "parquet": pd.read_parquet, "xlsx": pd.read_excel}[fmt](path)
    assert list(back.columns) == ["p", "wind", "range", "crashed"] and len(back) == 8
    assert np.allclose(back["range"], 10 * back["p"] - back["wind"])
    assert json.load(open(path + ".recipe.json"))["question"]["rowFilter"] == "crashed == 0"
    # the table opens again in Sweeps
    assert c.post("/api/sweep/open", json={"path": path}).status_code == 200


def test_export_without_question_is_the_table_as_read(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    f = tmp_path / "t.csv"
    _grid().to_csv(f, index=False)
    c = TestClient(app)
    tid = c.post("/api/sweep/open", json={"path": str(f)}).json()["id"]
    r = c.post("/api/sweep/export-table", json={"id": tid, "path": str(tmp_path / "raw.csv")}).json()
    assert r["rows"] == 9 and not os.path.exists(r["path"] + ".recipe.json")
