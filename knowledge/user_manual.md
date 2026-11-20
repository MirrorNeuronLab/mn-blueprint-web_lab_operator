# Web Lab Operator user manual

Start **Dye dilution sample** on a Linux execution computer with Docker, the
NVIDIA Container Toolkit and at least 48 GiB of NVIDIA GPU-accessible memory.
The included workcell runs in Isaac Sim on DGX Spark.

Open **Web lab live** when the co-worker reports that the cameras are ready.
Use **Overview** to see the bench and **Deck** for the overhead view. Equipment
readings come from the current simulated frame.

The dye dilution runs automatically. Watch the pipette draw and dispense as
food dye is mixed with water. Compare the stock dye with three lower
concentrations of 50%, 25% and 12.5%. Use **Stop sample** to keep the current
state and **Run sample again** to replay from the beginning.

Choose a joint, enter a target and select **Move joint**. **Hold motion** keeps
the current position and clears pending movement targets. **Home arm** returns
the arm joints to their starting positions. Operate the inspection lid and
light with their own controls. Recent actions show controls that were applied.
All controls are scoped to the simulated workcell.

Pause or stop the co-worker to shut down the simulator. Resume to start a fresh
sample. Open `equipment_state.json` in the configured output folder to review
the last dye concentrations, observed positions, light and action history with
their observation time.
