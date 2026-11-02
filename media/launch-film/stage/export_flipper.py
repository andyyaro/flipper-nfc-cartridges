"""Straighten the Flipper Zero model, give its screen real UVs, split the moving parts, and export a GLB for three.js.

    blender -b --factory-startup --disable-autoexec \
        <Flipper.blend> --python stage/export_flipper.py -- assets/models/flipper.glb

The source mesh is posed at an angle. Its screen faces give the device's own axes: the screen's long side (towards
the D-pad) becomes +X, the screen's up becomes +Y and the screen's normal +Z (glTF axes); the device is centred on
its bounding box. The screen faces get planar UVs over their own extent (the source shader projected a video
instead). The D-pad ring, the back button and the LED become their own objects (origin at their centre) so the
stage can press and light them. Materials keep their names; stage/stage.html rebuilds them (the source uses Cycles
node groups that glTF cannot carry).
"""
import bpy, bmesh, mathutils, sys
import numpy as np

out = sys.argv[sys.argv.index("--") + 1]
o = bpy.data.objects["flipper_Model"]
names = [s.material.name for s in o.material_slots]
for x in list(bpy.data.objects):
    if x is not o:
        bpy.data.objects.remove(x)
bpy.context.view_layer.objects.active = o; o.select_set(True)
me = o.data
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()

scr = [f for f in bm.faces if names[f.material_index] == "Flipper_Screen"]
pts = np.array([tuple(v.co) for f in scr for v in f.verts])
c = mathutils.Vector(pts.mean(0))
n = sum((f.normal * f.calc_area() for f in scr), mathutils.Vector()).normalized()
P = pts - np.array(c); N = np.array(n); P = P - np.outer(P @ N, N)
w, V = np.linalg.eigh(P.T @ P)
major = mathutils.Vector(V[:, 2]).normalized()
dpad = mathutils.Vector((0.0, 0.0, 0.0)); k = 0
for f in bm.faces:   # orient the long axis towards the D-pad (orange, right of the screen)
    if names[f.material_index] == "Flipper_Orange":
        dpad += f.calc_center_median(); k += 1
if (dpad / k - c).dot(major) < 0:
    major = -major
minor = n.cross(major).normalized()
# Blender axes: major -> X, minor -> Z, normal -> -Y  (the glTF exporter turns that into X, Y, Z)
R = mathutils.Matrix(((*major, 0), (*(-n), 0), (*minor, 0), (0, 0, 0, 1)))
bm.transform(R @ mathutils.Matrix.Translation(-c))
xs = np.array([tuple(v.co) for v in bm.verts]); mid = (xs.min(0) + xs.max(0)) / 2
bm.transform(mathutils.Matrix.Translation(-mathutils.Vector(mid)))
print("device size (x, depth, y):", tuple(np.round(xs.max(0) - xs.min(0), 4)), "centre offset", tuple(np.round(mid, 4)))

uv = bm.loops.layers.uv.active
sp = np.array([tuple(v.co) for f in scr for v in f.verts])
u0, u1, v0, v1 = sp[:, 0].min(), sp[:, 0].max(), sp[:, 2].min(), sp[:, 2].max()
for f in scr:
    for l in f.loops:
        l[uv].uv = ((l.vert.co.x - u0) / (u1 - u0), (l.vert.co.z - v0) / (v1 - v0))
print("screen rect (x, y):", round(u0, 4), round(u1, 4), round(v0, 4), round(v1, 4), "size", round(u1 - u0, 4), round(v1 - v0, 4),
      "front z", round(-sp[:, 1].min(), 4))
bm.to_mesh(me); bm.free(); me.update()


def islands(mat):
    b = bmesh.new(); b.from_mesh(me); b.faces.ensure_lookup_table()
    fs = set(f.index for f in b.faces if names[f.material_index] == mat); res = []
    while fs:
        st = [fs.pop()]; isl = [st[0]]
        while st:
            fi = st.pop()
            for e in b.faces[fi].edges:
                for g in e.link_faces:
                    if g.index in fs: fs.remove(g.index); st.append(g.index); isl.append(g.index)
        cen = sum((b.faces[i].calc_center_median() for i in isl), mathutils.Vector()) / len(isl)
        res.append((isl, cen))
    b.free()
    return res


def split(face_ids, name):
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.context.tool_settings.mesh_select_mode = (False, False, True)
    eb = bmesh.from_edit_mesh(me)
    for v in eb.verts: v.select_set(False)
    for e in eb.edges: e.select_set(False)
    for f in eb.faces: f.select_set(False)
    eb.faces.ensure_lookup_table()
    for i in face_ids: eb.faces[i].select_set(True)
    eb.select_flush_mode(); bmesh.update_edit_mesh(me)
    bpy.ops.mesh.separate(type="SELECTED")
    bpy.ops.object.mode_set(mode="OBJECT")
    new = [x for x in bpy.context.selected_objects if x is not o][0]
    new.name = name; new.data.name = name
    new.select_set(False); o.select_set(True); bpy.context.view_layer.objects.active = o
    return new


orange = islands("Flipper_Orange")
ring = max(orange, key=lambda t: len(t[0]))                                     # the biggest orange piece: the D-pad
back = min((t for t in orange if t[1].x > ring[1].x + 0.08 and t[1].z < ring[1].z - 0.03), key=lambda t: (t[1] - ring[1]).length)
led = islands("Flipper_Green")[0]
print("dpad centre", tuple(round(x, 4) for x in ring[1]), "back centre", tuple(round(x, 4) for x in back[1]), "led", tuple(round(x, 4) for x in led[1]))
# split in descending face-index order is not needed: each split re-reads the islands of what is left
parts = {}
parts["dpad"] = split(set(ring[0]), "dpad")
back2 = [t for t in islands("Flipper_Orange") if (t[1] - back[1]).length < 1e-4][0]
parts["back_button"] = split(set(back2[0]), "back_button")
parts["led"] = split(set(islands("Flipper_Green")[0][0]), "led")
scr_ids = set(p.index for p in me.polygons if names[p.material_index] == "Flipper_Screen")
parts["screen"] = split(scr_ids, "screen")
o.name = "body"; o.data.name = "body"
for name, x in parts.items():
    bpy.ops.object.select_all(action="DESELECT"); x.select_set(True); bpy.context.view_layer.objects.active = x
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    print("part", name, "origin", tuple(round(v, 4) for v in x.location), "faces", len(x.data.polygons))
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=True, export_yup=True, export_apply=True,
                          export_cameras=False, export_lights=False)
print("wrote", out)
