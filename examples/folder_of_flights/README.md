# A folder of recordings

Ten ArduPilot flight logs of two quad-copters over six weeks (made by `tools/make_folder_example.py`), with the
measures to take of each in `measures.json`: the highest vibration (`VIBE[0].VibeZ`) and the lowest battery voltage
(`BAT[0].Volt`), and the vehicle and date read from each file's name (`{vehicle}_{date}`).

In the app: the welcome card **A folder of recordings**, or *Sweeps ▸ Data ▸ From a folder of recordings…* and
choose this folder. Each flight becomes one row in Sweeps; tick rows and *Open in Recordings* opens them together.
From the command line: `signalviewer-cli summarize examples/folder_of_flights --measures examples/folder_of_flights/measures.json --out table.csv`.

- **X8-A** – a motor bearing wearing out: the vibration grows flight after flight (18 → 29 m/s/s) until the flight
  of 7 Oct (67 m/s/s, with clipping).
- **X8-B** – healthy, but the flight of 19 Sep has a stretch of poor GPS (5 satellites, HDOP 3.2) and the flight of
  17 Oct sagged under the battery's low-voltage limit (a worn pack: 13.6 V).
