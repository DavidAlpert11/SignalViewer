"""T17c: a plain 3D plot - any three signals as X, Y, Z (a trajectory in metres, three sensor
axes, a state space...). Nothing geographic: the map / 3D globe are for places on Earth.
Y and Z are aligned onto X's samples over the time all three share, then thinned to at most
`points` samples (every k-th one, the last kept) for drawing."""
from typing import Dict, Optional, Tuple

import numpy as np

from svcore.analysis import align_to

Series = Tuple[np.ndarray, np.ndarray]


def xyz_track(sx: Series, sy: Series, sz: Series, alignment: str = "linear", points: int = 20000) -> Optional[Dict]:
    """{t, x, y, z} on X's time base, or None when the three signals share no time."""
    tx = np.asarray(sx[0], dtype=np.float64)
    if not len(tx) or not len(sy[0]) or not len(sz[0]):
        return None
    t0 = max(float(tx[0]), float(sy[0][0]), float(sz[0][0]))
    t1 = min(float(tx[-1]), float(sy[0][-1]), float(sz[0][-1]))
    if t1 < t0:
        return None
    i0, i1 = np.searchsorted(tx, t0, "left"), np.searchsorted(tx, t1, "right")
    t = tx[i0:i1]
    x = np.asarray(sx[1], dtype=np.float64)[i0:i1]
    y = align_to(t, sy[0], sy[1], alignment)
    z = align_to(t, sz[0], sz[1], alignment)
    n = len(t)
    if n > points > 0:
        idx = np.unique(np.append(np.arange(0, n, int(np.ceil(n / points))), n - 1))
        t, x, y, z = t[idx], x[idx], y[idx], z[idx]
    return {"t": t, "x": x, "y": y, "z": z}
