"""Project the sample pose and dye mixtures into the OpenUSD session layer."""

from .dilution import WELLS


STATION = "/World/DilutionStation"
WATER_COLOR = (0.65, 0.84, 0.9)
DYE_COLOR = (0.008, 0.035, 0.34)


def liquid_color(concentration):
    # Use a nonlinear display ramp to make the lighter dilutions readable.
    tint = concentration**.65
    return tuple(water + (dye - water) * tint for water, dye in zip(WATER_COLOR, DYE_COLOR))


class StageDilution:
    def __init__(self, stage):
        from pxr import UsdGeom, UsdShade

        carriage = stage.GetPrimAtPath(f"{STATION}/Carriage")
        head = stage.GetPrimAtPath(f"{STATION}/Carriage/Head")
        self.carriage = carriage.GetAttribute("xformOp:translate")
        self.head = head.GetAttribute("xformOp:translate")
        self.low = head.GetAttribute("webLab:workingHeight").Get()
        self.head_x, self.head_y, self.high = self.head.Get()
        _, self.carriage_y, self.carriage_z = self.carriage.Get()
        self.unit_height = stage.GetPrimAtPath(f"{STATION}/Wells").GetAttribute("webLab:unitHeight").Get()
        self.columns = []
        self.liquids = []
        for name, _ in WELLS:
            path = f"{STATION}/Wells/{name}"
            position = stage.GetPrimAtPath(path).GetAttribute("xformOp:translate").Get()
            liquid = UsdGeom.Cylinder.Get(stage, f"{path}/Liquid")
            height = liquid.GetHeightAttr().Get()
            bottom = liquid.GetPrim().GetAttribute("xformOp:translate").Get()[2] - height / 2
            shader = UsdShade.Shader.Get(stage, f"{path}/Mixture/Preview")
            self.columns.append(position[0])
            self.liquids.append((liquid, bottom, shader.GetInput("diffuseColor")))
        self.tip = UsdGeom.Imageable.Get(stage, f"{STATION}/Carriage/Head/Loaded")
        tip_shader = UsdShade.Shader.Get(stage, f"{STATION}/Looks/TipDye/Preview")
        self.tip_color = tip_shader.GetInput("diffuseColor")
        self.previous = None

    def apply(self, pose):
        from pxr import Gf

        if pose == self.previous:
            return
        start = int(pose.well)
        end = min(start + 1, len(self.columns) - 1)
        x = self.columns[start] + (self.columns[end] - self.columns[start]) * (pose.well - start)
        self.carriage.Set(Gf.Vec3d(x, self.carriage_y, self.carriage_z))
        height = self.low + (self.high - self.low) * pose.height
        self.head.Set(Gf.Vec3d(self.head_x, self.head_y, height))

        for index, (liquid, bottom, color_input) in enumerate(self.liquids):
            mixture = pose.mixtures[index]
            if self.previous and self.previous.mixtures[index] == mixture:
                continue
            height = self.unit_height * mixture.volume
            radius = liquid.GetRadiusAttr().Get()
            liquid.GetHeightAttr().Set(height)
            liquid.GetExtentAttr().Set([(-radius, -radius, -height / 2), (radius, radius, height / 2)])
            prim = liquid.GetPrim()
            prim.GetAttribute("xformOp:translate").Set(Gf.Vec3d(0, 0, bottom + height / 2))
            color = Gf.Vec3f(*liquid_color(mixture.concentration))
            liquid.GetDisplayColorAttr().Set([color])
            color_input.Set(color)

        if not self.previous or self.previous.tip != pose.tip:
            self.tip.GetVisibilityAttr().Set("inherited" if pose.tip.volume > 0 else "invisible")
            self.tip_color.Set(Gf.Vec3f(*liquid_color(pose.tip.concentration)))
        self.previous = pose
