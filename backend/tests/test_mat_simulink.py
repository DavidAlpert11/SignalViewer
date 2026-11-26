"""CC14: Simulink's Structure with time is named as the model names it; MATLAB objects are said, not dropped."""
import numpy as np
import scipy.io as sio

from svcore.mat_loader import load_mat


def test_structure_with_time_named_by_its_label(tmp_path):
    t1, t2 = np.linspace(0, 10, 1001), np.linspace(0, 10, 101)
    p = tmp_path / "sim.mat"
    sio.savemat(p, {"ctrl": {"time": t1, "signals": {"values": np.sin(t1), "label": "u"}},
                    "plant": {"time": t2, "signals": {"values": np.c_[np.cos(t2), np.sin(t2)], "label": "pos",
                                                       "blockName": "model/Plant"}},
                    "scope": {"time": t2, "signals": {"values": t2, "blockName": "model/Scope 1"}},
                    "tout": t1})
    run, skipped = load_mat(str(p), "sim.mat")
    names = set(run.signals)
    assert {"ctrl.u", "plant.pos[1]", "plant.pos[2]", "scope.Scope_1"} <= names, names
    assert len(run.signals["plant.pos[1]"].time) == 101 and len(run.signals["ctrl.u"].time) == 1001   # own rates
    assert not any(".signals." in n for n in names)
