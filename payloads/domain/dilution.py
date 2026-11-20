"""One fixed food-dye dilution in the simulated workcell."""

from dataclasses import dataclass


WELLS = (("Stock", "Stock"), ("Half", "1:2"), ("Quarter", "1:4"), ("Eighth", "1:8"))
TOTAL_TRANSFERS = len(WELLS) - 1


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


START = Pose(0, 1, (Mixture(2, 2), WATER, WATER, WATER))


def dilution_steps():
    mixtures = START.mixtures
    yield Step("Ready with stock dye and water", 2.0, START, 0)
    for source_index in range(TOTAL_TRANSFERS):
        target_index = source_index + 1
        source_name, target_name = WELLS[source_index][1], WELLS[target_index][1]
        yield Step(f"Lowering over {source_name}", .8, Pose(source_index, 0, mixtures), source_index)

        source = mixtures[source_index]
        draw = Mixture(1, source.concentration)
        remaining = Mixture(source.volume - draw.volume, source.dye - draw.dye)
        mixtures = mixtures[:source_index] + (remaining,) + mixtures[target_index:]
        yield Step(f"Drawing from {source_name}", 1.2, Pose(source_index, 0, mixtures, draw), source_index)
        yield Step(f"Lifting from {source_name}", .8, Pose(source_index, 1, mixtures, draw), source_index)
        yield Step(f"Moving to {target_name}", 1.2, Pose(target_index, 1, mixtures, draw), source_index)
        yield Step(f"Lowering over {target_name}", .8, Pose(target_index, 0, mixtures, draw), source_index)

        target = mixtures[target_index]
        mixed = Mixture(target.volume + draw.volume, target.dye + draw.dye)
        mixtures = mixtures[:target_index] + (mixed,) + mixtures[target_index + 1:]
        yield Step(f"Dispensing and mixing {target_name}", 1.6, Pose(target_index, 0, mixtures), target_index)
        yield Step(f"Lifting from {target_name}", .8, Pose(target_index, 1, mixtures), target_index)
    yield Step("Parking the pipette", 1.2, Pose(1.5, 1, mixtures), TOTAL_TRANSFERS)


STEPS = tuple(dilution_steps())


@dataclass(frozen=True)
class Observation:
    status: str
    action: str
    transfers: int
    pose: Pose

    def snapshot(self):
        return {
            "status": self.status,
            "action": self.action,
            "completed_transfers": self.transfers,
            "total_transfers": TOTAL_TRANSFERS,
            "wells": [
                {"name": name, "concentration_percent": round(mixture.concentration * 100, 2)}
                for (_, name), mixture in zip(WELLS, self.pose.mixtures)
            ],
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
            return Observation("complete", "Dye dilution complete", TOTAL_TRANSFERS, STEPS[-1].pose)
        step = STEPS[self.index]
        previous = STEPS[self.index - 1] if self.index else STEPS[0]
        return Observation(
            "stopped" if self.stopped else "running",
            "Sample stopped" if self.stopped else step.label,
            previous.transfers,
            previous.pose.blend(step.pose, self.elapsed / step.seconds),
        )
