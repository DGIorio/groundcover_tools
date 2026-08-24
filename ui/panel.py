import bpy

try:
    from ..operators.paint import is_instancer
except Exception:
    def is_instancer(obj):
        return (obj is not None and obj.type == 'MESH'
                and any(m.type == 'NODES' for m in obj.modifiers))


class GC_PT_tools(bpy.types.Panel):
    bl_label = "Groundcover Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Groundcover"

    def draw(self, context):
        layout = self.layout
        s = context.scene.gc_brush
        obj = context.active_object
        instancer = is_instancer(obj)

        if obj is None:
            layout.label(text="No active object", icon='DOT')
        elif instancer:
            layout.label(text="Instancer: %s" % obj.name, icon='OUTLINER_OB_POINTCLOUD')
        else:
            layout.label(text="Active isn't an instancer", icon='INFO')

        box = layout.box()
        box.label(text="New", icon='ADD')
        box.operator("gc.add_instancer", text="Add Groundcover", icon='OUTLINER_OB_POINTCLOUD')
        box.label(text="Also under Add > Groundcover.")

        box = layout.box()
        box.label(text="Paint", icon='BRUSH_DATA')
        if not instancer:
            col = box.column(align=True)
            col.label(text="Select a Quadtree point cloud")
            col.label(text="(needs light-mode import).")
        else:
            box.label(text="Activate 'Vegetation Paint' (T),")
            box.label(text="then drag. Ctrl-drag inverts mode.")
        box.prop(s, "paint_mode", expand=True)
        col = box.column(align=True)
        col.prop(s, "radius")
        col.prop(s, "density")
        col.prop(s, "spacing")
        col.prop(s, "flow")
        col.prop(s, "single")

        col = box.column(align=True)
        col.label(text="Orientation")
        col.prop(s, "align_mode", text="")
        col.prop(s, "random_yaw")

        col = box.column(align=True)
        col.label(text="Size")
        col.prop(s, "size_mode", text="")
        row = col.row(align=True)
        row.prop(s, "size_min")
        row.prop(s, "size_max")
        if s.size_mode == 'NONUNIFORM':
            row = col.row(align=True)
            row.prop(s, "height_min")
            row.prop(s, "height_max")

        box = layout.box()
        box.label(text="Edit", icon='MODIFIER')
        box.operator("gc.scale_cards", text="Scale Selected", icon='FULLSCREEN_ENTER')
        box.label(text="Edit Mode: select points first.")


def register():
    bpy.utils.register_class(GC_PT_tools)


def unregister():
    bpy.utils.unregister_class(GC_PT_tools)
