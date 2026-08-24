"""Add > Groundcover: create a fresh vegetation instancer, then drop the user
straight into the paint tool.

Card options in the popup:
  * New Card     - builds a card mesh with a ready alpha-clipped material.
                   Pick a loaded image, browse to open one, or leave empty and
                   add the image to the texture node afterwards.
  * Use Existing - instance any mesh object already in the scene.
"""

import bpy


# ------------------------------------------------------------------ card / material

def _card_mesh(name, page=0, columns=1, rows=1):
    """An upright unit quad (pivot at base). The image is treated as a
    `columns` x `rows` atlas; `page` is the row-major cell whose UV is baked
    onto the card (page 0 = top-left). A strip is just rows = 1."""
    columns = max(1, columns)
    rows = max(1, rows)
    page = max(0, min(page, columns * rows - 1))
    col = page % columns
    row = page // columns
    u0, u1 = col / columns, (col + 1) / columns
    v1 = 1.0 - row / rows            # top of the cell
    v0 = 1.0 - (row + 1) / rows      # bottom of the cell
    m = bpy.data.meshes.new(name)
    m.from_pydata([(-0.5, 0, 0), (0.5, 0, 0), (0.5, 0, 1), (-0.5, 0, 1)], [], [(0, 1, 2, 3)])
    m.update()
    uv = m.uv_layers.new(name="UVMap")
    for d, co in zip(uv.data, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]):
        d.uv = co
    return m


def _card_material(name, image=None, speed=0.1):
    """Ready-to-use foliage material: Image Texture -> Base Color + Alpha on a
    Principled BSDF, alpha-clipped and double-sided. The image can be filled in
    later via the 'Card Texture' node. A 'speed' custom property (Vector4, wind
    amount in [0]) is stored."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = False
    mat["speed"] = [float(speed), 0.0, 0.0, 0.0]
    # alpha cutout - property names differ across EEVEE versions, so guard each
    for attr, val in (("blend_method", 'CLIP'),
                      ("shadow_method", 'CLIP'),
                      ("alpha_threshold", 0.5),
                      ("surface_render_method", 'DITHERED')):
        if hasattr(mat, attr):
            try:
                setattr(mat, attr, val)
            except Exception:
                pass

    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (300, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (0, 0)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.location = (-420, 0)
    tex.name = "Card Texture"
    tex.label = "Card Texture"
    if image is not None:
        tex.image = image
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    return mat


def _new_card(name, image, page=0, columns=1, rows=1, speed=0.1):
    """Fresh card mesh + material for a 'New Card' instancer."""
    if image is None:
        page, columns, rows = 0, 1, 1
    mesh = _card_mesh("GC_Card_%s" % name, page, columns, rows)
    mesh.materials.append(_card_material("GC_%s" % name, image, speed))
    return mesh


def _default_card_mesh():
    name = "GC_DefaultCard"
    return bpy.data.meshes.get(name) or _card_mesh(name)


# ------------------------------------------------------------------ instancer

def _templates_collection(context):
    name = "GC_Templates"
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        context.scene.collection.children.link(col)
        lc = context.view_layer.layer_collection.children.get(name)
        if lc:
            lc.exclude = True
    return col


def _template_object(context, mesh):
    """Hidden object whose geometry the node group instances."""
    tname = "GC_Template_%s" % mesh.name
    obj = bpy.data.objects.get(tname)
    if obj is None:
        obj = bpy.data.objects.new(tname, mesh)
        _templates_collection(context).objects.link(obj)
        # excluded collection already keeps it out of the view layer
        obj.hide_render = True
    return obj


# Bump when the instancer node group structure changes, so older cached groups
# in an existing .blend are never silently reused (that hides new wiring such
# as the rotation / align support).
_NG_VERSION = 4


def _instancer_node_group(template_obj, wind=0.0):
    # Wind amplitude: prefer the template material's "speed" custom property (value
    # in [0]); fall back to the passed value otherwise.
    wamp = float(wind)
    if template_obj.data and template_obj.data.materials:
        mat = template_obj.data.materials[0]
        if mat is not None and "speed" in mat:
            try:
                wamp = float(mat["speed"][0])
            except Exception:
                pass
    name = "GC_Instancer_v%d_%s%s" % (_NG_VERSION, template_obj.name,
                                      ("_wind" if wamp > 0 else ""))
    ng = bpy.data.node_groups.get(name)
    if ng is not None:
        return ng

    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

    nin = ng.nodes.new("NodeGroupInput");  nin.location = (-500, 0)
    nout = ng.nodes.new("NodeGroupOutput"); nout.location = (600, 0)

    info = ng.nodes.new("GeometryNodeObjectInfo")
    info.location = (-260, -220)
    info.transform_space = 'ORIGINAL'
    info.inputs["Object"].default_value = template_obj

    sattr = ng.nodes.new("GeometryNodeInputNamedAttribute")
    sattr.data_type = 'FLOAT_VECTOR'
    sattr.inputs["Name"].default_value = "scale"
    sattr.location = (-500, 200)

    iop = ng.nodes.new("GeometryNodeInstanceOnPoints")
    iop.location = (200, 0)
    ng.links.new(nin.outputs["Geometry"], iop.inputs["Points"])
    ng.links.new(info.outputs["Geometry"], iop.inputs["Instance"])
    ng.links.new(iop.outputs["Instances"], nout.inputs["Geometry"])

    scale_out = sattr.outputs["Attribute"]
    try:
        vlen = ng.nodes.new("ShaderNodeVectorMath")
        vlen.operation = 'LENGTH'; vlen.location = (-300, 320)
        ng.links.new(scale_out, vlen.inputs[0])
        cmp = ng.nodes.new("FunctionNodeCompare")
        cmp.data_type = 'FLOAT'; cmp.operation = 'LESS_THAN'
        cmp.inputs[1].default_value = 1e-6; cmp.location = (-120, 320)
        ng.links.new(vlen.outputs["Value"], cmp.inputs[0])
        switch = ng.nodes.new("GeometryNodeSwitch")
        switch.input_type = 'VECTOR'; switch.location = (0, 120)
        ng.links.new(cmp.outputs["Result"], switch.inputs["Switch"])
        ng.links.new(scale_out, switch.inputs["False"])
        switch.inputs["True"].default_value = (1.0, 1.0, 1.0)
        ng.links.new(switch.outputs[0], iop.inputs["Scale"])
    except Exception:
        ng.links.new(scale_out, iop.inputs["Scale"])

    # rotation from the 'rotation' attribute (align-to-normal / random yaw).
    # The Rotation socket takes the quaternion attribute directly - routing it
    # through Quaternion-to-Rotation mis-converts it.
    try:
        rattr = ng.nodes.new("GeometryNodeInputNamedAttribute")
        rattr.data_type = 'QUATERNION'
        rattr.inputs["Name"].default_value = "rotation"
        rattr.location = (-500, -120)
        rot_out = rattr.outputs["Attribute"]
        ng.links.new(rot_out, iop.inputs["Rotation"])   # base link (guaranteed)
    except Exception:
        rot_out = None

    # optional wind sway, combined in LOCAL space so it sways about the card's
    # own axis. Phase = world_position . wind_dir * spatial_freq, so nearby
    # cards move together as a wave instead of randomly.
    if wamp > 0 and rot_out is not None:
        try:
            WIND_DIR = (1.0, 0.0, 0.0)
            SPATIAL_FREQ = 0.5
            SPEED = 1.5

            pos = ng.nodes.new("GeometryNodeInputPosition"); pos.location = (-500, -300)
            wdir = ng.nodes.new("ShaderNodeCombineXYZ"); wdir.location = (-500, -430)
            wdir.inputs[0].default_value = WIND_DIR[0]
            wdir.inputs[1].default_value = WIND_DIR[1]
            wdir.inputs[2].default_value = WIND_DIR[2]
            dot = ng.nodes.new("ShaderNodeVectorMath")
            dot.operation = 'DOT_PRODUCT'; dot.location = (-320, -340)
            ng.links.new(pos.outputs[0], dot.inputs[0])
            ng.links.new(wdir.outputs[0], dot.inputs[1])
            phase = ng.nodes.new("ShaderNodeMath")
            phase.operation = 'MULTIPLY'; phase.inputs[1].default_value = SPATIAL_FREQ
            phase.location = (-160, -340)
            ng.links.new(dot.outputs["Value"], phase.inputs[0])

            st = ng.nodes.new("GeometryNodeInputSceneTime"); st.location = (-500, -200)
            tt = ng.nodes.new("ShaderNodeMath")
            tt.operation = 'MULTIPLY'; tt.inputs[1].default_value = SPEED
            tt.location = (-320, -200)
            ng.links.new(st.outputs["Seconds"], tt.inputs[0])

            arg = ng.nodes.new("ShaderNodeMath"); arg.operation = 'ADD'; arg.location = (0, -260)
            ng.links.new(tt.outputs[0], arg.inputs[0])
            ng.links.new(phase.outputs[0], arg.inputs[1])
            sine = ng.nodes.new("ShaderNodeMath"); sine.operation = 'SINE'; sine.location = (160, -260)
            ng.links.new(arg.outputs[0], sine.inputs[0])
            amp = ng.nodes.new("ShaderNodeMath")
            amp.operation = 'MULTIPLY'; amp.inputs[1].default_value = float(wamp)
            amp.location = (320, -260)
            ng.links.new(sine.outputs[0], amp.inputs[0])

            aa = ng.nodes.new("FunctionNodeAxisAngleToRotation"); aa.location = (480, -220)
            aa.inputs[0].default_value = (1.0, 0.0, 0.0)     # tilt about local X
            ng.links.new(amp.outputs[0], aa.inputs[1])
            rr = ng.nodes.new("FunctionNodeRotateRotation"); rr.location = (660, -120)
            try:
                rr.rotation_space = 'LOCAL'                  # sway in the card's frame
            except Exception:
                pass
            ng.links.new(rot_out, rr.inputs[0])
            ng.links.new(aa.outputs[0], rr.inputs[1])
            ng.links.new(rr.outputs[0], iop.inputs["Rotation"])   # relink through wind
        except Exception:
            pass

    return ng


def _new_instancer(context, name, template_obj, collection, page=0, wind=0.0):
    mesh = bpy.data.meshes.new("Points_%s" % name)   # starts empty
    for attr, atype in (("scale", 'FLOAT_VECTOR'), ("mw_slot", 'INT'),
                        ("mw_texture_page", 'INT'), ("mw_render_flags", 'INT'),
                        ("rotation", 'QUATERNION')):
        mesh.attributes.new(attr, atype, 'POINT')

    obj = bpy.data.objects.new(name, mesh)
    obj["mw_instancer"] = True
    obj["mw_page"] = int(page)
    mod = obj.modifiers.new("GC_Instancer", 'NODES')
    mod.node_group = _instancer_node_group(template_obj, wind)
    collection.objects.link(obj)
    return obj


# ------------------------------------------------------------------ operator

class GC_OT_add_instancer(bpy.types.Operator):
    bl_idname = "gc.add_instancer"
    bl_label = "Add Groundcover"
    bl_options = {'REGISTER', 'UNDO'}

    name: bpy.props.StringProperty(name="Name", default="Vegetation")
    card_mode: bpy.props.EnumProperty(
        name="Card",
        items=[('NEW', "New Card", "Create a card with a ready material"),
               ('EXISTING', "Use Existing", "Instance an object already in the scene")],
        default='NEW')
    # New Card
    image_name: bpy.props.StringProperty(name="Image", description="Image already loaded in Blender")
    image_path: bpy.props.StringProperty(
        name="Open", subtype='FILE_PATH', description="Open an image file from disk")
    atlas_layout: bpy.props.EnumProperty(
        name="Atlas",
        items=[('GRID', "Grid", "Columns x rows atlas (common in-game)"),
               ('STRIP', "Strip", "A single row of pages")],
        default='GRID')
    pages: bpy.props.IntProperty(
        name="Pages", default=4, min=1, max=64,
        description="Number of columns in a strip atlas")
    columns: bpy.props.IntProperty(
        name="Columns", default=4, min=1, max=64,
        description="Grid columns")
    rows: bpy.props.IntProperty(
        name="Rows", default=4, min=1, max=64,
        description="Grid rows")
    page: bpy.props.IntProperty(
        name="Page", default=0, min=0,
        description="Which cell this card uses (row-major, 0 = top-left)")
    # Use Existing
    card_object: bpy.props.StringProperty(
        name="Object", description="Mesh object to instance")
    # common
    size_min: bpy.props.FloatProperty(name="Min Size", default=0.8, min=0.001)
    size_max: bpy.props.FloatProperty(name="Max Size", default=1.4, min=0.001)
    radius: bpy.props.FloatProperty(name="Brush Radius", default=5.0, min=0.01)
    wind: bpy.props.BoolProperty(
        name="Wind Sway", default=False,
        description="Animate the cards with a gentle time-based sway")
    wind_amount: bpy.props.FloatProperty(
        name="Wind Amount", default=0.1, min=0.0, soft_max=1.0,
        description="Sway strength (also written to the material's 'speed' property). The material's speed custom property will be used if it exists")
    activate_tool: bpy.props.BoolProperty(
        name="Start Painting", default=True,
        description="Select the new instancer and activate the Vegetation Paint tool")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=340)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name")
        layout.prop(self, "card_mode", expand=True)

        if self.card_mode == 'EXISTING':
            layout.prop_search(self, "card_object", bpy.data, "objects", text="Object")
            if not self.card_object:
                layout.label(text="None picked - a default quad is used.", icon='INFO')
        else:
            col = layout.column(align=True)
            col.prop_search(self, "image_name", bpy.data, "images", text="Image")
            col.prop(self, "image_path", text="Open")
            has_image = bool(self.image_name or self.image_path)

            atlas = layout.column(align=True)
            atlas.enabled = has_image
            atlas.prop(self, "atlas_layout", expand=True)
            if self.atlas_layout == 'GRID':
                r = atlas.row(align=True)
                r.prop(self, "columns")
                r.prop(self, "rows")
            else:
                atlas.prop(self, "pages")
            atlas.prop(self, "page")

            if has_image:
                layout.label(text="Fill the 'Card Texture' node if empty.", icon='INFO')
            else:
                layout.label(text="No image - single page (0).", icon='INFO')

        row = layout.row(align=True)
        row.prop(self, "size_min")
        row.prop(self, "size_max")
        layout.prop(self, "radius")
        row = layout.row(align=True)
        row.prop(self, "wind")
        if self.wind:
            row.prop(self, "wind_amount")
        layout.prop(self, "activate_tool")

    def execute(self, context):
        if self.card_mode == 'EXISTING':
            src = bpy.data.objects.get(self.card_object) if self.card_object else None
            if self.card_object and src is None:
                self.report({'WARNING'}, "Object %r not found" % self.card_object)
            mesh = (src.data if (src and src.type == 'MESH') else _default_card_mesh())
            new_page = 0
        else:
            image = None
            if self.image_path:
                try:
                    image = bpy.data.images.load(bpy.path.abspath(self.image_path),
                                                 check_existing=True)
                except Exception as exc:
                    self.report({'WARNING'}, "Could not open image: %s" % exc)
            elif self.image_name:
                image = bpy.data.images.get(self.image_name)
            new_page = self.page if image is not None else 0
            if image is None:
                cols, rws = 1, 1
            elif self.atlas_layout == 'GRID':
                cols, rws = self.columns, self.rows
            else:
                cols, rws = self.pages, 1
            mesh = _new_card(self.name, image, new_page, cols, rws,
                             speed=(self.wind_amount if self.wind else 0.0))

        wind = self.wind_amount if self.wind else 0.0
        template = _template_object(context, mesh)
        collection = context.collection or context.scene.collection
        obj = _new_instancer(context, self.name, template, collection, new_page, wind)

        s = context.scene.gc_brush
        s.size_min = self.size_min
        s.size_max = self.size_max
        s.radius = self.radius

        for o in context.selected_objects:
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj

        if self.activate_tool:
            try:
                bpy.ops.wm.tool_set_by_id(name="gc.vegetation_paint")
            except Exception:
                pass

        self.report({'INFO'}, "Created groundcover '%s' - drag on the terrain to paint" % obj.name)
        return {'FINISHED'}


def _add_menu(self, context):
    self.layout.operator("gc.add_instancer", text="Groundcover", icon='OUTLINER_OB_POINTCLOUD')


def register():
    bpy.utils.register_class(GC_OT_add_instancer)
    bpy.types.VIEW3D_MT_add.append(_add_menu)


def unregister():
    bpy.types.VIEW3D_MT_add.remove(_add_menu)
    bpy.utils.unregister_class(GC_OT_add_instancer)
