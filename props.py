import bpy


class GCBrushSettings(bpy.types.PropertyGroup):
    """Persistent brush settings, stored per scene (scene.gc_brush)."""
    # brush
    radius: bpy.props.FloatProperty(
        name="Radius", default=5.0, min=0.01, soft_max=50.0,
        description="Brush radius in world units")
    density: bpy.props.IntProperty(
        name="Density", default=6, min=1, max=500,
        description="Cards placed per dab (one stamp of the brush as you drag)")
    spacing: bpy.props.FloatProperty(
        name="Spacing", default=1.0, min=0.0, soft_max=20.0,
        description="Minimum cursor travel between dabs")
    flow: bpy.props.FloatProperty(
        name="Flow", default=20.0, min=0.5, max=60.0,
        description="Maximum dabs per second (lower = slower painting)")
    single: bpy.props.BoolProperty(
        name="Single Card", default=False,
        description="Place one card at the cursor instead of scattering")
    paint_mode: bpy.props.EnumProperty(
        name="Mode",
        items=[('PAINT', "Paint", "Add cards"),
               ('ERASE', "Erase", "Remove cards within the brush")],
        default='PAINT')

    # size
    size_mode: bpy.props.EnumProperty(
        name="Size",
        items=[('EQUAL', "Equal", "Square cards (width = height)"),
               ('RANDOM', "Random", "Width and height each random in the range"),
               ('NONUNIFORM', "Non-uniform", "Separate width and height ranges")],
        default='EQUAL')
    size_min: bpy.props.FloatProperty(name="W Min", default=0.8, min=0.001, soft_max=100.0)
    size_max: bpy.props.FloatProperty(name="W Max", default=1.4, min=0.001, soft_max=100.0)
    height_min: bpy.props.FloatProperty(name="H Min", default=1.5, min=0.001, soft_max=100.0)
    height_max: bpy.props.FloatProperty(name="H Max", default=3.0, min=0.001, soft_max=100.0)

    # orientation
    align_mode: bpy.props.EnumProperty(
        name="Align",
        items=[('NONE', "Upright", "Cards stay vertical"),
               ('NORMAL', "Normal", "Align each card to the surface normal"),
               ('AVERAGE', "Average", "Align to the averaged normal of the dab")],
        default='NONE')
    random_yaw: bpy.props.BoolProperty(
        name="Random Yaw", default=True,
        description="Random rotation around the up axis")


def register():
    bpy.utils.register_class(GCBrushSettings)
    bpy.types.Scene.gc_brush = bpy.props.PointerProperty(type=GCBrushSettings)


def unregister():
    del bpy.types.Scene.gc_brush
    bpy.utils.unregister_class(GCBrushSettings)
