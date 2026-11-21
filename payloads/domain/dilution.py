"""One fixed food-dye dilution in the simulated workcell."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Well:
    prim: str
    label: str
    target_percent: float


WELLS = (
    Well("Stock", "Stock", 100),
    Well("Half", "1:2", 50),
    Well("Quarter", "1:4", 25),
    Well("Eighth", "1:8", 12.5),
    Well("Blank", "Blank", 0),
)
TOTAL_TRANSFERS = 3
COLOR_TOLERANCE_PP = 2
FILL_TOLERANCE = .05


@dataclass(frozen=True)
class Mixture:
    volume: float
    dye: float

    @property
    def concentration(self):
        return self.dye / self.volume if self.volume else 0.0

    def blend(self, target, fraction):
        return Mixture(
            self.volume + (target.volume - self.volume) * fraction,
            self.dye + (target.dye - self.dye) * fraction,
        )


EMPTY = Mixture(0, 0)
WATER = Mixture(1, 0)


@dataclass(frozen=True)
class Pose:
    well: float
    height: float
    mixtures: tuple[Mixture, ...]
    tip: Mixture = EMPTY

    def blend(self, target, fraction):
        return Pose(
            self.well + (target.well - self.well) * fraction,
            self.height + (target.height - self.height) * fraction,
            tuple(start.blend(end, fraction) for start, end in zip(self.mixtures, target.mixtures)),
            self.tip.blend(target.tip, fraction),
        )


@dataclass(frozen=True)
class Step:
    label: str
    seconds: float
    pose: Pose
    transfers: int
    phase: str = "transferring"
    flow: bool = False
    checked: int = 0
    reading_index: int | None = None


START = Pose(0, 1, (Mixture(2, 2), WATER, WATER, WATER, WATER))


def dilution_steps():
    mixtures = START.mixtures
    yield Step("Preparing the stock dye and water blank", 2.0, START, 0, phase="preparing")
    for source_index in range(TOTAL_TRANSFERS):
        target_index = source_index + 1
        source_name, target_name = WELLS[source_index].label, WELLS[target_index].label
        yield Step(f"Lowering over {source_name}", .8, Pose(source_index, 0, mixtures), source_index)

        source = mixtures[source_index]
        draw = Mixture(1, source.concentration)
        remaining = Mixture(source.volume - draw.volume, source.dye - draw.dye)
        mixtures = mixtures[:source_index] + (remaining,) + mixtures[target_index:]
        yield Step(f"Drawing from {source_name}", 1.2, Pose(source_index, 0, mixtures, draw), source_index)
        yield Step(f"Lifting from {source_name}", .8, Pose(source_index, 1, mixtures, draw), source_index)
        yield Step(f"Moving to {target_name}", 1.2, Pose(target_index, 1, mixtures, draw), source_index)
        yield Step(f"Lowering over {target_name}", .8, Pose(target_index, .56, mixtures, draw), source_index)

        target = mixtures[target_index]
        mixed = Mixture(target.volume + draw.volume, target.dye + draw.dye)
        mixtures = mixtures[:target_index] + (mixed,) + mixtures[target_index + 1:]
        yield Step(f"Dispensing into {target_name}", 1.4, Pose(target_index, .56, mixtures), source_index, flow=True)
        yield Step(f"Mixing {target_name}", .65, Pose(target_index, .14, mixtures), source_index)
        yield Step(f"Lifting from {target_name}", .8, Pose(target_index, 1, mixtures), target_index)
    for index, well in enumerate(WELLS):
        pose = Pose(index, 1, mixtures)
        yield Step(f"Moving above {well.label}", .9, pose, TOTAL_TRANSFERS, phase="checking", checked=index)
        yield Step(f"Checking {well.label}", 1.25, pose, TOTAL_TRANSFERS, phase="checking",
                   checked=index + 1, reading_index=index)
    yield Step("Parking the pipette", 1.1, Pose(1.5, 1, mixtures), TOTAL_TRANSFERS,
               phase="checking", checked=len(WELLS))


STEPS = tuple(dilution_steps())


@dataclass(frozen=True)
class Observation:
    status: str
    action: str
    transfers: int
    pose: Pose
    phase: str
    flow: bool = False
    checked: int = 0
    reading_index: int | None = None

    def snapshot(self, readings):
        wells = []
        for index, (well, reading, final) in enumerate(zip(WELLS, readings, STEPS[-1].pose.mixtures, strict=True)):
            percent = 100 * reading.concentration
            fill_matches = abs(reading.volume - final.volume) <= FILL_TOLERANCE
            color_matches = abs(percent - well.target_percent) <= COLOR_TOLERANCE_PP
            issues = []
            if index < self.checked:
                if not color_matches:
                    issues.append("Color differs from target")
                if not fill_matches:
                    issues.append("Fill differs from target")
            wells.append({
                "name": well.label,
                "concentration_percent": round(percent, 2),
                "target_percent": well.target_percent,
                "fill_units": round(reading.volume, 3),
                "target_fill_units": final.volume,
                "check": ("needs_review" if issues else "passed") if index < self.checked else "pending",
                "issues": issues,
            })
        check_status = "pending"
        if self.checked == len(WELLS):
            check_status = "passed" if all(well["check"] == "passed" for well in wells) else "needs_review"
        return {
            "status": self.status,
            "phase": self.phase,
            "action": self.action,
            "completed_transfers": self.transfers,
            "total_transfers": TOTAL_TRANSFERS,
            "reading_well": WELLS[self.reading_index].label if self.reading_index is not None else None,
            "check": {"status": check_status, "checked": self.checked, "total": len(WELLS),
                      "tolerance_pp": COLOR_TOLERANCE_PP},
            "wells": wells,
        }


class DilutionSample:
    def __init__(self):
        self.restart()

    def restart(self):
        self.index = 0
        self.elapsed = 0.0
        self.stopped = False

    def stop(self):
        if self.index == len(STEPS):
            return False
        self.stopped = True
        return True

    def advance(self, seconds):
        if self.stopped or self.index == len(STEPS):
            return
        self.elapsed += seconds
        while self.index < len(STEPS) and self.elapsed >= STEPS[self.index].seconds:
            self.elapsed -= STEPS[self.index].seconds
            self.index += 1

    def observe(self):
        if self.index == len(STEPS):
            return Observation("complete", "Reference check complete", TOTAL_TRANSFERS, STEPS[-1].pose,
                               "complete", checked=len(WELLS))
        step = STEPS[self.index]
        previous = STEPS[self.index - 1] if self.index else STEPS[0]
        return Observation(
            "stopped" if self.stopped else "running",
            "Sample stopped" if self.stopped else step.label,
            previous.transfers,
            previous.pose.blend(step.pose, self.elapsed / step.seconds),
            step.phase,
            flow=step.flow and not self.stopped,
            checked=previous.checked,
            reading_index=step.reading_index if not self.stopped else None,
        )
