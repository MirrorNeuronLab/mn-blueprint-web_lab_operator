# Web Lab Operator specification

## Outcome

The co-worker owns one live Isaac Sim workcell per running service attempt.
It opens the bundled, self-contained OpenUSD bench and continually renders
overview and deck cameras. The operator can move four arm joints, hold motion,
return the arm to its starting positions, move an inspection-station lid,
and switch an inspection light. The workcell uses inert props and kinematic
transforms scoped to the simulated stage.

## Runtime and lifecycle

- Use the catalog's NVIDIA CUDA placement contract on Linux. The worker runs
  Isaac Sim 6.2 with the declared Docker image and the Job's GPU allocation.
- Start under the stock monitored-service block. Publish the workspace claim
  after both cameras produce images. Use the standard Job Web UI proxy for
  static assets and the bounded bidirectional WebSocket.
- Supervise the process and rendered heartbeat. A failed process or stale
  render stream fails the service. Pause or stop retires the claim and ends
  the owned child process. A replacement or resumed attempt starts at the
  authored pose with a fresh command session.
- Publish the last observed state to `equipment_state.json` while running and
  on shutdown. Include service status, observation time, observed positions
  and current targets, light state and up to 12 applied command receipts.
  The position and activity fields qualify the last observation on shutdown.

## Interaction and state

- Keep the arm and inspection lid's motion limits, starting positions and
  rates in the USD asset. Validate the selected control server-side. Motion
  advances toward the latest admitted target in bounded increments.
- Read the simulated transforms and light state back from USD after rendering.
  Send observations and a corresponding camera frame together. Switching
  views changes only the selected viewer's camera.
- Admit one manual command at a time. A current workspace session and state
  revision are required. Report acceptance separately from an applied control
  observation. On disconnect, the window disables controls, reconnects and
  displays current state. An interrupted command is resolved from observed
  state and recent actions.
- Hold captures the currently rendered pose and clears active targets. A fresh
  move or home command can start motion again. Home only targets the four arm
  joints. Command admission and rendering continue while the workspace is closed.
