"""Vegetation Paint - a WorkSpaceTool + stroke operator.

Paint or erase cards onto the surface under the cursor, into the ACTIVE
instancer. Mode (Paint/Erase) is a toggle in the tool settings; Ctrl-drag
temporarily inverts it. A brush ring is drawn on the surface.
"""

import math
import random
import time

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector, Quaternion
from bpy_extras import view3d_utils


# ------------------------------------------------------------------ helpers

def is_instancer(obj):
    return (obj is not None and obj.type == 'MESH'
            and any(m.type == 'NODES' for m in obj.modifiers))


def _ray_from_mouse(context, mx, my):
    region = context.region
    rv3d = context.region_data
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, (mx, my))
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, (mx, my))
    return origin, direction


def _is_gc_instancer(ob):
    """True for any groundcover instancer object (so the ray passes through
    existing vegetation to the terrain underneath)."""
    if ob is None:
        return False
    o = getattr(ob, "original", ob)
    if o.get("is_groundcover"):
        return True
    for m in getattr(o, "modifiers", ()):
        ng = getattr(m, "node_group", None)
        if ng is not None and ng.name.startswith("GC_Instancer"):
            return True
    return False


def _raycast_terrain(context, origin, direction, target=None, max_steps=8):
    """Raycast the scene, stepping past the paint target AND any other
    groundcover instancer, so cards land on the ground, not on vegetation."""
    depsgraph = context.evaluated_depsgraph_get()
    o = origin.copy()
    for _ in range(max_steps):
        hit, loc, nrm, idx, ob, mat = context.scene.ray_cast(depsgraph, o, direction)
        if not hit:
            return (False, None, None)
        if ob is target or _is_gc_instancer(ob):
            o = loc + direction * 1e-3
            continue
        return (True, loc, nrm)
    return (False, None, None)


def _tangent_basis(n):
    n = n.normalized()
    t = n.cross(Vector((0, 0, 1)))
    if t.length < 1e-4:
        t = n.cross(Vector((1, 0, 0)))
    t.normalize()
    b = n.cross(t).normalized()
    return t, b


def _page_of(obj):
    a = obj.data.attributes.get("page")
    if a and len(a.data):
        return a.data[0].value
    return int(obj.get("page", 0))


def _card_size(s):
    lo, hi = min(s.size_min, s.size_max), max(s.size_min, s.size_max)
    if s.size_mode == 'RANDOM':
        return random.uniform(lo, hi), random.uniform(lo, hi)
    if s.size_mode == 'NONUNIFORM':
        hlo, hhi = min(s.height_min, s.height_max), max(s.height_min, s.height_max)
        return random.uniform(lo, hi), random.uniform(hlo, hhi)
    v = random.uniform(lo, hi)   # EQUAL
    return v, v


_WORLD_UP = Vector((0, 0, 1))


def _card_rotation(normal, align_mode, random_yaw):
    """Quaternion (w,x,y,z) for one card. Height (+Z) is rotated onto `up` by
    the shortest arc (so 'Upright' is exactly identity), then optionally spun
    around `up` by a random yaw."""
    if align_mode == 'NONE':
        up = _WORLD_UP
        q = Quaternion()                       # identity - stays vertical
    else:
        up = normal.normalized() if normal.length > 1e-6 else _WORLD_UP
        q = _WORLD_UP.rotation_difference(up)  # shortest arc +Z -> normal
    if random_yaw:
        q = Quaternion(up, random.uniform(0.0, math.tau)) @ q
    return (q.w, q.x, q.y, q.z)


# ------------------------------------------------------------------ add / erase

def _append_points(obj, world_points, sizes, rots, page):
    if not world_points:
        return
    mesh = obj.data
    mw_inv = obj.matrix_world.inverted()
    start = len(mesh.vertices)
    mesh.vertices.add(len(world_points))
    for i, wp in enumerate(world_points):
        mesh.vertices[start + i].co = mw_inv @ wp

    def _attr(name, atype):
        a = mesh.attributes.get(name)
        return a if a is not None else mesh.attributes.new(name, atype, 'POINT')

    a_scale = _attr("scale", 'FLOAT_VECTOR')
    a_slot = _attr("slot", 'INT')
    a_page = _attr("page", 'INT')
    a_flags = _attr("flags", 'INT')
    a_rot = _attr("rotation", 'QUATERNION')
    for i, (w, h) in enumerate(sizes):
        j = start + i
        a_scale.data[j].vector = (w, w, h)
        a_slot.data[j].value = j
        a_page.data[j].value = page
        a_flags.data[j].value = 1
        a_rot.data[j].value = rots[i]
    mesh.update()


def _rebuild_points(obj, keep):
    old = obj.data
    old_name = old.name
    coords = [tuple(old.vertices[i].co) for i in keep]
    new = bpy.data.meshes.new(old_name + "_tmp")
    new.from_pydata(coords, [], [])
    new.update()
    for a in old.attributes:
        if a.domain != 'POINT' or a.name.startswith('.') or a.name == 'position':
            continue
        t = a.data_type
        na = new.attributes.new(a.name, t, 'POINT')
        for j, i in enumerate(keep):
            src, dst = a.data[i], na.data[j]
            if t in ('FLOAT_VECTOR', 'FLOAT2'):
                dst.vector = src.vector
            elif t in ('FLOAT_COLOR', 'BYTE_COLOR'):
                dst.color = src.color
            elif t == 'QUATERNION':
                dst.value = src.value
            else:
                dst.value = src.value
    obj.data = new
    if old.users == 0:
        try:
            bpy.data.meshes.remove(old)
        except Exception:
            pass
    try:
        new.name = old_name
    except Exception:
        pass
    obj.data.update()


def _erase_near(obj, center_world, radius):
    mesh = obj.data
    mw = obj.matrix_world
    r2 = radius * radius
    keep = [i for i, v in enumerate(mesh.vertices)
            if ((mw @ v.co) - center_world).length_squared > r2]
    if len(keep) == len(mesh.vertices):
        return 0
    removed = len(mesh.vertices) - len(keep)
    _rebuild_points(obj, keep)
    return removed


# ------------------------------------------------------------------ brush ring

_RING_SEGMENTS = 48


def _draw_brush_ring(context, xy):
    try:
        region = context.region
        rv3d = context.region_data
        if region is None or rv3d is None:
            return
        s = context.scene.gc_brush
        origin, direction = _ray_from_mouse(context, xy[0], xy[1])
        hit, loc, nrm = _raycast_terrain(context, origin, direction)
        if not hit:
            return
        t, b = _tangent_basis(nrm)
        pts = []
        for i in range(_RING_SEGMENTS + 1):
            a = (i / _RING_SEGMENTS) * math.tau
            wp = loc + (t * math.cos(a) + b * math.sin(a)) * s.radius
            p2 = view3d_utils.location_3d_to_region_2d(region, rv3d, wp)
            if p2 is None:
                return
            pts.append((p2.x, p2.y))
        color = (1.0, 0.3, 0.3, 0.9) if s.paint_mode == 'ERASE' else (1.0, 0.85, 0.2, 0.9)
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(1.5)
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": pts})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')
    except Exception:
        pass


# ------------------------------------------------------------------ operator

class GC_OT_paint(bpy.types.Operator):
    bl_idname = "gc.paint"
    bl_label = "Paint Groundcover"
    bl_options = {'REGISTER', 'UNDO'}

    invert: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def _dab(self, context, mx, my):
        s = context.scene.gc_brush
        origin, direction = _ray_from_mouse(context, mx, my)
        hit, loc, nrm = _raycast_terrain(context, origin, direction, self.target)
        if not hit:
            return None

        if self.erase:
            _erase_near(self.target, loc, s.radius)
            return loc

        page = _page_of(self.target)
        t, b = _tangent_basis(nrm)
        world_points, sizes, rots = [], [], []

        # candidate positions on the tangent disk. Single = just the centre;
        # otherwise Poisson-ish dart throwing so cards don't clump.
        if s.single:
            candidates = [loc]
        else:
            min_dist = (0.85 * s.radius / math.sqrt(s.density)) if s.density > 0 else 0.0
            candidates = []
            budget = s.density * 12
            tries = 0
            while len(candidates) < s.density and tries < budget:
                tries += 1
                ang = random.uniform(0.0, math.tau)
                rr = s.radius * math.sqrt(random.random())
                cand = loc + (t * math.cos(ang) + b * math.sin(ang)) * rr
                if all((cand - c).length >= min_dist for c in candidates):
                    candidates.append(cand)

        for cand in candidates:
            if s.single:
                sloc, snrm = loc, nrm
            else:
                shit, sloc, snrm = _raycast_terrain(context, cand + nrm, -nrm, self.target)
                if not shit:
                    continue
            if s.align_mode == 'AVERAGE':
                use_n = nrm                 # one normal for the whole dab
            elif s.align_mode == 'NORMAL':
                use_n = snrm
            else:
                use_n = _WORLD_UP
            w, h = _card_size(s)
            world_points.append(sloc)
            sizes.append((w, h))
            rots.append(_card_rotation(use_n, s.align_mode, s.random_yaw))
        _append_points(self.target, world_points, sizes, rots, page)
        return loc

    def invoke(self, context, event):
        obj = context.active_object
        if not is_instancer(obj):
            self.report({'WARNING'},
                        "Select a groundcover instancer first "
                        "(a Quadtree point cloud; requires light-mode import)")
            return {'CANCELLED'}
        self.target = obj
        s = context.scene.gc_brush
        self.erase = (s.paint_mode == 'ERASE') != self.invert   # Ctrl inverts
        self._last = self._dab(context, event.mouse_region_x, event.mouse_region_y)
        self._last_time = time.monotonic()
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            origin, direction = _ray_from_mouse(
                context, event.mouse_region_x, event.mouse_region_y)
            hit, loc, nrm = _raycast_terrain(context, origin, direction, self.target)
            if hit:
                s = context.scene.gc_brush
                now = time.monotonic()
                moved = self._last is None or (loc - self._last).length >= s.spacing
                timed = (now - self._last_time) >= (1.0 / max(s.flow, 0.001))
                if moved and timed:
                    self._last = self._dab(
                        context, event.mouse_region_x, event.mouse_region_y)
                    self._last_time = now
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            return {'FINISHED'}
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


# ------------------------------------------------------------------ tool

class GC_WT_vegetation_paint(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = "gc.vegetation_paint"
    bl_label = "Vegetation Paint"
    bl_description = ("Paint groundcover onto the surface under the cursor.\n"
                      "Ctrl-drag inverts the Paint/Erase mode")
    bl_icon = "brush.generic"
    bl_widget = None
    bl_keymap = (
        ("gc.paint", {"type": 'LEFTMOUSE', "value": 'PRESS'},
         {"properties": [("invert", False)]}),
        ("gc.paint", {"type": 'LEFTMOUSE', "value": 'PRESS', "ctrl": True},
         {"properties": [("invert", True)]}),
    )

    def draw_settings(context, layout, tool):
        s = context.scene.gc_brush
        if not is_instancer(context.active_object):
            layout.label(text="Select an instancer", icon='ERROR')
        layout.prop(s, "paint_mode", text="")
        row = layout.row(align=True)
        row.prop(s, "radius")
        row.prop(s, "density")
        row.prop(s, "single", text="", icon='DECORATE')
        row = layout.row(align=True)
        row.prop(s, "spacing")
        row.prop(s, "flow")
        row = layout.row(align=True)
        row.prop(s, "align_mode", text="")
        row.prop(s, "random_yaw", text="", icon='FILE_REFRESH')
        row = layout.row(align=True)
        row.prop(s, "size_mode", text="")
        row.prop(s, "size_min")
        row.prop(s, "size_max")
        if s.size_mode == 'NONUNIFORM':
            row = layout.row(align=True)
            row.prop(s, "height_min")
            row.prop(s, "height_max")

    def draw_cursor(context, tool, xy):
        _draw_brush_ring(context, xy)


def register():
    bpy.utils.register_class(GC_OT_paint)
    bpy.utils.register_tool(GC_WT_vegetation_paint,
                            after={"builtin.transform"}, separator=True, group=False)


def unregister():
    bpy.utils.unregister_tool(GC_WT_vegetation_paint)
    bpy.utils.unregister_class(GC_OT_paint)
