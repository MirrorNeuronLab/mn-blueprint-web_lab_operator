"""Supervise the Isaac Sim process and publish the live Job workspace."""

import ctypes
import json
import os
import signal
import socket
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from mn_sdk.blueprint.hooks import report_activity
from mn_sdk.blueprint.services import claim_service_web_ui
from mn_sdk_common.beacon import mark_agent_progress
from mn_sdk_common.files import atomic_write_json
from mn_sdk_web_ui import resolve_web_ui_binding


PAYLOAD = Path(__file__).resolve().parents[1]
STAGE = PAYLOAD / "isaac" / "assets" / "web_lab.usda"
STAGE_LAYERS = (
    "web_lab.usda", "andrew_plus.usda", "dilution_station.usda",
    "vendor/mk3_frame.usdc", "vendor/erlenmeyer_flask.usdc",
)
ISAAC_PYTHON = Path("/isaac-sim/python.sh")
STATE_PATH = "equipment_state.json"
FRAME_TIMEOUT = 12


def check_workcell(_block, _inputs):
    if not ISAAC_PYTHON.is_file() or not all(
        (STAGE.parent / name).is_file() for name in STAGE_LAYERS
    ):
        raise RuntimeError("The OpenUSD workcell or Isaac Sim runtime is missing.")
    try:
        cuda = ctypes.CDLL("libcuda.so.1")
        count = ctypes.c_int()
        available = cuda.cuInit(0) == 0 and cuda.cuDeviceGetCount(ctypes.byref(count)) == 0 and count.value > 0
    except OSError as error:
        raise RuntimeError("Isaac Sim needs access to an NVIDIA GPU through Docker.") from error
    if not available:
        raise RuntimeError("Isaac Sim needs access to an NVIDIA GPU through Docker.")
    return {}


def stop_process(process, work):
    # Let the launcher reap Kit after a graceful shutdown. The process group
    # also covers a launch that failed before the interpreter wrote its PID.
    try:
        simulator_pid = int((work / "simulator.pid").read_text())
        if os.getpgid(simulator_pid) == process.pid:
            os.kill(simulator_pid, signal.SIGTERM)
            process.wait(timeout=6)
            return
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=3)


class LabSession:
    def __init__(self, block):
        self.block = block
        self.binding = resolve_web_ui_binding(block.config, environment=block.environment)
        self.locations = dict.fromkeys((block.store.path(STATE_PATH), block.output_directory / STATE_PATH))
        self.state = {
            "schema_version": "mn.web_lab.state.v1", "status": "starting",
            "frame": 0, "revision": 0, "observed_at": None, "motion": None,
            "joints": {}, "inspection_light": None, "sample": None, "recent_actions": [],
        }
        self.work = None
        self.process = None
        self.last_frame_at = None
        self.last_revision = 0
        self.last_published = 0
        self.last_sample_status = None
        self.claimed = False
        self.failed = False
        self.startup_deadline = getattr(block, "deadline", None)

    def start(self):
        self.publish()
        self.temporary = TemporaryDirectory(prefix="web-lab-live-")
        self.work = Path(self.temporary.name)
        self.log = self.work / "isaac.log"
        # Isaac loads its bundled Python and libraries. Keep the SDK environment
        # out of the renderer process.
        environment = {
            key: value for key, value in os.environ.items()
            if not key.startswith("MN_") and key not in {
                "LD_LIBRARY_PATH", "LD_PRELOAD", "PYTHONPATH", "PYTHONHOME", "BASH_ENV",
            }
        }
        environment["PYTHONPATH"] = "/opt/web-lab-deps"
        with self.log.open("wb") as output:
            self.process = subprocess.Popen(
                [str(ISAAC_PYTHON), "--no-ros-env", "-m", "domain.isaac_scene",
                 str(STAGE), str(self.work), "--host", self.binding.host, "--port", str(self.binding.port)],
                cwd=PAYLOAD, env=environment, stdout=output, stderr=subprocess.STDOUT,
                start_new_session=True,
            )

    def collect(self):
        try:
            receipt = json.loads((self.work / "state.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        state = receipt["state"]
        if state["frame"] > self.state["frame"]:
            self.state = state
            self.last_frame_at = time.monotonic()
        return receipt["port"]

    def check(self):
        exit_code = self.process.poll()
        if exit_code is not None:
            self.failed = True
            with self.log.open("rb") as output:
                output.seek(max(0, os.fstat(output.fileno()).st_size - 4000))
                tail = output.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Isaac Sim exited ({exit_code}).\n{tail}")
        try:
            port = self.collect()
            if self.last_frame_at is not None and time.monotonic() - self.last_frame_at > FRAME_TIMEOUT:
                raise RuntimeError("Isaac Sim stopped sending live camera frames.")
        except Exception:
            self.failed = True
            raise
        return port

    def claim(self, port):
        environment = self.block.environment or {}
        if environment.get("MN_DOCKER_WORKER_NETWORK_MODE") == "runtime" and not (
            environment.get("MN_BLUEPRINT_WEB_UI_BASE_URL") or environment.get("MN_WEB_UI_PROXY_HOST")
        ):
            worker = environment["MN_DOCKER_WORKER_CONTAINER_NAME"]
            environment = {**environment, "MN_WEB_UI_PROXY_HOST": socket.gethostbyname(worker)}
        claim_service_web_ui(
            self.block, title="Web lab live", service_name="web-lab-live", node_id=self.block.agent_id,
            url=self.binding.advertised_url(port, environment=environment),
            http_ports=[port], websocket_ports=[port],
        )
        self.claimed = True

    def publish(self):
        for location in self.locations:
            atomic_write_json(location, self.state, mode=0o644)

    def record(self):
        self.publish()
        if self.state["frame"] != self.last_published:
            mark_agent_progress()
            self.last_published = self.state["frame"]
        for event in reversed(self.state["recent_actions"]):
            if event["id"] > self.last_revision:
                report_activity(event["label"], kind="action")
                self.last_revision = event["id"]
        sample = self.state["sample"]
        if sample and sample["status"] != self.last_sample_status:
            if sample["status"] == "complete":
                report_activity("Finished the dye dilution sample", kind="result")
            self.last_sample_status = sample["status"]
        return {"frame": self.state["frame"]}

    def close(self):
        try:
            if self.work is not None:
                self.collect()
            if not self.claimed and self.startup_deadline is not None and time.monotonic() >= self.startup_deadline:
                self.failed = True
            # Preserve the last observation before waiting for Kit to shut down.
            self.state["status"] = "failed" if self.failed else "stopped"
            self.publish()
        finally:
            try:
                if self.process is not None:
                    stop_process(self.process, self.work)
            finally:
                if self.work is not None:
                    self.temporary.cleanup()


def start(block, _inputs):
    lab = LabSession(block)
    block.resources["lab"] = lab
    report_activity("Starting the OpenUSD workcell in Isaac Sim", kind="action")
    try:
        lab.start()
    except Exception:
        lab.failed = True
        raise


def ready(block, _inputs):
    lab = block.resources["lab"]
    try:
        port = lab.check()
        if port is None:
            return False
        if not lab.claimed:
            lab.claim(port)
            report_activity("The workcell cameras are live", kind="result")
        return True
    except Exception:
        lab.failed = True
        raise


def health(block, _inputs):
    block.resources["lab"].check()
    return True


def cycle(block, _inputs):
    return block.resources["lab"].record()


def stop(block, _inputs):
    lab = block.resources.pop("lab", None)
    if lab:
        lab.close()
