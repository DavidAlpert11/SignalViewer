# The Fleet example

Ten ArduPilot flight logs of two quad-copters over six weeks (made by `tools/make_fleet_example.py`).
In the app: rail ▸ **Fleet** ▸ *Try the example fleet* (or *Add a folder…* and choose this folder).

- **X8-A** – a motor bearing wearing out: the vibration grows flight after flight (18 → 29 m/s/s)
  until the flight of 7 Oct crosses the limit (67 m/s/s, with clipping). Choose the number
  *Vibration · max* to see the trend; type `X8-A` to see this copter alone; *Open here* opens the
  flight at the moment of the finding.
- **X8-B** – healthy, but the flight of 19 Sep has a stretch of poor GPS (5 satellites, HDOP 3.2)
  and the flight of 17 Oct sagged under the battery's low-voltage limit (a worn pack). Choose the
  level *Warning or error* to list them.
