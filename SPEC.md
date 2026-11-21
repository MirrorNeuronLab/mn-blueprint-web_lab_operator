# Web Lab Operator specification

## Outcome

The co-worker opens one bundled OLA MK3 box cell per Isaac Sim service attempt.
It renders overview and sample tray cameras. The food-dye sample starts when
both cameras stream. The gantry and liquid geometry are kinematic, and the
color and fill readings describe the simulated USD scene.

## Runtime and lifecycle

- Use the catalog's NVIDIA CUDA placement contract on Linux. The worker runs
  Isaac Sim 6.2 with the declared Docker image and the Job's GPU allocation.
- Start under the stock monitored-service block. Publish the workspace claim
  after both cameras produce images. Use the standard Job Web UI proxy for
  static assets and the bounded bidirectional WebSocket.
- A failed process or stale render stream fails the service. Pause or stop
  retires the claim and ends the owned child process. A replacement or resumed
  attempt starts at the authored pose with a fresh sample and command session.
- Publish the last observed state to `equipment_state.json` while running and
  on shutdown. The `mn.web_lab.state.v2` artifact contains service status,
  observation time, the current sample and up to 12 applied control receipts.

## Sample and checks

- Start with stock food dye, three receiving vessels with water and a separate
  water blank. The pipette visits three successive source and destination pairs.
  Each transfer updates the gantry pose, liquid level and color. The sample
  tray labels and stream show the vessel and current action.
- Check the five vessels at the end of the transfers. The read marker selects
  the vessel being checked. Read the liquid cylinder heights and USD material
  colors after rendering. Compare their derived dye strengths with 100%, 50%,
  25%, 12.5% and 0%. A vessel passes when its fill is within 0.05 simulated
  units of its target and its color reading is within two percentage points.
- Show observed and expected dye strength and each vessel's check result beside
  the matching camera frame. The sample reports **Needs review** if a reading
  misses either check. Its saved observation includes the fill readings and the
  reason for each mismatch.

## Workspace controls

- **Stop sample** holds the pose and liquid state. **Run sample again** restores
  the starting pose and mixture. Admit one control at a time using the current
  workspace session and revision. Report acceptance separately from the applied
  receipt in a rendered observation.
- Switching camera views changes the selected viewer's camera. If disconnected,
  disable controls, reconnect and show the current observation. Command admission
  and rendering continue while the workspace is closed.
