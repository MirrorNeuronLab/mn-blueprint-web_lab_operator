# Web Lab Operator

Monitor and control a live, Andrew+-inspired workcell in NVIDIA Isaac Sim.
The co-worker keeps the workcell running while its window is closed. Open
**Web lab live** in OtterDesk to see the latest camera frames and operate the
simulated equipment.

## Start the workcell

Use a Linux execution computer with Docker, the NVIDIA Container Toolkit and
at least 48 GiB of NVIDIA GPU-accessible memory. Unified memory on DGX Spark
counts toward this requirement. The first start prepares the Isaac Sim 6.2
worker image and compiles shaders, which can take several minutes. Use a
MirrorNeuron SDK and worker installation matching
[`dependencies.json`](dependencies.json). Source-mode development can prepare
those dependencies from the matching local SDK and agent checkouts.

Hire or refresh **Web Lab Operator**, select **Live lab workcell**, and start
the co-worker on the NVIDIA execution computer. Open **Web lab live** after
both cameras are ready. To start from a local catalog checkout, run:

```sh
mn blueprint run ./web_lab_operator --detached --follow-seconds 0
```

Use **Overview** for the full bench and **Deck** for the overhead camera.
**Equipment** shows the positions observed in the USD stage after the current
render. Choose a joint and target to move the arm. Use **Hold motion** to keep
the current positions and **Home arm** to return the four arm joints to their
starting positions. The inspection station has a separate lid and the arm has
an inspection light. **Recent actions** shows the latest controls that Isaac Sim
applied. A motion stays **Moving** until the target is reached or held.

Pause or stop the co-worker to shut down the workspace and simulator. Resuming
opens a fresh session at the starting positions. The most recent equipment
observation is stored in the Job's run store and configured output folder as
`equipment_state.json`. The default output folder is
`~/Downloads/web-lab-operator`. Use its observation time and service status
when reviewing a saved state.

## OpenUSD assets

Open [web_lab.usda](payloads/isaac/assets/web_lab.usda) in Isaac Sim to inspect
the full bench. It references the reusable
[andrew_plus.usda](payloads/isaac/assets/andrew_plus.usda) component. Keep the
two files together when copying the scene.

The column, folding arm, dock and modular bench fixtures take visual cues from
Michael Raspuzzi's Andrew+ visualization. The USD geometry and control limits
are original and illustrative. The arm and lid are kinematic, and the deck
contains dry inspection props. [3D Lab Views](https://michaelraspuzzi.github.io/labautomationin3d/#andrew-plus)

The standard MirrorNeuron service blocks supervise Isaac Sim and authorize the
Job workspace through its Web UI proxy. The controls apply to the USD session
layer. The workspace shows camera pixels and equipment positions from that
same session.

## Validate

Run the focused service and placement checks from the catalog root using its
companion test environment:

```sh
python -m pytest tests/test_web_lab_operator.py tests/test_web_lab_operator_placement.py tests/test_mcp_web_lab_operator.py -q
```

On a running Isaac Sim job, pass its Web UI proxy URL to the Playwright smoke
test with an isolated validation session:

```sh
node tests/e2e/web-lab-operations.cjs <web-ui-proxy-url>
```
