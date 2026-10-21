# Simulation against flight

The same attitude test (roll and pitch doublets in ALT_HOLD) flown in a model and on the vehicle.
Written by `tools/make_sim_vs_flight.py`; walked through in [docs/sim-vs-flight.md](../../docs/sim-vs-flight.md).

```bash
signalviewer-cli compare sim_attitude_doublets.mat flight_attitude_doublets.bin \
    --align auto --align-on ATT.DesRoll --tolerances tolerances.json
```
