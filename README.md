# Web Lab Operator

Watch a food-dye dilution and control an Andrew+-inspired inspection bench in
NVIDIA Isaac Sim. Open **Web lab live** in OtterDesk to follow the sample and
view the equipment. The workcell keeps running when its window is closed.

## Start the workcell

Use a Linux execution computer with Docker, the NVIDIA Container Toolkit and
at least 48 GiB of NVIDIA GPU-accessible memory. Unified memory on DGX Spark
counts toward this requirement. The first start prepares the Isaac Sim 6.2
worker image and compiles shaders, which can take several minutes. Use a
MirrorNeuron SDK and worker installation matching
[`dependencies.json`](dependencies.json). Source-mode development can prepare
those dependencies from the matching local SDK and agent checkouts.

Hire or refresh **Web Lab Operator**, select **Dye dilution sample**, and start
the co-worker on the NVIDIA execution computer. Open **Web lab live** after
both cameras are ready. To start from a local catalog checkout, run:

```sh
mn blueprint run ./web_lab_operator --detached --follow-seconds 0
```

The sample starts when the cameras begin streaming. The pipette draws from
each mixed vessel, moves to the next vessel and dispenses into water. The panel
reports the applied transfers and relative dye concentration. At completion,
the four vessels show stock, 50%, 25% and 12.5% with a visible color gradient.
Use **Stop sample** to keep the current result or **Run sample again** to reset
the dye and water and replay the sequence. The sample updates USD transforms,
liquid height and color from a deterministic mixing model.

Use **Overview** for the full workcell and **Deck** for the overhead camera.
**Equipment** shows the positions observed in the USD stage after the current
render. Choose a joint and target to move the arm. Use **Hold motion** to keep
the current positions and **Home arm** to return the four arm joints to their
starting positions. The inspection station has a separate lid and the arm has
an inspection light. **Recent actions** shows the latest controls that Isaac Sim
applied. A motion stays **Moving** until the target is reached or held.

Pause or stop the co-worker to shut down the workspace and simulator. Resuming
opens a fresh session and starts the sample again. The latest equipment and
dilution observation is stored in the Job's run store and configured output folder as
`equipment_state.json`. The default output folder is
`~/Downloads/web-lab-operator`. Use its observation time and service status
when reviewing a saved state.

## OpenUSD assets

Open [web_lab.usda](payloads/isaac/assets/web_lab.usda) in Isaac Sim to inspect
the workcell. It composes the
[inspection bench](payloads/isaac/assets/andrew_plus.usda),
[dilution station](payloads/isaac/assets/dilution_station.usda) and local vendor
meshes. Keep the `assets` directory together when copying the scene. The frame
comes from the Open Lab Automata MK3 structural CAD, and the flask comes from
the QUIKTECH SimReady catalog. See the [asset notices](payloads/isaac/assets/vendor/NOTICE.txt).

The column, folding arm, dock and modular bench fixtures take visual cues from
Michael Raspuzzi's Andrew+ visualization. The USD geometry and control limits
are original and illustrative. The kinematic arm and lid sit on the dry
inspection bench. [3D Lab Views](https://michaelraspuzzi.github.io/labautomationin3d/#andrew-plus)

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
