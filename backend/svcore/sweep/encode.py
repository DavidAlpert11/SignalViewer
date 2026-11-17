"""Columns to the page: numbers as Float32 (base64), text as codes into a list of labels."""
import base64
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


def labels_of(s: pd.Series) -> pd.Series:
    """A text column's values as the page's labels (what a category filter names); NA stays NA."""
    if isinstance(s.dtype, pd.CategoricalDtype):
        return s.astype(str).where(s.notna())
    return s.astype("string")


def category_labels(s: pd.Series) -> List[str]:
    """A text column's labels in the page's order: numbers kept as text in number order, else sorted."""
    labels = [str(x) for x in pd.Categorical(labels_of(s)).categories]
    try:
        return [labels[i] for i in np.argsort([float(x) for x in labels], kind="stable")]
    except ValueError:
        return labels


def encode(values, whole: Optional[pd.Series] = None, labels: Optional[List[str]] = None) -> Dict:
    """`whole`: the full column when `values` are some of its rows (a sample) - a text column's codes then
    come from every value of it, so a code means the same label whichever rows were sent. `labels`: those
    labels already worked out (category_labels of the whole column, kept by the caller)."""
    s = values if isinstance(values, pd.Series) else pd.Series(values)
    if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
        a = s.to_numpy(dtype=np.float32, na_value=np.nan)
        return {"type": "num", "data": base64.b64encode(a.tobytes()).decode()}
    if labels is None:
        labels = category_labels(whole if whole is not None else s)
    codes = pd.Categorical(labels_of(s), categories=labels).codes.astype(np.float32)
    codes[codes < 0] = np.nan
    return {"type": "cat", "data": base64.b64encode(codes.tobytes()).decode(), "labels": labels}
