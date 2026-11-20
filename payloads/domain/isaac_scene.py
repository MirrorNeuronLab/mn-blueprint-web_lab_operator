"""Apply manual controls to the OpenUSD workcell and render observed state."""

import argparse
import io
import json
import os
import signal
import time
import traceback
from pathlib import Path
from threading import Event

from .equipment import Equipment, Joint
from .workspace import CAMERAS, LiveFrames, Workspace


RESOLUTION = (896, 560)
FRAME_INTERVAL = 1 / 6
ARM = "/World/Equipment/Lift"
JOINTS = {
    "lift": ("Lift", ARM, "xformOp:translate", "mm", 1000),
    "shoulder": ("Shoulder", ARM + "/Shoulder", "xformOp:rotateZ", "°", 1),
    "elbow": ("Elbow", ARM + "/Shoulder/Elbow", "xformOp:rotateZ", "°", 1),
    "wrist": ("Wrist", ARM + "/Shoulder/Elbow/Wrist", "xformOp:rotateZ", "°", 1),
    "lid": ("Inspection lid", "/World/Equipment/InspectionStation/Lid", "xformOp:rotateX", "°", 1),
}
LIGHT = ARM + "/Shoulder/Elbow/Wrist/InspectionLight"


class StageEquipment:
    def __init__(self, stage):
        from pxr import UsdGeom

        if UsdGeom.GetStageUpAxis(stage) != UsdGeom.Tokens.z or UsdGeom.GetStageMetersPerUnit(stage) != 1:
            raise ValueError("The Web Lab stage must use meters and Z up.")
        stage.SetEditTarget(stage.GetSessionLayer())
        self.joints, self.ops = {}, {}
        for name, (label, path, attribute, unit, scale) in JOINTS.items():
            prim = stage.GetPrimAtPath(path)
            op = prim.GetAttribute(attribute)
            value = op.Get()
            home = value[2] if name == "lift" else value
            lower, upper, speed = (prim.GetAttribute(f"webLab:{key}").Get() * scale for key in ("min", "max", "speed"))
            self.ops[name] = op
            self.joints[name] = Joint(label, unit, lower, upper, home * scale, speed)
        self.light = stage.GetPrimAtPath(LIGHT).GetAttribute("inputs:intensity")
        self.lit_intensity = stage.GetPrimAtPath(LIGHT).GetAttribute("webLab:onIntensity").Get()
        self.commanded, self.light_on = self.observe()

    def apply(self, positions, light_on):
        from pxr import Gf

        for name, value in positions.items():
            if value == self.commanded[name]:
                continue
            op = self.ops[name]
            if name == "lift":
                before = op.Get()
                op.Set(Gf.Vec3d(before[0], before[1], value / JOINTS[name][-1]))
            else:
                op.Set(value)
            self.commanded[name] = value
        if light_on != self.light_on:
            self.light.Set(self.lit_intensity if light_on else 0)
            self.light_on = light_on

    def observe(self):
        values = {name: op.Get() for name, op in self.ops.items()}
        values["lift"] = values["lift"][2] * JOINTS["lift"][-1]
        return values, self.light.Get() > 0


def render(app, stage_path, work, host, port, stopping):
    import numpy as np
    import omni.replicator.core as rep
    import omni.timeline
    import omni.usd
    from PIL import Image

    context = omni.usd.get_context()
    if not context.open_stage(str(stage_path)):
        raise RuntimeError("Isaac Sim couldn't open the Web Lab stage.")
    rig = StageEquipment(context.get_stage())
    equipment = Equipment(rig.joints, light_on=rig.observe()[1])
    frames = LiveFrames(rig.joints)
    app.reset_render_settings()
    rep.orchestrator.set_capture_on_play(False)
    timeline = omni.timeline.get_timeline_interface()
    timeline.set_auto_update(False)
    timeline.play()
    timeline.commit()
    app.update()
    timeline.pause()
    timeline.set_current_time(0.0)

    workspace = Workspace(host, port, frames)
    products, annotators = {}, {}
    try:
        for camera, path in CAMERAS.items():
            products[camera] = rep.create.render_product(path, RESOLUTION)
            annotators[camera] = rep.AnnotatorRegistry.get_annotator("rgb")
            annotators[camera].attach(products[camera])
        for _ in range(48):
            if stopping.is_set():
                return
            app.update()
        for _ in range(4):
            rep.orchestrator.step(rt_subframes=2, delta_time=0.0, pause_timeline=True)

        frame = 0
        next_write = last_tick = time.monotonic()
        state_path = work / "state.json"
        temporary = work / "state.tmp"
        while not stopping.is_set() and app.is_running():
            tick = time.monotonic()
            workspace.check()
            command = frames.command()
            if command:
                equipment.apply(*command)
            equipment.advance(min(.2, tick - last_tick))
            rig.apply(equipment.position, equipment.light_on)
            rep.orchestrator.step(rt_subframes=1, delta_time=0.0, pause_timeline=True)
            observed, light_on = rig.observe()
            images = {}
            for camera, annotator in annotators.items():
                rgb = np.asarray(annotator.get_data())
                if rgb.ndim != 3 or rgb.shape[:2] != RESOLUTION[::-1] or rgb.shape[2] not in (3, 4):
                    raise RuntimeError(f"Isaac Sim returned no image from the {camera} camera.")
                with io.BytesIO() as output:
                    Image.fromarray(rgb[:, :, :3]).save(output, "JPEG", quality=80)
                    images[camera] = output.getvalue()
            frame += 1
            state = equipment.snapshot(frame, observed, light_on)
            frames.publish(state, images)
            if tick >= next_write or command:
                temporary.write_text(json.dumps({"port": workspace.port, "state": state}, allow_nan=False), encoding="utf-8")
                temporary.replace(state_path)
                next_write = tick + 1
            last_tick = tick
            stopping.wait(max(0, FRAME_INTERVAL - (time.monotonic() - tick)))
        if not stopping.is_set():
            raise RuntimeError("The Isaac Sim application stopped.")
    finally:
        workspace.close()
        for camera, product in products.items():
            if camera in annotators:
                annotators[camera].detach(product)
            product.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", type=Path)
    parser.add_argument("work", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    options = parser.parse_args()

    stopping = Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    (options.work / "simulator.pid").write_text(str(os.getpid()), encoding="ascii")

    from isaacsim import SimulationApp

    width, height = RESOLUTION
    app = SimulationApp({
        "headless": True,
        "renderer": "RealTimePathTracing",
        "width": width,
        "height": height,
        "disable_viewport_updates": True,
        "extra_args": ["--allow-root"],
    })
    exit_code = 0
    try:
        render(app, options.stage, options.work, options.host, options.port, stopping)
    except Exception:
        traceback.print_exc()
        exit_code = 1
    finally:
        app.close(exit_code=exit_code)


if __name__ == "__main__":
    main()
