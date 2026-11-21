"""Project the sample pose and dye mixtures into the OpenUSD session layer."""

from .dilution import Mixture, WELLS


STATION = "/World/Cell"
WATER_COLOR = (0.65, 0.84, 0.9)
DYE_COLOR = (0.008, 0.035, 0.34)
COLOR_EXPONENT = .65
COLOR_AXIS = tuple(dye - water for water, dye in zip(WATER_COLOR, DYE_COLOR))
COLOR_AXIS_LENGTH_SQUARED = sum(channel**2 for channel in COLOR_AXIS)


def liquid_color(concentration):
    # Use a nonlinear display ramp to make the lighter dilutions readable.
    tint = concentration**COLOR_EXPONENT
    return tuple(water + channel * tint for water, channel in zip(WATER_COLOR, COLOR_AXIS))


def read_concentration(color):
    tint = sum((value - water) * channel for value, water, channel in zip(color, WATER_COLOR, COLOR_AXIS))
    return max(0, tint / COLOR_AXIS_LENGTH_SQUARED)**(1 / COLOR_EXPONENT)


def set_column(cylinder, position, height):
    from pxr import Gf

    radius = cylinder.GetRadiusAttr().Get()
    cylinder.GetHeightAttr().Set(height)
    cylinder.GetExtentAttr().Set([(-radius, -radius, -height / 2), (radius, radius, height / 2)])
    cylinder.GetPrim().GetAttribute("xformOp:translate").Set(Gf.Vec3d(*position))


class StageDilution:
    def __init__(self, stage):
        from pxr import UsdGeom, UsdShade

        if UsdGeom.GetStageUpAxis(stage) != UsdGeom.Tokens.z or UsdGeom.GetStageMetersPerUnit(stage) != 1:
            raise ValueError("The Web Lab stage must use meters and Z up.")
        stage.SetEditTarget(stage.GetSessionLayer())
        carriage_path = f"{STATION}/Gantry/Carriage"
        tool_path = f"{carriage_path}/Tool"
        carriage = stage.GetPrimAtPath(carriage_path)
        head = stage.GetPrimAtPath(tool_path)
        self.carriage = carriage.GetAttribute("xformOp:translate")
        self.head = head.GetAttribute("xformOp:translate")
        self.low = head.GetAttribute("webLab:workingHeight").Get()
        self.head_x, self.head_y, self.high = self.head.Get()
        _, self.carriage_y, self.carriage_z = self.carriage.Get()
        self.unit_height = stage.GetPrimAtPath(f"{STATION}/Wells").GetAttribute("webLab:unitHeight").Get()
        self.positions = []
        self.liquids = []
        self.focus_rings = []
        for well in WELLS:
            path = f"{STATION}/Wells/{well.prim}"
            position = stage.GetPrimAtPath(path).GetAttribute("xformOp:translate").Get()
            liquid = UsdGeom.Cylinder.Get(stage, f"{path}/Liquid")
            height = liquid.GetHeightAttr().Get()
            bottom = liquid.GetPrim().GetAttribute("xformOp:translate").Get()[2] - height / 2
            shader = UsdShade.Shader.Get(stage, f"{path}/Mixture/Preview")
            self.positions.append(position)
            self.liquids.append((liquid, bottom, shader.GetInput("diffuseColor")))
            self.focus_rings.append(UsdGeom.Imageable.Get(stage, f"{path}/ReadMarker"))
        self.tip = UsdGeom.Imageable.Get(stage, f"{tool_path}/Loaded")
        self.tip_z = stage.GetPrimAtPath(f"{tool_path}/TipEnd").GetAttribute("xformOp:translate").Get()[2]
        tip_shader = UsdShade.Shader.Get(stage, f"{STATION}/Looks/TipDye/Preview")
        self.tip_color = tip_shader.GetInput("diffuseColor")
        self.stream = UsdGeom.Cylinder.Get(stage, f"{STATION}/Stream")
        self.reading_index = None
        self.previous = None

    def apply(self, observation):
        from pxr import Gf

        pose = observation.pose
        start = int(pose.well)
        end = min(start + 1, len(self.positions) - 1)
        x = self.positions[start][0] + (self.positions[end][0] - self.positions[start][0]) * (pose.well - start)
        height = self.low + (self.high - self.low) * pose.height
        if not self.previous or self.previous.well != pose.well:
            self.carriage.Set(Gf.Vec3d(x, self.carriage_y, self.carriage_z))
        if not self.previous or self.previous.height != pose.height:
            self.head.Set(Gf.Vec3d(self.head_x, self.head_y, height))

        for index, (liquid, bottom, color_input) in enumerate(self.liquids):
            mixture = pose.mixtures[index]
            if self.previous and self.previous.mixtures[index] == mixture:
                continue
            fill_height = self.unit_height * mixture.volume
            set_column(liquid, (0, 0, bottom + fill_height / 2), fill_height)
            color = Gf.Vec3f(*liquid_color(mixture.concentration))
            liquid.GetDisplayColorAttr().Set([color])
            color_input.Set(color)

        if not self.previous or self.previous.tip != pose.tip:
            self.tip.GetVisibilityAttr().Set("inherited" if pose.tip.volume > 0 else "invisible")
            self.tip_color.Set(Gf.Vec3f(*liquid_color(pose.tip.concentration)))

        stream_visible = observation.flow and pose.tip.volume > 0
        if stream_visible:
            position = self.positions[start]
            liquid, bottom, _ = self.liquids[start]
            top = height + self.tip_z
            level = position[2] + bottom + liquid.GetHeightAttr().Get()
            set_column(self.stream, (x, position[1], (top + level) / 2), top - level)
        visibility = self.stream.GetVisibilityAttr()
        desired = "inherited" if stream_visible else "invisible"
        if visibility.Get() != desired:
            visibility.Set(desired)

        reading = observation.reading_index
        if reading != self.reading_index:
            if self.reading_index is not None:
                self.focus_rings[self.reading_index].MakeInvisible()
            if reading is not None:
                self.focus_rings[reading].MakeVisible()
            self.reading_index = reading
        self.previous = pose

    def observe(self):
        readings = []
        for liquid, _, color in self.liquids:
            volume = liquid.GetHeightAttr().Get() / self.unit_height
            readings.append(Mixture(volume, volume * read_concentration(color.Get())))
        return tuple(readings)
