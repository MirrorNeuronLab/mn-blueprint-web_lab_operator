"""State and manual commands for the simulated workcell."""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite


@dataclass(frozen=True)
class Joint:
    label: str
    unit: str
    minimum: float
    maximum: float
    home: float
    speed: float

    def __post_init__(self):
        values = (self.minimum, self.maximum, self.home, self.speed)
        if not all(map(isfinite, values)) or not (
            self.minimum <= self.home <= self.maximum and self.minimum < self.maximum and self.speed > 0
        ):
            raise ValueError(f"Invalid USD joint limits for {self.label}.")


class CommandError(ValueError):
    pass


def command_from_message(message, joints):
    if not isinstance(message, dict):
        raise CommandError("Choose a workcell control.")
    action = message.get("action")
    keys = set(message)
    if action == "move" and keys == {"action", "joint", "target"}:
        name, target = message["joint"], message["target"]
        joint = joints.get(name) if isinstance(name, str) else None
        if joint is None or name == "lid":
            raise CommandError("Choose an arm joint.")
        if type(target) not in (int, float) or not joint.minimum <= target <= joint.maximum:
            raise CommandError(f"Set {joint.label.lower()} between {joint.minimum:g} and {joint.maximum:g}.")
        return {"action": action, "joint": name, "target": float(target)}
    if action in ("lid", "light") and keys == {"action", "enabled"} and type(message["enabled"]) is bool:
        return message
    if action in ("home", "hold") and keys == {"action"}:
        return message
    raise CommandError("Choose a workcell control.")


class Equipment:
    """Integrate toward the latest operator targets on the Isaac Sim thread."""

    def __init__(self, joints, light_on=False):
        self.joints = joints
        self.position = {name: joint.home for name, joint in joints.items()}
        self.target = self.position.copy()
        self.light_on = light_on
        self.held = False
        self.revision = 0
        self.events = deque(maxlen=12)

    def apply(self, revision, command):
        action = command["action"]
        if action == "hold":
            self.target = self.position.copy()
            self.held = True
            label = "Held motion"
        elif action == "home":
            self.target.update({name: joint.home for name, joint in self.joints.items() if name != "lid"})
            self.held = False
            label = "Set arm to home"
        elif action == "move":
            name, target = command["joint"], command["target"]
            self.target[name] = target
            self.held = False
            joint = self.joints[name]
            label = f"Set {joint.label.lower()} target to {target:g} {joint.unit}"
        elif action == "lid":
            joint = self.joints["lid"]
            self.target["lid"] = joint.minimum if command["enabled"] else joint.home
            self.held = False
            label = "Set lid to open" if command["enabled"] else "Set lid to close"
        elif action == "light":
            self.light_on = command["enabled"]
            label = "Turned inspection light on" if self.light_on else "Turned inspection light off"
        else:
            raise ValueError("Invalid workcell command.")
        self.revision = revision
        self.events.appendleft({"id": revision, "label": label, "at": timestamp()})

    def advance(self, dt):
        for name, joint in self.joints.items():
            current, target = self.position[name], self.target[name]
            distance = joint.speed * dt
            self.position[name] = min(current + distance, max(current - distance, target))

    def snapshot(self, frame, observed, light_on):
        axes = {
            name: {
                "label": joint.label, "unit": joint.unit,
                "min": joint.minimum, "max": joint.maximum, "home": joint.home,
                "value": round(observed[name], 2), "target": round(self.target[name], 2),
            }
            for name, joint in self.joints.items()
        }
        moving = any(axis["value"] != axis["target"] for axis in axes.values())
        return {
            "schema_version": "mn.web_lab.state.v1",
            "status": "running",
            "frame": frame,
            "revision": self.revision,
            "observed_at": timestamp(),
            "motion": "held" if self.held else "moving" if moving else "ready",
            "joints": axes,
            "inspection_light": light_on,
            "recent_actions": list(self.events),
        }


def timestamp():
    return datetime.now(timezone.utc).isoformat()
