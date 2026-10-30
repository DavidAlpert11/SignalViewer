"""Columns to the page: numbers as Float32 (base64), text as codes into a list of labels."""
import base64
from typing import Dict

import numpy as np
import pandas as pd


def encode(values) -> Dict:
    s = values if isinstance(values, pd.Series) else pd.Series(values)
    if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
        a = s.to_numpy(dtype=np.float32, na_value=np.nan)
        return {"type": "num", "data": base64.b64encode(a.tobytes()).decode()}
    cat = pd.Categorical(s.astype("string") if not isinstance(s.dtype, pd.CategoricalDtype) else s.astype(str).where(s.notna()))
    codes = cat.codes.astype(np.float32)
    codes[codes < 0] = np.nan
    labels = [str(x) for x in cat.categories]
    try:                                                     # numbers kept as text: in number order
        order = np.argsort([float(x) for x in labels], kind="stable")
        remap = np.empty(len(labels), dtype=np.float32)
        remap[order] = np.arange(len(labels))
        codes = np.where(np.isnan(codes), np.nan, remap[np.nan_to_num(codes).astype(int)]).astype(np.float32)
        labels = [labels[i] for i in order]
    except ValueError:
        pass
    return {"type": "cat", "data": base64.b64encode(codes.tobytes()).decode(), "labels": labels}
