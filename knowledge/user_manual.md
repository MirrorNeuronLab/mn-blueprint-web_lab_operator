# Web Lab Operator user manual

Start **Dye dilution sample** on a Linux execution computer with Docker, the
NVIDIA Container Toolkit and at least 48 GiB of NVIDIA GPU-accessible memory.
The included workcell runs in Isaac Sim on DGX Spark.

Open **Web lab live** when the co-worker reports that the cameras are ready.
Use **Overview** to see the MK3 box cell or **Sample tray** to follow the pipette
and read the vessel labels.

The sample prepares three dilutions and checks their simulated color and fill
alongside the stock dye and water blank. The table shows the target and observed
dye strength relative to stock. A check marked **Review** means the color or
fill differs from its target.

Use **Stop sample** to keep the current pose and readings. **Run sample again**
restores the initial tray and starts again. Pause or stop the co-worker to shut
down Isaac Sim. Resume to start a fresh sample. The configured output folder
contains the latest observation and checks in `equipment_state.json`.
