"""Track the live sample and its applied workspace controls."""

from collections import deque
from datetime import datetime, timezone

from .dilution import DilutionSample


STATE_VERSION = "mn.web_lab.state.v2"


class CommandError(ValueError):
    pass


def command_from_message(message):
    if isinstance(message, dict) and message.keys() == {"action"} and message["action"] in (
        "stop_sample", "restart_sample",
    ):
        return message["action"]
    raise CommandError("Choose Stop sample or Run sample again.")


class SampleRun:
    def __init__(self):
        self.sample = DilutionSample()
        self.revision = 0
        self.events = deque(maxlen=12)

    def apply(self, revision, action):
        if action == "stop_sample":
            label = "Stopped dye dilution" if self.sample.stop() else "Dye dilution already complete"
        elif action == "restart_sample":
            self.sample.restart()
            label = "Restarted dye dilution"
        else:
            raise ValueError("Unknown sample control.")
        self.revision = revision
        self.events.appendleft({"id": revision, "label": label, "at": timestamp()})

    def snapshot(self, frame, observation, readings):
        return {
            "schema_version": STATE_VERSION,
            "status": "running",
            "frame": frame,
            "revision": self.revision,
            "observed_at": timestamp(),
            "sample": observation.snapshot(readings),
            "recent_actions": list(self.events),
        }


def timestamp():
    return datetime.now(timezone.utc).isoformat()
