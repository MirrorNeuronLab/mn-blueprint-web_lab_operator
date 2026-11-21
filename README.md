# Web Lab Operator

Watch the OLA MK3 box cell prepare and verify dye references in NVIDIA Isaac
Sim. Open **Web lab live** in OtterDesk to follow the sample. The workcell keeps
running when its window is closed.

## Start the workcell

Use a Linux execution computer with Docker, the NVIDIA Container Toolkit and
at least 48 GiB of NVIDIA GPU-accessible memory. Unified memory on DGX Spark
counts toward this requirement. The first start prepares the Isaac Sim 6.2
worker image and compiles shaders, which can take several minutes. Use a
MirrorNeuron SDK and worker installation matching
[`dependencies.json`](dependencies.json). Source-mode development can prepare
those dependencies from the matching local SDK and agent checkouts.

Hire or refresh **Web Lab Operator**, select **Dye dilution sample**, and start
it on the NVIDIA execution computer. Open **Web lab live** after both cameras
are ready. To start from a local catalog checkout, run:

```sh
mn blueprint run ./web_lab_operator --detached --follow-seconds 0
```

The sample starts with the cameras. The gantry moves the pipette as it draws,
dispenses and mixes dye with water. **Overview** shows the box cell. **Sample
tray** shows the labeled vessels, liquid stream and active check.

At the end the cell checks stock, three dilutions and a water blank against
100%, 50%, 25%, 12.5% and 0% of stock strength. It reads color and liquid
height from the USD stage after rendering. Each reference needs its expected
fill and a color reading within two percentage points of its target.

Use **Stop sample** to hold the current pose and results. **Run sample again**
resets the tray. Pause or stop the co-worker to shut down the simulator. Resume
to start a fresh sample. The latest observation and check results are saved as
`equipment_state.json` in the Job's run store and the configured output folder.
The default folder is `~/Downloads/web-lab-operator`.

## OpenUSD assets

[web_lab.usda](payloads/isaac/assets/web_lab.usda) opens the full cell. It
composes the [sample tray and gantry](payloads/isaac/assets/dilution_station.usda)
and [MK3 visual mesh](payloads/isaac/assets/vendor/mk3_cell.usdc) from
`ola_mk3_openusd_starter.zip`. The mesh is adapted and simplified for live
rendering. Keep the `assets` directory together when copying the scene.
[Asset provenance and licenses](payloads/isaac/assets/vendor/NOTICE.txt)

MirrorNeuron supervises Isaac Sim and serves the workspace through the Job Web
UI proxy. Sample updates apply to the USD session layer. Each streamed frame
carries the vessel readings from that session.

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
