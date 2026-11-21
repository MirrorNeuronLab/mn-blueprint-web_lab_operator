"""Run the MK3 sample in Isaac Sim and stream its observed state."""

import argparse
import io
import json
import os
import signal
import time
import traceback
from pathlib import Path
from threading import Event

from .dilution_scene import StageDilution
from .sample_run import SampleRun
from .workspace import CAMERAS, LiveFrames, Workspace


RESOLUTION = (896, 560)
FRAME_INTERVAL = 1 / 6


def render(app, stage_path, work, host, port, stopping):
    import numpy as np
    import omni.replicator.core as rep
    import omni.timeline
    import omni.usd
    from PIL import Image

    context = omni.usd.get_context()
    if not context.open_stage(str(stage_path)):
        raise RuntimeError("Isaac Sim couldn't open the Web Lab stage.")
    dilution = StageDilution(context.get_stage())
    run = SampleRun()
    dilution.apply(run.sample.observe())
    frames = LiveFrames()
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
                run.apply(*command)
            run.sample.advance(min(.2, tick - last_tick))
            observation = run.sample.observe()
            dilution.apply(observation)
            rep.orchestrator.step(rt_subframes=1, delta_time=0.0, pause_timeline=True)
            readings = dilution.observe()
            images = {}
            for camera, annotator in annotators.items():
                rgb = np.asarray(annotator.get_data())
                if rgb.ndim != 3 or rgb.shape[:2] != RESOLUTION[::-1] or rgb.shape[2] not in (3, 4):
                    raise RuntimeError(f"Isaac Sim returned no image from the {camera} camera.")
                with io.BytesIO() as output:
                    Image.fromarray(rgb[:, :, :3]).save(output, "JPEG", quality=80)
                    images[camera] = output.getvalue()
            frame += 1
            state = run.snapshot(frame, observation, readings)
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
