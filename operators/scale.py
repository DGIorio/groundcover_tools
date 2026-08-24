"""Scale groundcover instancer cards by editing the per-point 'scale' attribute.
Select the point(s) in Edit Mode (or nothing, to affect all) and run; drag
Factor in the redo panel to dial the size."""

import bpy


class GC_OT_scale_cards(bpy.types.Operator):
    bl_idname = "gc.scale_cards"
    bl_label = "Scale Groundcover Cards"
    bl_options = {'REGISTER', 'UNDO'}

    factor: bpy.props.FloatProperty(
        name="Factor", default=1.5, min=0.0001, soft_min=0.1, soft_max=10.0)
    height_only: bpy.props.BoolProperty(
        name="Height Only", default=False,
        description="Scale only the card height, keeping its width")

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH'
                and obj.data is not None
                and "scale" in obj.data.attributes)

    def execute(self, context):
        obj = context.active_object
        was_edit = (obj.mode == 'EDIT')
        if was_edit:
            bpy.ops.object.mode_set(mode='OBJECT')

        mesh = obj.data
        attr = mesh.attributes["scale"]
        selected = [i for i, v in enumerate(mesh.vertices) if v.select]
        targets = selected if selected else range(len(mesh.vertices))

        f = self.factor
        for i in targets:
            s = attr.data[i].vector
            if self.height_only:
                attr.data[i].vector = (s[0], s[1], s[2] * f)
            else:
                attr.data[i].vector = (s[0] * f, s[1] * f, s[2] * f)
        mesh.update()

        if was_edit:
            bpy.ops.object.mode_set(mode='EDIT')

        self.report({'INFO'}, "Scaled %d card(s) by %.3g" % (len(targets), f))
        return {'FINISHED'}


def register():
    bpy.utils.register_class(GC_OT_scale_cards)


def unregister():
    bpy.utils.unregister_class(GC_OT_scale_cards)
