# Web Lab Operator user manual

Start **Live lab workcell** on a Linux execution computer with Docker, the
NVIDIA Container Toolkit and at least 48 GiB of NVIDIA GPU-accessible memory.
The included workcell runs in Isaac Sim on DGX Spark.

Open **Web lab live** when the co-worker reports that the cameras are ready.
Use **Overview** to see the bench and **Deck** for the overhead view. Equipment
readings come from the current simulated frame.

Choose a joint, enter a target and select **Move joint**. **Hold motion** keeps
the current position and clears pending movement targets. **Home arm** returns
the arm joints to their starting positions. Operate the inspection lid and
light with their own controls. Recent actions show controls that were applied.
All controls are scoped to the simulated workcell.

Pause or stop the co-worker to shut down the simulator. Resume to start the
workcell at its initial pose. Open `equipment_state.json` in the configured
output folder to review the last observed positions, light and action history
with their observation time.
