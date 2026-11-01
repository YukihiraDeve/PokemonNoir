"""Construit les scènes 3D du jeu dans Blender et les exporte en GLB.

À lancer dans Blender (onglet Scripting, ou via le MCP Blender) :
    exec(compile(open(p).read(), p, "exec"), {"__file__": p})
avec p = chemin de ce fichier.

- Scène « Library »      : les 68 modèles du Stylized Nature MegaKit, les pièces du Medieval
                            Village MegaKit (maisons) et quelques modèles Kenney, rangés en grille.
- Scène « Battle_Forest » : clairière de combat → public/assets/scenes/battle-forest.glb
- Scène « Route_01 »      : Renouet, la Route 1 et Arabelle, d'après la grille de tools/maps
                            → public/assets/scenes/route-01.glb (+ route-01.json pour le jeu)
- Scène « Interior_Center » : intérieur du Centre Pokémon (soins, PC, comptoir de la boutique)
                            → public/assets/scenes/center.glb

Les objets placés sont des copies liées des modèles de la Library (même maillage).
Repères lus par le jeu (objets vides, nom dans la propriété « marker ») : Spawn_*, NPC_*, Door_*
(vers une autre carte : target, spawn, dir, arrive), Sign_*, Area_*, Bounds. Propriétés
personnalisées : « collider » (rayon en m) sur les obstacles ronds, « solid » sur les bâtiments
(boîte englobante).
"""
import math
import os
import random
import re

import bmesh
import bpy
from mathutils import Euler, Vector, noise

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
KIT = os.path.join(ROOT, "public/assets/environment/quaternius_stylized-nature-megakit/glTF")
TOWN_KIT = os.path.join(ROOT, "public/assets/environment/kenney_city-kit-suburban/Models/GLB format")
VILLAGE_KIT = os.path.join(ROOT, "public/assets/environment/quaternius_medieval-village-megakit/glTF")
TOWN_MODELS = ["planter"]  # bacs à plantes des intérieurs (Kenney)
TEXTURES = os.path.join(ROOT, "public/assets/environment/textures")
OUT = os.path.join(ROOT, "public/assets/scenes")
BLEND = os.path.join(ROOT, "blender/scenes.blend")

TREES = [("CommonTree_1", 6), ("CommonTree_2", 6), ("CommonTree_3", 4), ("CommonTree_4", 6),
         ("CommonTree_5", 6), ("Pine_1", 1), ("Pine_2", 1), ("Pine_4", 1), ("TwistedTree_3", 1)]
# Les arbres tordus du kit font ~16 m de haut : on les ramène à la taille des autres.
TREE_SCALE = {"TwistedTree_3": 0.5}


# ---------------------------------------------------------------- bibliothèque

def ensure_library():
    lib = bpy.data.scenes.get("Library") or bpy.data.scenes.new("Library")
    coll = bpy.data.collections.get("Library")
    if coll is None:
        coll = bpy.data.collections.new("Library")
        lib.collection.children.link(coll)
    bpy.context.window.scene = lib
    for f in sorted(os.listdir(KIT)):
        name = f[:-5]
        if f.endswith(".gltf") and name not in bpy.data.objects:
            bpy.ops.import_scene.gltf(filepath=os.path.join(KIT, f))
    for name in TOWN_MODELS:
        if name not in bpy.data.objects:
            bpy.ops.import_scene.gltf(filepath=os.path.join(TOWN_KIT, f"{name}.glb"))
    for name in sorted(kit_names(VILLAGE_KIT)):
        if name not in bpy.data.objects:
            bpy.ops.import_scene.gltf(filepath=os.path.join(VILLAGE_KIT, f"{name}.gltf"))
    library = kit_names() | set(TOWN_MODELS) | kit_names(VILLAGE_KIT)
    meshes = sorted((o for o in bpy.data.objects if o.type == "MESH" and o.name in library), key=lambda o: o.name)
    for i, o in enumerate(meshes):
        for c in list(o.users_collection):
            if c != coll:
                c.objects.unlink(o)
        if coll not in o.users_collection:
            coll.objects.link(o)
        o.data.name = o.name
        o.location = ((i % 10) * 8.0, (i // 10) * 8.0, 0)
    # Chaque import recrée ses matériaux : on fusionne « Leaves.001 » dans « Leaves », etc.
    for datablocks in (bpy.data.images, bpy.data.materials):
        for item in list(datablocks):
            base = re.sub(r"\.\d{3}$", "", item.name)
            if base != item.name and base in datablocks:
                item.user_remap(datablocks[base])
                datablocks.remove(item)


def kit_names(folder=KIT):
    return {f[:-5] for f in os.listdir(folder) if f.endswith(".gltf")}


def village_materials():
    """Variantes des matériaux du Medieval Village MegaKit : tuiles bleues (maisons de Renouet),
    bois clair (bardage), vitres opaques bleutées (le verre du kit est presque transparent)."""
    for src, dst, image in (("MI_RoundTiles", "MI_RoundTiles_Blue", "T_RoundTiles_BaseColor_Blue.png"),
                            ("MI_WoodTrim", "MI_WoodTrim_Light", "T_WoodTrim_BaseColor_Light.png"),
                            ("MI_RedBrick", "MI_RedBrick_Dark", "T_RedBrick_BaseColor_Dark.png")):
        mat = bpy.data.materials.get(dst)
        if mat is None:
            mat = bpy.data.materials[src].copy()
            mat.name = dst
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image and "BaseColor" in node.image.name:
                node.image = bpy.data.images.load(os.path.join(VILLAGE_KIT, image), check_existing=True)
    glass = bpy.data.materials["MI_WindowGlass"]
    bsdf = next(n for n in glass.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.16, 0.27, 0.4, 1)
    bsdf.inputs["Alpha"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.12
    bsdf.inputs["Metallic"].default_value = 0.3
    for link in list(glass.node_tree.links):
        if link.to_socket == bsdf.inputs["Alpha"]:
            glass.node_tree.links.remove(link)


def green_foliage():
    """Le feuillage des buissons et arbres tordus est un masque rouge (teinté par le shader
    Unity du kit) : on le remplace par la version verte de generate_textures.py."""
    green = bpy.data.images.load(os.path.join(TEXTURES, "leaves-green.png"), check_existing=True)
    for node in bpy.data.materials["Leaves_TwistedTree"].node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image and node.image.name.startswith("Leaves_TwistedTree"):
            node.image = green


# ---------------------------------------------------------------- outils

def fresh_scene(name):
    old = bpy.data.scenes.get(name)
    if old:
        for o in list(old.collection.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.scenes.remove(old)
    scene = bpy.data.scenes.new(name)
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    return scene


def pixel_material(name, texture, roughness=1.0, alpha=False, emission=None):
    """Matériau à texture pixel art : filtrage « Closest » → NEAREST dans le glTF. `alpha` :
    la transparence de l'image découpe la surface (décalcomanies). `emission` : (texture,
    intensité), parties qui éclairent d'elles-mêmes (vitrages allumés)."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(TEXTURES, texture), check_existing=True)
    tex.interpolation = "Closest"
    bsdf.inputs["Roughness"].default_value = roughness
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if alpha:
        links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    if emission:
        glow = nodes.new("ShaderNodeTexImage")
        glow.image = bpy.data.images.load(os.path.join(TEXTURES, emission[0]), check_existing=True)
        glow.interpolation = "Closest"
        links.new(glow.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = emission[1]
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def place(coll, model, x, y, z, rot=None, scale=1.0, name=None, collider=None):
    obj = bpy.data.objects.new(name or model, bpy.data.objects[model].data)
    obj.location = (x, y, z)
    obj.rotation_euler = (0, 0, rot if rot is not None else random.uniform(0, math.tau))
    obj.scale = (scale, scale, scale)
    if collider:
        obj["collider"] = round(collider * scale, 2)
    coll.objects.link(obj)
    return obj


def marker(coll, name, x, y, z, size=(0.5, 0.5, 0.5), **props):
    obj = bpy.data.objects.new(name, None)
    # Les noms d'objets sont uniques dans tout le .blend (« Bounds.001 » dans la 2e scène) :
    # le nom voulu est aussi rangé dans une propriété, exportée avec l'objet.
    obj["marker"] = name
    obj.empty_display_type = "CUBE"
    obj.location = (x, y, z)
    obj.scale = size
    for k, v in props.items():
        obj[k] = v
    coll.objects.link(obj)
    return obj


def weighted(choices):
    return random.choices([c for c, _ in choices], weights=[w for _, w in choices])[0]


def scatter(count, sample, ok, min_dist, taken=None):
    """Points aléatoires acceptés par ok(x, y), espacés d'au moins min_dist."""
    pts = [] if taken is None else taken
    start, tries = len(pts), 0
    while len(pts) - start < count and tries < count * 200:
        tries += 1
        x, y = sample()
        if ok(x, y) and all((x - px) ** 2 + (y - py) ** 2 >= min_dist ** 2 for px, py in pts):
            pts.append((x, y))
    return pts[start:]


def smoothstep(a, b, v):
    t = min(1.0, max(0.0, (v - a) / (b - a)))
    return t * t * (3 - 2 * t)


def ground(coll, name, size, center, res, height, mat, tile=3.0):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=res, y_segments=res, size=size / 2)
    for v in bm.verts:
        v.co.x += center[0]
        v.co.y += center[1]
        v.co.z = height(v.co.x, v.co.y)
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for loop in f.loops:
            loop[uv].uv = (loop.vert.co.x / tile, loop.vert.co.y / tile)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    return obj


def flat_shape(coll, name, outline, z, mat, tile=3.0):
    """Surface plate (terre) à partir d'un contour, triangulée en éventail depuis son centre."""
    bm = bmesh.new()
    verts = [bm.verts.new((x, y, z)) for x, y in outline]
    face = bm.faces.new(verts)
    bmesh.ops.poke(bm, faces=[face])
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for loop in f.loops:
            loop[uv].uv = (loop.vert.co.x / tile, loop.vert.co.y / tile)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    return obj


def blob_outline(cx, cy, radius, seed, n=44):
    rng = random.Random(seed)
    pts = []
    for i in range(n):
        a = math.tau * i / n
        r = radius * (1 + 0.08 * math.sin(3 * a + seed) + rng.uniform(-0.05, 0.05))
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def strip_outline(x0, x1, y0, y1, step=0.45, jitter=0.18, seed=0):
    """Rectangle aux bords irréguliers (bord de chemin « mordu » par l'herbe)."""
    rng = random.Random(seed)
    j = lambda: rng.uniform(-jitter, jitter)
    pts = []
    n_y, n_x = max(2, int((y1 - y0) / step)), max(2, int((x1 - x0) / step))
    pts += [(x1 + j(), y0 + (y1 - y0) * i / n_y) for i in range(n_y)]
    pts += [(x1 - (x1 - x0) * i / n_x, y1 + j()) for i in range(n_x)]
    pts += [(x0 + j(), y1 - (y1 - y0) * i / n_y) for i in range(n_y)]
    pts += [(x0 + (x1 - x0) * i / n_x, y0 + j()) for i in range(n_x)]
    return pts


def camera(coll, name, pos, target, lens):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    cam.data.lens = lens
    cam.data.clip_end = 300
    cam.location = pos
    cam.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(cam)
    return cam


def color_material(name, color, roughness=0.8, metallic=0.0, emission=None):
    """Matériau uni ; `emission` : (couleur, intensité) d'une surface lumineuse."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission[0], 1)
        bsdf.inputs["Emission Strength"].default_value = emission[1]
    return mat


def box(coll, name, cx, cy, z0, w, d, h, mat, tile=3.0, solid=False):
    """Pavé w×d×h posé en z0, UV projetées dans le repère du monde (textures raccordées)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((cx + v.co.x * w, cy + v.co.y * d, z0 + (v.co.z + 0.5) * h))
    bm.normal_update()
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        n = f.normal
        for loop in f.loops:
            c = loop.vert.co
            u, v = (c.x, c.y) if abs(n.z) > 0.5 else (c.y, c.z) if abs(n.x) > 0.5 else (c.x, c.z)
            loop[uv].uv = (u / tile, v / tile)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    if solid:
        obj["solid"] = 1
    coll.objects.link(obj)
    return obj


def front_plane(coll, name, cx, y, zc, w, h, mat):
    """Panneau vertical tourné vers le sud (la caméra), UV de 0 à 1 : enseignes."""
    bm = bmesh.new()
    verts = [bm.verts.new((cx + dx * w / 2, y, zc + dz * h / 2)) for dx, dz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    face = bm.faces.new(verts)
    uv = bm.loops.layers.uv.new("UVMap")
    for loop, coords in zip(face.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop[uv].uv = coords
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    return obj


def cylinder(coll, name, cx, cy, z0, radius, h, mat, segments=28):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius, depth=h)
    for v in bm.verts:
        v.co = Vector((cx + v.co.x, cy + v.co.y, z0 + h / 2 + v.co.z))
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for loop in f.loops:
            loop[uv].uv = (loop.vert.co.x / 1.5, (loop.vert.co.y + loop.vert.co.z) / 1.5)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    return obj


def signpost(coll, name, x, y, text):
    wood = color_material("Town_Wood", (0.36, 0.2, 0.08))
    post = box(coll, f"{name}_Post", x, y, 0, 0.16, 0.16, 1.0, wood)
    post["collider"] = 0.35
    box(coll, f"{name}_Board", x, y, 0.75, 1.3, 0.12, 0.7, wood)
    marker(coll, name, x, y, 0, text=text)


# ---------------------------------------------------------------- Centre Pokémon

def chamfered(x0, x1, y0, y1, c, square=""):
    """Rectangle aux angles coupés, sens trigonométrique. `square` : côtés dont les angles
    restent droits ("w" ouest, "e" est) — ceux qui s'appuient sur un autre volume."""
    cw = 0 if "w" in square else c
    ce = 0 if "e" in square else c
    pts = [(x0 + cw, y0), (x1 - ce, y0), (x1, y0 + ce), (x1, y1 - ce), (x1 - ce, y1), (x0 + cw, y1), (x0, y1 - cw),
           (x0, y0 + cw)]
    out = []
    for p in pts:  # sommets confondus quand un angle reste droit
        if not out or (Vector(p) - Vector(out[-1])).length > 1e-6:
            out.append(p)
    if (Vector(out[0]) - Vector(out[-1])).length < 1e-6:
        out.pop()
    return [Vector(p) for p in out]


def offset_poly(poly, d):
    """Contour décalé de d vers l'extérieur (d < 0 : vers l'intérieur), angles en onglet."""
    out = []
    for i, p1 in enumerate(poly):
        p0, p2 = poly[i - 1], poly[(i + 1) % len(poly)]
        e1, e2 = (p1 - p0).normalized(), (p2 - p1).normalized()
        n1, n2 = Vector((e1.y, -e1.x)), Vector((e2.y, -e2.x))
        m = (n1 + n2).normalized()
        out.append(p1 + m * (d / max(0.3, m.dot(n1))))
    return out


class Builder:
    """Maillages regroupés par matériau : un objet par matériau à la fin (peu d'objets)."""

    def __init__(self, name):
        self.name, self.parts = name, {}

    def bm(self, mat):
        if mat.name not in self.parts:
            bm = bmesh.new()
            self.parts[mat.name] = (mat, bm, bm.loops.layers.uv.new("UVMap"))
        return self.parts[mat.name]

    def loft(self, mat, lo, hi, z0, z1, bay=None, skip=()):
        """Faces entre deux contours (murs, pentes) ; `bay` : largeur d'une travée de texture,
        la texture couvre toute la hauteur."""
        _, bm, uv = self.bm(mat)
        u = 0.0
        for i in range(len(lo)):
            j = (i + 1) % len(lo)
            length = (lo[j] - lo[i]).length
            if i not in skip:
                quad = [(lo[i], z0), (lo[j], z0), (hi[j], z1), (hi[i], z1)]
                f = bm.faces.new([bm.verts.new((p.x, p.y, z)) for p, z in quad])
                coords = [(u, 0), (u + length, 0), (u + length, 1), (u, 1)]
                for loop, (cu, cv) in zip(f.loops, coords):
                    loop[uv].uv = (cu / bay, cv) if bay else (cu / 3, cv)
            u += length

    def ring(self, mat, poly, z0, z1, out0=0.0, out1=None, bay=None, skip=()):
        self.loft(mat, offset_poly(poly, out0), offset_poly(poly, out0 if out1 is None else out1), z0, z1, bay, skip)

    def cap(self, mat, poly, z, flip=False):
        _, bm, uv = self.bm(mat)
        f = bm.faces.new([bm.verts.new((p.x, p.y, z)) for p in poly])
        if flip:
            f.normal_flip()
        for loop in f.loops:
            loop[uv].uv = (loop.vert.co.x / 3, loop.vert.co.y / 3)
        bmesh.ops.triangulate(bm, faces=[f])

    def quad(self, mat, pts, uvs):
        _, bm, uv = self.bm(mat)
        f = bm.faces.new([bm.verts.new(p) for p in pts])
        for loop, t in zip(f.loops, uvs):
            loop[uv].uv = t
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()

    def face(self, mat, pts):
        _, bm, uv = self.bm(mat)
        f = bm.faces.new([bm.verts.new(p) for p in pts])
        for loop in f.loops:
            loop[uv].uv = (loop.vert.co.x / 3, loop.vert.co.z / 3)
        return f

    def box(self, mat, cx, cy, z0, w, d, h):
        x0, x1, y0, y1, z1 = cx - w / 2, cx + w / 2, cy - d / 2, cy + d / 2, z0 + h
        for pts in (((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)),
                    ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)),
                    ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)),
                    ((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)),
                    ((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1))):
            self.face(mat, pts)

    def build(self, coll, solid=()):
        for key, (mat, bm, _) in self.parts.items():
            mesh = bpy.data.meshes.new(f"{self.name}_{key}")
            bm.normal_update()
            bm.to_mesh(mesh)
            bm.free()
            mesh.materials.append(mat)
            obj = bpy.data.objects.new(f"{self.name}_{key}", mesh)
            coll.objects.link(obj)
            if key in solid:
                obj["solid"] = 1


def arch_tube(b, mat, cx, y, z, radius, width=0.3, depth=0.34, segments=7):
    """Arche blanche à facettes (demi-polygone vertical, section rectangulaire) dans le plan y."""
    path = [(cx - radius * math.cos(math.pi * k / segments), z + radius * math.sin(math.pi * k / segments))
            for k in range(segments + 1)]
    rings = []
    for k, (x, zz) in enumerate(path):
        a = path[max(0, k - 1)]
        c = path[min(segments, k + 1)]
        t = Vector((c[0] - a[0], c[1] - a[1])).normalized()
        n = Vector((-t.y, t.x))  # vers l'extérieur de l'arche
        rings.append([(x + n.x * sx * width / 2, y + sy * depth / 2, zz + n.y * sx * width / 2)
                      for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(4):
            j = (i + 1) % 4
            b.face(mat, [r0[i], r0[j], r1[j], r1[i]])
    b.face(mat, rings[0][::-1])
    b.face(mat, rings[-1])


def pokemon_center(coll, cx, fy, scale=0.68):
    """Centre Pokémon de Noir et Blanc : bloc central à angles coupés sur deux niveaux, ailes
    basses à l'est et à l'ouest, vitrages bleus, liseré jaune-blanc-bleu, jupe et toit rouges,
    voûte à pans sur le toit, entrée en demi-octogone avec auvent rouge et arche blanche.
    Construit aux proportions du modèle de référence, puis réduit de `scale` autour du milieu de
    la façade pour s'accorder aux maisons et aux personnages. `fy` : façade sud. Renvoie le y du
    seuil de l'entrée."""
    before = set(coll.objects)
    red = color_material("PCExt_Red", (0.52, 0.055, 0.014), roughness=0.75)
    red_dark = color_material("PCExt_RedDark", (0.26, 0.025, 0.008), roughness=0.8)
    plinth = color_material("PCExt_Plinth", (0.045, 0.045, 0.05), roughness=0.8)
    navy = color_material("PCExt_Navy", (0.015, 0.025, 0.08), roughness=0.6)
    blue = color_material("PCExt_Blue", (0.09, 0.24, 0.78), roughness=0.4)
    white = color_material("PCExt_White", (0.85, 0.86, 0.9), roughness=0.35)
    yellow = color_material("PCExt_Yellow", (0.86, 0.68, 0.16), roughness=0.4)
    trim = color_material("PCExt_Trim", (0.6, 0.77, 0.9), roughness=0.4)
    grey = color_material("PCExt_Grey", (0.4, 0.41, 0.45), roughness=0.5)
    dark = color_material("PCExt_Dark", (0.01, 0.01, 0.012), roughness=0.9)
    # Vitrages éclairés de l'intérieur, sas baigné de la même lumière bleutée.
    glass_low = pixel_material("PCExt_GlassLow", "center-glass-low.png", roughness=0.35,
                               emission=("center-glass-low-glow.png", 0.55))
    glass_high = pixel_material("PCExt_GlassHigh", "center-glass-high.png", roughness=0.35,
                                emission=("center-glass-high-glow.png", 0.55))
    interior = color_material("PCExt_Interior", (0.03, 0.045, 0.07), roughness=0.9, emission=((0.42, 0.62, 0.85), 0.55))
    b = Builder("PokemonCenter")

    W, D = 8.6, 6.6
    # Hauteurs : socle, vitrage du bas, liseré, jupe rouge, vitrage de l'étage, toit.
    z_glass, z_stripes, z_skirt, z_up, z_trim, z_roof, z_top = 0.3, 3.0, 3.42, 4.4, 6.6, 6.7, 7.7
    main = chamfered(cx - W / 2, cx + W / 2, fy, fy + D, 1.0)
    wings = [(chamfered(cx + W / 2 - 0.3, cx + W / 2 + 2.0, fy + 0.7, fy + D - 0.7, 0.8, square="w"), "w"),
             (chamfered(cx - W / 2 - 2.0, cx - W / 2 + 0.3, fy + 0.7, fy + D - 0.7, 0.8, square="e"), "e")]
    vest = [Vector(p) for p in ((cx - 1.9, fy + 0.3), (cx - 1.9, fy - 0.75), (cx - 1.25, fy - 1.7),
                                (cx + 1.25, fy - 1.7), (cx + 1.9, fy - 0.75), (cx + 1.9, fy + 0.3))]
    inner = lambda poly, side: [i for i in range(len(poly)) if
                                abs(poly[i].x - poly[(i + 1) % len(poly)].x) < 1e-6 and
                                (poly[i].x - cx) * (1 if side == "w" else -1) < W / 2]

    def ground_floor(poly, skip=()):
        b.ring(plinth, poly, 0.0, z_glass, 0.06, skip=skip)
        b.ring(glass_low, poly, z_glass, z_stripes, bay=1.25, skip=skip)
        stripes(poly, skip)

    def stripes(poly, skip=()):
        for mat, z0, z1, out in ((yellow, 0.0, 0.11, 0.03), (white, 0.11, 0.23, 0.05), (blue, 0.23, 0.34, 0.07),
                                 (navy, 0.34, 0.42, 0.09)):
            b.ring(mat, poly, z_stripes + z0, z_stripes + z1, out, skip=skip)

    def hip(poly, z, rise, inset, skip=()):
        """Toit rouge : bandeau vertical débordant puis pente jusqu'à un dessus plat."""
        b.ring(red, poly, z, z + 0.22, 0.4, skip=skip)
        b.loft(red, offset_poly(poly, 0.4), offset_poly(poly, -inset), z + 0.22, z + rise, skip=skip)
        b.cap(red, offset_poly(poly, -inset), z + rise)

    # Bloc central : rez-de-chaussée, jupe rouge, étage vitré, toit.
    ground_floor(main)
    b.ring(red, main, z_skirt, z_skirt + 0.24, 0.45)
    b.loft(red, offset_poly(main, 0.45), main, z_skirt + 0.24, z_up)
    b.ring(glass_high, main, z_up, z_trim, bay=0.95)
    b.ring(trim, main, z_trim, z_roof, 0.04)
    b.ring(red, main, z_roof, z_roof + 0.25, 0.35)
    top = offset_poly(main, -1.0)
    b.loft(red, offset_poly(main, 0.35), top, z_roof + 0.25, z_top)
    b.cap(red, top, z_top)
    # Emblème centré sur la bande claire (rangées 20 à 29 des 72 de la texture, depuis le haut).
    front_plane(coll, "PokemonCenter_Emblem", cx, fy - 0.03, z_trim - (z_trim - z_up) * 24.5 / 72, 1.75, 1.75,
                pixel_material("Decal_CenterEmblem", "center-emblem.png", roughness=0.4, alpha=True))
    # Ailes basses (un niveau) de part et d'autre.
    for poly, side in wings:
        skip = inner(poly, side)
        ground_floor(poly, skip)
        hip(poly, z_skirt, 0.85, 0.6, skip)
    # Voûte à pans sur le toit, ouverte en façade.
    ya, yb, R = fy + 2.1, fy + D - 1.3, 1.75
    prof = [(R * math.cos(a), 0.92 * R * math.sin(a)) for a in (0, 0.7, 1.25, math.pi - 1.25, math.pi - 0.7, math.pi)]
    for (x0, z0), (x1, z1) in zip(prof, prof[1:]):
        b.face(red, [(cx + x0, ya, z_top + z0), (cx + x1, ya, z_top + z1), (cx + x1, yb, z_top + z1), (cx + x0, yb, z_top + z0)])
    b.face(red, [(cx + x, yb, z_top + z) for x, z in prof])
    # Façade de la voûte : cadre rouge, ébrasement plus sombre, ouverture noire sous un linteau gris.
    for k0, k1, mat, depth in ((1.0, 0.8, red, 0.0), (0.8, 0.64, red_dark, 0.16)):
        for (x0, z0), (x1, z1) in zip(prof, prof[1:]):
            b.face(mat, [(cx + x0 * k0, ya, z_top + z0 * k0), (cx + x1 * k0, ya, z_top + z1 * k0),
                         (cx + x1 * k1, ya + depth, z_top + z1 * k1), (cx + x0 * k1, ya + depth, z_top + z0 * k1)])
    b.face(grey, [(cx + x * 0.64, ya + 0.18, z_top + z * 0.64) for x, z in prof])
    b.face(dark, [(cx + x * 0.56, ya + 0.17, z_top + z * 0.5) for x, z in prof])
    # Entrée : sas en demi-octogone ouvert devant, intérieur sombre, auvent rouge, arche blanche.
    front_edge, back_edge = 2, 5
    b.ring(white, vest, 0.0, 0.12, 0.22, skip=(back_edge,))
    b.cap(white, offset_poly(vest, 0.22), 0.12)
    b.ring(white, vest, 0.12, z_stripes, skip=(front_edge, back_edge))
    lining = offset_poly(vest, -0.12)
    b.loft(dark, lining, lining, 0.13, z_stripes - 0.01, skip=(front_edge, back_edge))
    b.cap(dark, lining, 0.13)
    b.cap(dark, lining, z_stripes - 0.01, flip=True)
    # Fond du sas : les portes vitrées du hall, éclairées ; le sol du sas en reçoit la lumière.
    b.quad(glass_low, [(cx - 1.8, fy - 0.02, 0.13), (cx + 1.8, fy - 0.02, 0.13), (cx + 1.8, fy - 0.02, z_stripes),
                       (cx - 1.8, fy - 0.02, z_stripes)], [(0, 0), (3.6 / 1.25, 0), (3.6 / 1.25, 1), (0, 1)])
    b.cap(interior, offset_poly(lining, -0.02), 0.14)
    for p in (vest[2], vest[3]):
        box(coll, "PokemonCenter_Post", p.x, p.y + 0.05, 0.12, 0.32, 0.32, z_stripes - 0.1, grey)
    stripes(vest, (back_edge,))
    b.ring(red, vest, z_skirt, z_skirt + 0.22, 0.4, skip=(back_edge,))
    mid = offset_poly(vest, 0.05)
    b.loft(red, offset_poly(vest, 0.4), mid, z_skirt + 0.22, z_skirt + 0.52, skip=(back_edge,))
    b.loft(red, mid, offset_poly(vest, -0.55), z_skirt + 0.52, z_skirt + 0.7, skip=(back_edge,))
    b.cap(red, offset_poly(vest, -0.55), z_skirt + 0.7)
    arch_tube(b, white, cx, fy - 2.0, z_skirt + 0.18, 1.6)
    b.build(coll, solid=("PCExt_Plinth",))
    # Lumière des vitrages sur le sol (le jeu l'ajoute en mode additif) : une bande devant
    # chaque pan du rez-de-chaussée, une flaque plus large devant l'entrée.
    glow = Builder("Glow")
    spill = pixel_material("Glow_Spill", "light-spill.png", alpha=True)
    for poly, skip in [(main, ())] + [(poly, inner(poly, side)) for poly, side in wings]:
        base = offset_poly(poly, 0.07)
        for i, a in enumerate(base):
            if i in skip:
                continue
            c = base[(i + 1) % len(base)]
            n = Vector(((c - a).y, -(c - a).x)).normalized() * 1.6
            glow.quad(spill, [(a.x, a.y, 0.07), (c.x, c.y, 0.07), (c.x + n.x, c.y + n.y, 0.07), (a.x + n.x, a.y + n.y, 0.07)],
                      [(0, 0), (1, 0), (1, 1), (0, 1)])
    pool = pixel_material("Glow_Pool", "light-pool.png", alpha=True)
    y0 = fy - 1.7 - 0.22
    glow.quad(pool, [(cx - 2.6, y0, 0.08), (cx + 2.6, y0, 0.08), (cx + 2.6, y0 - 3.2, 0.08), (cx - 2.6, y0 - 3.2, 0.08)],
              [(0, 0), (1, 0), (1, 1), (0, 1)])
    glow.build(coll)
    # Collision du sas (le bloc et les ailes : boîte du socle).
    box(coll, "PokemonCenter_Porch", cx, fy - 0.85, 0, 3.8, 1.7, 0.01, dark, solid=True)
    pivot = Vector((cx, fy, 0))
    for obj in set(coll.objects) - before:
        if obj.type == "MESH":  # sommets en coordonnées du monde, objets à l'origine
            for v in obj.data.vertices:
                v.co = pivot + (v.co - pivot) * scale
    return fy - 1.7 * scale


# ---------------------------------------------------------------- combat

def build_battle():
    random.seed(4)
    scene = fresh_scene("Battle_Forest")
    coll = scene.collection
    grass, dirt = pixel_material("Ground_Grass", "grass.png"), pixel_material("Ground_Dirt", "dirt.png")

    C = Vector((0.0, 8.0))           # centre de la clairière
    P = Vector((-1.9, 1.0))          # Pokémon du joueur (vu de dos, en bas à gauche de l'image)
    E = Vector((1.8, 9.0))           # Pokémon adverse (au centre, un peu à droite)
    cam_pos = Vector((-1.0, -3.6))

    def height(x, y):
        r = (Vector((x, y)) - C).length
        bumps = noise.noise(Vector((x * 0.09, y * 0.09, 0.5))) * 0.6
        return smoothstep(13, 32, r) * 3.5 + bumps * smoothstep(9, 18, r)

    ground(coll, "Ground", 140, (0, 14), 70, height, grass)
    flat_shape(coll, "Pad_Player", blob_outline(P.x, P.y, 1.7, 1), 0.03, dirt)
    flat_shape(coll, "Pad_Enemy", blob_outline(E.x, E.y, 1.4, 2), 0.03, dirt)
    for pad, radius in ((P, 1.7), (E, 1.4)):
        for i in range(int(radius * 9)):
            a = math.tau * i / int(radius * 9) + random.uniform(-0.1, 0.1)
            r = radius * random.uniform(0.95, 1.12)
            place(coll, "Grass_Wispy_Short", pad.x + r * math.cos(a), pad.y + r * math.sin(a), 0,
                  scale=random.uniform(0.3, 0.45))

    near_cam = lambda x, y, d: (Vector((x, y)) - cam_pos).length < d
    ring = lambda r0, r1: (lambda: (C.x + (r := random.uniform(r0, r1)) * math.cos(a := random.uniform(0, math.tau)),
                                    C.y + r * math.sin(a)))
    dist_c = lambda x, y: (Vector((x, y)) - C).length

    # Deux couronnes d'arbres : une serrée en lisière (gros houppiers), une plus lâche derrière.
    trees = []
    for r0, r1, count, dist, (s0, s1) in ((12.5, 20, 60, 3.0, (1.4, 2.0)), (20, 42, 90, 3.8, (1.2, 1.7))):
        for x, y in scatter(count, ring(r0, r1), lambda x, y: not near_cam(x, y, 7), dist, trees):
            model = weighted(TREES)
            place(coll, model, x, y, height(x, y) - 0.1,
                  scale=TREE_SCALE.get(model, 1.0) * random.uniform(s0, s1), name="Tree")

    # Lisière dense : buissons, fougères, grandes plantes, herbes hautes.
    edge = [("Bush_Common", 5), ("Bush_Common_Flowers", 1), ("Fern_1", 3), ("Plant_1_Big", 2),
            ("Plant_7_Big", 2), ("Grass_Wispy_Tall", 1)]
    for x, y in scatter(150, ring(9.5, 16), lambda x, y: not near_cam(x, y, 5.5), 1.1):
        model = weighted(edge)
        scale = random.uniform(1.2, 2.0) if model.startswith("Bush") else random.uniform(0.8, 1.15)
        place(coll, model, x, y, height(x, y), scale=scale)

    # Rochers derrière le Pokémon adverse.
    for i, a in enumerate((70, 88, 104, 122)):
        r = random.uniform(11, 13)
        x, y = C.x + r * math.cos(math.radians(a)), C.y + r * math.sin(math.radians(a))
        place(coll, f"Rock_Medium_{i % 3 + 1}", x, y, height(x, y) - 0.4, scale=random.uniform(0.55, 0.95))

    # Sol de la clairière : herbes courtes, trèfles, fleurs, galets (hors des terrains).
    def free_floor(x, y):
        return (dist_c(x, y) < 9.5 and (Vector((x, y)) - P).length > 2.3
                and (Vector((x, y)) - E).length > 1.9 and not near_cam(x, y, 2.5))
    floor = [("Grass_Common_Short", 3), ("Clover_1", 3), ("Clover_2", 3), ("Pebble_Round_2", 1),
             ("Pebble_Round_4", 1)]
    for x, y in scatter(40, ring(4, 9.5), free_floor, 1.2):
        place(coll, weighted(floor), x, y, 0, scale=random.uniform(0.4, 0.6))

    # Premier plan : grandes fougères à droite du Pokémon du joueur (comme la référence).
    place(coll, "Fern_1", 0.9, -0.4, 0, rot=0.6, scale=0.95)
    place(coll, "Plant_7_Big", 2.6, 1.6, 0, rot=2.0, scale=0.8)
    place(coll, "Fern_1", -3.8, 2.8, 0, rot=4.0, scale=0.8)

    marker(coll, "Spawn_PlayerPokemon", P.x, P.y, 0.03)
    marker(coll, "Spawn_EnemyPokemon", E.x, E.y, 0.03)
    camera(coll, "Camera_Battle", (cam_pos.x, cam_pos.y, 1.9), (1.2, 9.5, 1.0), 26)
    return scene


# ---------------------------------------------------------------- route

# Carte décalquée de Pokémon Noir & Blanc : Renouet au sud, Route 1 (tools/maps/route-1.txt),
# puis Arabelle au nord (tools/maps/arabelle.txt, lignes négatives). Une case de la grille = une
# case du jeu (16 px) = 1,25 m.
GRID = os.path.join(ROOT, "tools/maps/route-1.txt")
TOWN_GRID = os.path.join(ROOT, "tools/maps/arabelle.txt")
TOWN_LEVELS = os.path.join(ROOT, "tools/maps/arabelle-levels.txt")
TILE = 1.25
GRID_COL0 = 19                 # colonne de la grille centrée sur x = 0
SEAWALL_ROW = 99               # digue de Renouet ; la mer est au-delà
LOWER = -1.2                   # herbe en contrebas, au bord de l'étang
POND_BED, POND_SURFACE = -2.2, -1.55
SEA_BED, SEA_SURFACE = -2.6, -1.4
# Niveaux d'Arabelle : rue principale, plateau de la maison bleue, place en contrebas.
TOWN_Z = {"0": 0.0, "U": 2.5, "D": -3.0, "p": 0.35}  # p : plateau de l'estrade
TOWN_ROWS = 34
# Rampes d'Arabelle : (colonnes, lignes de la ville, axe, hauteur au début, à la fin) ; le début
# est au nord pour l'axe y, à l'est pour l'axe x. Le talus boisé de l'ouest descend aussi vers
# l'est : sa pente s'annule contre la forêt du bord de la grille (colonne 0).
TOWN_RAMPS = [((26, 27), (5, 11), "y", TOWN_Z["U"], 0.0),    # escalier du plateau, vers le sud
              ((18, 23), (23, 24), "x", 0.0, TOWN_Z["D"])]   # escalier de la place, vers l'ouest
TALUS = ((0, 5), (14, 27), 0.0, TOWN_Z["D"])                  # colonnes, lignes, haut (nord), bas (sud)
PINES = [("Pine_1", 2), ("Pine_2", 2), ("Pine_4", 2), ("Pine_5", 3), ("CommonTree_1", 1)]
PINE_SCALE = (0.5, 0.62)
BLOCKING = set("TWCBKX")


class TileMap:
    """Grille de cases : nature du sol, niveaux (contrebas, eau, plateaux) et hauteurs.

    Route 1 et Renouet (lignes 0 et plus) : hauteurs aux coins partagées, les falaises sont des
    pentes. Arabelle (lignes négatives) : chaque case a ses propres coins, à plat ou en rampe ;
    entre deux niveaux, build_scenes.py dresse un mur vertical."""

    def __init__(self, path, town_path=None, town_levels=None):
        read = lambda f: [line for line in open(f, encoding="utf-8").read().split("\n") if line]
        self.rows = read(path)
        self.h, self.w = len(self.rows), len(self.rows[0])
        self.town = read(town_path) if town_path else []
        self.town_levels = read(town_levels) if town_levels else []
        self.r0 = len(self.town)  # lignes de la ville : de -r0 à -1
        self.corners = self._corner_heights()

    def at(self, c, r):
        if not 0 <= c < self.w:
            return "T"
        if 0 <= r < self.h:
            return self.rows[r][c]
        return self.town[r + self.r0][c] if -self.r0 <= r < 0 else "T"

    def x(self, c):
        return (c - GRID_COL0) * TILE

    def y(self, r):
        return (self.h - r) * TILE

    def tile_at(self, x, y):
        return self.at(math.floor(x / TILE + GRID_COL0), math.floor(self.h - y / TILE))

    def level(self, c, r):
        ch = self.at(c, r)
        if ch == "W":
            return SEA_BED if r > SEAWALL_ROW else POND_BED
        if ch == "l":
            return LOWER
        return None if ch in "CR" else 0.0

    def _corner_heights(self):
        hh = [[None] * (self.w + 1) for _ in range(self.h + 1)]
        for i in range(self.h + 1):
            for j in range(self.w + 1):
                levels = [self.level(j + dc, i + dr) for dr in (-1, 0) for dc in (-1, 0)
                          if 0 <= i + dr < self.h and 0 <= j + dc < self.w]
                levels = [v for v in levels if v is not None]
                hh[i][j] = max(levels) if levels else None
        # Coins au milieu d'une falaise ou d'un escalier : moyenne des coins voisins connus.
        for _ in range(6):
            for i in range(self.h + 1):
                for j in range(self.w + 1):
                    if hh[i][j] is None:
                        near = [hh[a][b] for a, b in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1))
                                if 0 <= a <= self.h and 0 <= b <= self.w and hh[a][b] is not None]
                        if near:
                            hh[i][j] = sum(near) / len(near)
        return [[v if v is not None else 0.0 for v in row] for row in hh]

    def _ramp(self, col, row):
        """Hauteur d'une rampe d'Arabelle au point (colonne, ligne de la ville), en décimales."""
        for (c0, c1), (a0, a1), axis, h0, h1 in TOWN_RAMPS:
            if c0 <= col <= c1 + 1 and a0 <= row <= a1 + 1:
                t = (row - a0) / (a1 + 1 - a0) if axis == "y" else (c1 + 1 - col) / (c1 + 1 - c0)
                return h0 + (h1 - h0) * t
        (c0, c1), (a0, a1), h0, h1 = TALUS
        if c0 <= col <= c1 + 1 and a0 <= row <= a1 + 1:
            t = (row - a0) / (a1 + 1 - a0)
            return (h0 + (h1 - h0) * t) * (col - c0) / (c1 + 1 - c0)
        return 0.0

    def town_level(self, c, r):
        """Lettre de niveau d'une case d'Arabelle (None ailleurs)."""
        return self.town_levels[r + self.r0][c] if -self.r0 <= r < 0 and 0 <= c < self.w else None

    def tile_corners(self, c, r):
        """Hauteurs des coins d'une case : (nord-ouest, sud-ouest, sud-est, nord-est)."""
        if r >= 0:
            c, r = min(max(c, 0), self.w - 1), min(r, self.h - 1)
            hh = self.corners
            return hh[r][c], hh[r + 1][c], hh[r + 1][c + 1], hh[r][c + 1]
        if r < -self.r0 or not 0 <= c < self.w:
            return 0.0, 0.0, 0.0, 0.0
        a = r + self.r0
        lv = self.town_levels[a][c]
        if lv in TOWN_Z:
            return (TOWN_Z[lv],) * 4
        return (self._ramp(c, a), self._ramp(c, a + 1), self._ramp(c + 1, a + 1), self._ramp(c + 1, a))

    def height(self, x, y):
        fc, fr = x / TILE + GRID_COL0, self.h - y / TILE
        c = min(max(math.floor(fc), 0), self.w - 1)
        r = min(max(math.floor(fr), -self.r0), self.h - 1)
        t, u = min(max(fc - c, 0), 1), min(max(fr - r, 0), 1)
        nw, sw, se, ne = self.tile_corners(c, r)
        top, bottom = nw * (1 - t) + ne * t, sw * (1 - t) + se * t
        return top * (1 - u) + bottom * u

    def all_cells(self):
        return [(c, r) for r in range(-self.r0, self.h) for c in range(self.w)]


def tile_mesh(coll, name, tm, cells, mat, uv_tile=3.0, lift=0.0, top_uv=True):
    """Une facette par case, aux hauteurs des coins (falaises en pente comprises)."""
    bm = bmesh.new()
    for c, r in cells:
        x0, x1, ys, yn = tm.x(c), tm.x(c + 1), tm.y(r + 1), tm.y(r)
        nw, sw, se, ne = tm.tile_corners(c, r)
        quad = [(x0, yn, nw), (x0, ys, sw), (x1, ys, se), (x1, yn, ne)]
        bm.faces.new([bm.verts.new((x, y, z + lift)) for x, y, z in quad])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
    bm.normal_update()
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        n = f.normal
        for loop in f.loops:
            co = loop.vert.co
            if top_uv or abs(n.z) > 0.8:
                u, v = co.x, co.y
            else:
                u, v = (co.y if abs(n.x) > abs(n.y) else co.x), co.z
            loop[uv].uv = (u / uv_tile, v / uv_tile)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    return obj


def level_walls(coll, tm, wall_mat, rock_mat):
    """Murs verticaux d'Arabelle : sur chaque côté de case plus haut que la case voisine, une
    paroi descend jusqu'à elle (pierre taupe, ou roche sous une case de falaise)."""
    parts = {}
    for c, r in tm.all_cells():
        if r >= 0:
            continue
        if tm.at(c, r) == "E" or tm.town_level(c, r) == "p":
            continue  # escaliers et estrade ont leurs propres côtés
        nw, sw, se, ne = tm.tile_corners(c, r)
        x0, x1, yn, ys = tm.x(c), tm.x(c + 1), tm.y(r), tm.y(r + 1)
        # (côté : extrémités, hauteurs de cette case, case voisine, coins correspondants chez elle)
        sides = (((x1, yn), (x1, ys), (ne, se), (c + 1, r), (0, 1)), ((x0, ys), (x1, ys), (sw, se), (c, r + 1), (0, 3)),
                 ((x0, yn), (x0, ys), (nw, sw), (c - 1, r), (3, 2)), ((x0, yn), (x1, yn), (nw, ne), (c, r - 1), (1, 2)))
        for (p, q, (ha, hb), (nc, nr), (ia, ib)) in sides:
            if not 0 <= nc < tm.w or nr < -tm.r0:
                continue
            other = tm.tile_corners(nc, nr)
            la, lb = other[ia], other[ib]
            if ha - la < 0.05 and hb - lb < 0.05:
                continue
            mat = rock_mat if tm.at(c, r) == "C" else wall_mat
            if mat.name not in parts:
                parts[mat.name] = (bmesh.new(), mat)
            bm = parts[mat.name][0]
            bm.faces.new([bm.verts.new(v) for v in ((p[0], p[1], min(ha, la)), (q[0], q[1], min(hb, lb)),
                                                     (q[0], q[1], hb), (p[0], p[1], ha))])
    for name, (bm, mat) in parts.items():
        uv = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            for loop in f.loops:
                co = loop.vert.co
                loop[uv].uv = ((co.x + co.y) / 2.5, co.z / 2.5)
        mesh = bpy.data.meshes.new(f"Wall_{name}")
        bm.to_mesh(mesh)
        bm.free()
        mesh.materials.append(mat)
        coll.objects.link(bpy.data.objects.new(f"Wall_{name}", mesh))


def water_mesh(coll, name, quads):
    """Surface d'eau (texture de vagues projetée dans le repère du monde) ; le jeu l'anime."""
    bm = bmesh.new()
    for quad in quads:
        bm.faces.new([bm.verts.new(v) for v in quad])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for loop in f.loops:
            loop[uv].uv = (loop.vert.co.x / 3.0, loop.vert.co.y / 3.0)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(pixel_material("Water", "water.png"))
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    return obj


def water_plane(coll, name, x0, x1, y0, y1, z):
    return water_mesh(coll, name, [((x0, y1, z), (x0, y0, z), (x1, y0, z), (x1, y1, z))])


def foam_strips(coll, name, tm, width=0.38):
    """Écume le long des berges : une bande par côté de case d'eau qui touche la terre, posée
    là où la surface de l'eau coupe le talus (cherché en marchant vers la rive)."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    for r in range(tm.h):
        for c in range(tm.w):
            if tm.at(c, r) != "W":
                continue
            surface = SEA_SURFACE if r > SEAWALL_ROW else POND_SURFACE
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nc, nr = c + dc, r + dr
                if not (0 <= nc < tm.w and 0 <= nr < tm.h) or tm.at(nc, nr) == "W":
                    continue
                nx, ny = dc, -dr  # vers la rive, dans le repère de Blender (y vers le nord)
                cx, cy = tm.x(c + 0.5), tm.y(r + 0.5)
                ex, ey = cx + nx * TILE / 2, cy + ny * TILE / 2  # milieu du côté
                tx_, ty_ = -ny, nx  # le long du côté
                shore = []
                for k in range(5):
                    a = (k / 4 - 0.5) * TILE
                    px, py = ex + tx_ * a, ey + ty_ * a
                    d = -0.6
                    if tm.height(px + nx * d, py + ny * d) >= surface:
                        break
                    while d < TILE and tm.height(px + nx * d, py + ny * d) < surface:
                        d += 0.03
                    shore.append((px + nx * d, py + ny * d))
                if len(shore) < 5:
                    continue
                z = surface + 0.02
                for (x0, y0), (x1, y1) in zip(shore, shore[1:]):
                    # Rive en v = 0 (bas de la texture, le liseré blanc), large en v = 1.
                    corners = [(x0, y0, 0), (x1, y1, 0), (x1 - nx * width, y1 - ny * width, 1),
                               (x0 - nx * width, y0 - ny * width, 1)]
                    f = bm.faces.new([bm.verts.new((x, y, z)) for x, y, _ in corners])
                    f.normal_update()
                    if f.normal.z < 0:
                        f.normal_flip()
                    for loop in f.loops:
                        co = loop.vert.co
                        v = next(k for x, y, k in corners if abs(x - co.x) < 1e-3 and abs(y - co.y) < 1e-3)
                        loop[uv].uv = ((co.x if tx_ else co.y) / 3.0, v)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(pixel_material("Foam", "foam.png"))
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    return obj


def white_fence(coll, name, x0, y0, x1, y1):
    """Clôture blanche : poteaux tous les ~1,2 m et deux lisses ; la lisse haute bloque le passage."""
    white = color_material("Fence_White", (0.92, 0.92, 0.88), roughness=0.6)
    length = math.hypot(x1 - x0, y1 - y0)
    along_x = abs(x1 - x0) > abs(y1 - y0)
    n = max(1, round(length / 1.2))
    for i in range(n + 1):
        t = i / n
        box(coll, f"{name}_Post", x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, 0, 0.14, 0.14, 0.9, white)
    for z, solid in ((0.35, False), (0.7, True)):
        w, d = (length, 0.07) if along_x else (0.07, length)
        box(coll, f"{name}_Rail", (x0 + x1) / 2, (y0 + y1) / 2, z, w, d, 0.1, white, solid=solid)


def stairs(coll, name, x_top, x_bottom, y0, y1, z_top, z_bottom, steps=6):
    """Escalier en bois descendant de x_top (en haut) vers x_bottom, avec rampes au nord et au sud."""
    wood = pixel_material("Town_Planks", "wood-planks.png")
    rail = color_material("Rail_Red", (0.45, 0.14, 0.1), roughness=0.6)
    sx = (x_top - x_bottom) / steps
    dz = (z_top - z_bottom) / steps
    for k in range(steps):
        top = z_top - k * dz
        box(coll, f"{name}_Step", x_top - (k + 0.5) * sx, (y0 + y1) / 2, z_bottom - 0.4, abs(sx), y1 - y0,
            top - (z_bottom - 0.4), wood, tile=1.5)
    for y in (y0 + 0.1, y1 - 0.1):
        for x, z in ((x_top, z_top), (x_bottom, z_bottom)):
            box(coll, f"{name}_RailPost", x, y, z, 0.16, 0.16, 0.9, rail)
        # Main courante inclinée : construite autour de son centre, puis tournée et placée.
        bar = box(coll, f"{name}_Rail", 0, 0, -0.05, math.hypot(x_top - x_bottom, z_top - z_bottom) + 0.2, 0.1, 0.1, rail)
        bar.location = ((x_top + x_bottom) / 2, y, (z_top + z_bottom) / 2 + 0.85)
        bar.rotation_euler = (0, -math.atan2(z_top - z_bottom, x_top - x_bottom), 0)


def tilted_box(coll, name, x, y, z, w, d, h, mat, rot):
    """Pavé construit autour de l'origine puis placé et tourné (lucarnes, auvents, pales)."""
    obj = box(coll, name, 0, 0, -h / 2, w, d, h, mat)
    obj.location = (x, y, z)
    obj.rotation_euler = rot
    return obj


def kit_place(coll, model, x, y, z, rot=0.0, scale=1.0, name=None, swap=None):
    """Copie liée d'une pièce de kit ; `swap` remplace des matériaux ({ancien: nouveau}) sur une
    copie du maillage partagée par toutes les pièces qui font le même échange."""
    data = bpy.data.objects[model].data
    if swap:
        key = f"{model}__" + "_".join(sorted(swap.values()))
        if key not in bpy.data.meshes:
            copy = data.copy()
            copy.name = key
            for i, m in enumerate(copy.materials):
                base = re.sub(r"\.\d{3}$", "", m.name)
                if base in swap:
                    copy.materials[i] = bpy.data.materials[swap[base]]
        data = bpy.data.meshes[key]
    obj = bpy.data.objects.new(name or model, data)
    obj.location = (x, y, z)
    obj.rotation_euler = (0, 0, rot)
    obj.scale = scale if isinstance(scale, tuple) else (scale, scale, scale)
    coll.objects.link(obj)
    return obj


def trim_uv(obj, v0, v1, u_scale=2.0):
    """UV d'une bande de la planche de textures du kit (bois, pierre) : le fil suit la plus
    grande dimension de chaque face, la bande couvre la plus petite."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        edge = max(f.edges, key=lambda e: e.calc_length())
        a = (edge.verts[1].co - edge.verts[0].co).normalized()
        b = f.normal.cross(a)
        pb = [l.vert.co.dot(b) for l in f.loops]
        lo, hi = min(pb), max(pb)
        for loop, q in zip(f.loops, pb):
            loop[uv].uv = (loop.vert.co.dot(a) / u_scale, v0 + (q - lo) / max(hi - lo, 1e-6) * (v1 - v0))
    bm.to_mesh(obj.data)
    bm.free()
    return obj


# Bandes de T_WoodTrim (v) : planches claires, bois sombre.
PLANKS_BAND, DARK_WOOD_BAND = (0.72, 0.96), (0.40, 0.66)


def wall_skin(coll, name, mat, origin, along, out, span, z0, z1, openings=(), board=0.27, kick=0.035,
              world_uv=None):
    """Parement d'un mur percé d'ouvertures. Par défaut un bardage à clins : une planche par
    rangée, bas de planche décollé de `kick` pour l'ombre portée, UV dans la bande de planches
    du kit. `world_uv` (m par répétition) : parement lisse (crépi).
    span(z) → (u_min, u_max) le long du mur (pignon : se resserre en montant) ; ouvertures en
    (u_a, u_b, z_a, z_b)."""
    rng = random.Random(name)
    origin, along, out = Vector(origin), Vector(along), Vector(out)
    point = lambda u, z, o: origin + along * u + out * o + Vector((0, 0, z))
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    # Rangées coupées aux bords des planches et des ouvertures (trous exacts, pas arrondis à la planche).
    cuts_z = {z0, z1} | {z for o in openings for z in o[2:] if z0 < z < z1}
    if not world_uv:
        cuts_z |= {z0 + k * board for k in range(1, math.ceil((z1 - z0) / board)) if z0 + k * board < z1}
    zs = sorted(cuts_z)
    shifts = {}
    for zb, zt in zip(zs, zs[1:]):
        if zt - zb < 1e-4:
            continue
        k = math.floor((zb - z0) / board + 1e-6)
        tb, tt = ((zb - z0) / board - k, (zt - z0) / board - k) if not world_uv else (0.0, 1.0)
        kb, kt = (0.0, 0.0) if world_uv else (kick * (1 - tb), kick * (1 - tt))
        shift = shifts.setdefault(k, rng.uniform(0, 2))
        (lo_b, hi_b), (lo_t, hi_t) = span(zb), span(zt)
        cuts = sorted((ua, ub) for ua, ub, za, zc in openings if za < zt - 1e-4 and zc > zb + 1e-4)
        segments, left = [], None
        for ua, ub in cuts:
            segments.append((left, ua))
            left = ub
        segments.append((left, None))
        for lft, rgt in segments:
            lb, lt = (lo_b, lo_t) if lft is None else (lft, lft)
            rb, rt = (hi_b, hi_t) if rgt is None else (rgt, rgt)
            if rb - lb < 0.02 and rt - lt < 0.02:
                continue
            corners = [(lb, zb, kb, tb), (rb, zb, kb, tb), (rt, zt, kt, tt), (lt, zt, kt, tt)]
            face = bm.faces.new([bm.verts.new(point(u, z, o)) for u, z, o, _ in corners])
            face.normal_update()
            if face.normal.dot(out) < 0:
                face.normal_flip()
            for loop in face.loops:
                co = loop.vert.co
                u = (co - origin).dot(along)
                if world_uv:
                    loop[uv].uv = (u / world_uv, co.z / world_uv)
                else:
                    t = tb if abs(co.z - zb) < abs(co.z - zt) else tt
                    loop[uv].uv = ((u + shift) / 2.0, PLANKS_BAND[0] + t * (PLANKS_BAND[1] - PLANKS_BAND[0]))
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    return obj


def kit_opening(coll, name, model, surface, out, along_u, z=0.0, swap=None):
    """Fenêtre ou porte du kit posée dans un mur : le plan de façade du kit (9 cm devant
    l'origine de la pièce) est aligné sur la surface du mur."""
    out = Vector(out)
    rot = math.atan2(out.x, -out.y)  # les pièces du kit regardent vers -Y
    pos = Vector(surface) - out * 0.09
    return kit_place(coll, model, pos.x, pos.y, z, rot=rot, name=name, swap=swap)


WINDOW_HOLE = (0.66, 1.1, 2.4)    # Window_Wide_Flat1 : demi-largeur, bas, haut de l'ouverture
THIN_HOLE = (0.28, 1.16, 2.4)     # Window_Thin_Flat1
DOOR_HOLE = (0.68, 0.0, 2.22)      # DoorFrame_Flat_WoodDark


def kit_door(coll, name, surface, out, along):
    out, along = Vector(out), Vector(along)
    kit_opening(coll, f"{name}_DoorFrame", "DoorFrame_Flat_WoodDark", surface, out, along)
    rot = math.atan2(out.x, -out.y)
    pos = Vector(surface) - out * 0.12 - along * 0.51  # battant (charnière à gauche), un peu en retrait
    kit_place(coll, "Door_1_Flat", pos.x, pos.y, 0.04, rot=rot, name=f"{name}_Door")


def awning(coll, name, x0, x1, y_wall, z, tiles, depth=1.0, slope=20):
    """Auvent de tuiles au-dessus d'une porte (façade sud), bordé d'une planche de rive."""
    a = math.radians(slope)
    cy = y_wall - depth / 2 * math.cos(a)
    slab = tilted_box(coll, f"{name}_Tiles", (x0 + x1) / 2, cy, z - depth / 2 * math.sin(a), x1 - x0, depth, 0.1,
                      tiles, (a, 0, 0))
    fascia = tilted_box(coll, f"{name}_Fascia", (x0 + x1) / 2, y_wall - depth * math.cos(a) + 0.02,
                        z - depth * math.sin(a) - 0.08, x1 - x0 + 0.04, 0.06, 0.18,
                        bpy.data.materials["MI_WoodTrim"], (0, 0, 0))
    trim_uv(fascia, *DARK_WOOD_BAND)
    for x in (x0 + 0.15, x1 - 0.15):  # consoles
        bracket = tilted_box(coll, f"{name}_Bracket", x, y_wall - 0.3, z - 0.55, 0.1, 0.6, 0.1,
                             bpy.data.materials["MI_WoodTrim"], (math.radians(-40), 0, 0))
        trim_uv(bracket, *DARK_WOOD_BAND, u_scale=1.0)
    return slab


def flower_box(coll, name, x, y_wall, z, w=1.5):
    """Jardinière sous une fenêtre, garnie de fleurs du kit nature."""
    box_obj = box(coll, f"{name}_Box", x, y_wall - 0.18, z, w, 0.32, 0.24, bpy.data.materials["MI_WoodTrim"])
    trim_uv(box_obj, *DARK_WOOD_BAND, u_scale=1.0)
    for k in range(4):
        fx = x - w / 2 + (k + 0.5) * w / 4
        place(coll, "Flower_3_Group" if k % 2 else "Flower_4_Group", fx, y_wall - 0.18, z + 0.2,
              scale=random.uniform(0.28, 0.34))


def bw_house(coll, name, x0, x1, y0, y1, wall_h, door_x):
    """Maison de Renouet en pièces du Medieval Village MegaKit : noyau sombre, bardage à clins
    en bois clair percé de vraies ouvertures, angles en briques, soubassement de pierre, toit de
    tuiles rondes bleues (pignon au sud), fenêtres et porte du kit, auvent, jardinière, châssis
    de toit."""
    cx, cy, w, d = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
    siding = bpy.data.materials["MI_WoodTrim_Light"]
    blue = {"MI_RoundTiles": "MI_RoundTiles_Blue"}
    base_h, pillar = 0.42, 0.46
    box(coll, f"{name}_Core", cx, cy, 0, w - 0.8, d - 0.8, wall_h, color_material("House_Interior", (0.05, 0.04, 0.035)),
        solid=True)
    box(coll, f"{name}_Base", cx, cy, 0, w + 0.14, d + 0.14, base_h, bpy.data.materials["MI_UnevenBrick"], tile=1.6)
    for x in (x0 + pillar / 2 - 0.05, x1 - pillar / 2 + 0.05):
        for y in (y0 + pillar / 2 - 0.05, y1 - pillar / 2 + 0.05):
            box(coll, f"{name}_Corner", x, y, base_h - 0.02, pillar, pillar, wall_h - base_h + 0.08,
                bpy.data.materials["MI_RedBrick"], tile=1.4)
    # Roof_RoundTiles_4x6 : 5,5 × 7,6 m, faîtage nord-sud ; étiré pour couvrir la maison.
    sx, sy = (w / 2 + 0.7) / 2.76, (d + 1.0) / 7.58
    kit_place(coll, "Roof_RoundTiles_4x6", cx, cy, wall_h, scale=(sx, sy, 1.0), name=f"{name}_Roof", swap=blue)
    gable_h = 3.72 - 0.42 - (3.72 + 0.52) * (pillar / 2) / (2.76 * sx)
    flat = lambda lo, hi: (lambda z: (lo, hi))
    inner = (pillar - 0.05, w - pillar + 0.05)
    win_x = door_x + 1.95 if door_x + 2.75 < x1 else door_x - 1.95
    # Façade sud : porte et fenêtre ; pignon avec une petite fenêtre de grenier.
    du, wu = door_x - x0, win_x - x0
    wall_skin(coll, f"{name}_Front", siding, (x0, y0, 0), (1, 0, 0), (0, -1, 0), flat(*inner), base_h, wall_h,
              [(du - DOOR_HOLE[0], du + DOOR_HOLE[0], 0, DOOR_HOLE[2]),
               (wu - WINDOW_HOLE[0], wu + WINDOW_HOLE[0], WINDOW_HOLE[1], WINDOW_HOLE[2])])
    gable = lambda z: (w / 2 * min(1, (z - wall_h) / gable_h), w - w / 2 * min(1, (z - wall_h) / gable_h))
    attic_z = wall_h - 0.55
    for side, y, out in (("South", y0, (0, -1, 0)), ("North", y1, (0, 1, 0))):
        holes = [(w / 2 - THIN_HOLE[0], w / 2 + THIN_HOLE[0], attic_z + THIN_HOLE[1], attic_z + THIN_HOLE[2])] \
            if side == "South" else []
        wall_skin(coll, f"{name}_Gable{side}", siding, (x0, y, 0), (1, 0, 0), out, gable, wall_h, wall_h + gable_h, holes)
    kit_opening(coll, f"{name}_Attic", "Window_Thin_Flat1", (cx, y0, 0), (0, -1, 0), (1, 0, 0), z=attic_z)
    kit_door(coll, name, (door_x, y0, 0), (0, -1, 0), (1, 0, 0))
    kit_opening(coll, f"{name}_Window", "Window_Wide_Flat1", (win_x, y0, 0), (0, -1, 0), (1, 0, 0))
    # Autres murs : une fenêtre étroite au milieu de chaque côté, une large au nord.
    for side, origin, along, out in (("West", (x0, y0, 0), (0, 1, 0), (-1, 0, 0)), ("East", (x1, y0, 0), (0, 1, 0), (1, 0, 0)),
                                     ("Back", (x0, y1, 0), (1, 0, 0), (0, 1, 0))):
        length = d if along[1] else w
        hole = THIN_HOLE if side != "Back" else WINDOW_HOLE
        wall_skin(coll, f"{name}_{side}", siding, origin, along, out, flat(pillar - 0.05, length - pillar + 0.05),
                  base_h, wall_h, [(length / 2 - hole[0], length / 2 + hole[0], hole[1], hole[2])])
        mid = Vector(origin) + Vector(along) * (length / 2)
        kit_opening(coll, f"{name}_{side}Window", "Window_Thin_Flat1" if side != "Back" else "Window_Wide_Flat1",
                    mid, out, along)
    # Auvent bleu au-dessus de la porte et de la fenêtre, jardinière sous la fenêtre.
    lo, hi = min(door_x, win_x) - 1.0, max(door_x, win_x) + 1.0
    awning(coll, f"{name}_Awning", lo, hi, y0, wall_h - 0.12, bpy.data.materials["MI_RoundTiles_Blue"], depth=0.85)
    flower_box(coll, f"{name}_Flowers", win_x, y0, 0.68)
    box(coll, f"{name}_Step", door_x, y0 - 0.35, 0, 1.5, 0.7, 0.16, bpy.data.materials["MI_UnevenBrick"], tile=1.6)
    # Châssis vitré sur le pan est du toit.
    a = math.atan2(3.72 + 0.52, 2.76 * sx)
    run = 1.45
    sky_z = wall_h + 3.72 - (3.72 + 0.52) * run / (2.76 * sx) + 0.1
    frame = tilted_box(coll, f"{name}_SkylightFrame", cx + run, cy + 0.5, sky_z, 1.15, 1.25, 0.16,
                       bpy.data.materials["MI_WoodTrim"], (0, a, 0))
    trim_uv(frame, *DARK_WOOD_BAND, u_scale=1.0)
    tilted_box(coll, f"{name}_Skylight", cx + run + 0.06 * math.sin(a), cy + 0.5, sky_z + 0.06 * math.cos(a),
               0.92, 1.02, 0.06, bpy.data.materials["MI_WindowGlass"], (0, a, 0))


def bw_lab(coll, name, x0, x1, y0, y1):
    """Labo du Professeur : bâtiment principal crépi au toit de tuiles orange (faîtage est-ouest),
    lucarne du kit au-dessus de la porte, aile ouest plus haute à pignon pointu, chaînes d'angle
    en pierre, cheminée."""
    plaster = bpy.data.materials["MI_Plaster"]
    stone = bpy.data.materials["MI_UnevenBrick"]
    dark = color_material("House_Interior", (0.05, 0.04, 0.035))
    d, cy = y1 - y0, (y0 + y1) / 2
    wing_w = 2.8
    xw, xm = x0 + wing_w, x0 + wing_w / 2
    wh, base_h = 3.5, 0.85
    mw = x1 - xw
    door_x = (xw + x1) / 2
    # Bâtiment principal.
    box(coll, f"{name}_Core", (xw + x1) / 2, cy, 0, mw - 0.6, d - 0.6, wh, dark, solid=True)
    box(coll, f"{name}_Base", (xw + x1) / 2, cy, 0, mw + 0.14, d + 0.14, base_h, stone, tile=1.6)
    windows = [door_x + k * off for k in (-1, 1) for off in (2.05, 3.55)]
    holes = [(door_x - xw - DOOR_HOLE[0], door_x - xw + DOOR_HOLE[0], 0, DOOR_HOLE[2])]
    holes += [(wx - xw - WINDOW_HOLE[0], wx - xw + WINDOW_HOLE[0], WINDOW_HOLE[1] + 0.15, WINDOW_HOLE[2] + 0.15) for wx in windows]
    flat = lambda lo, hi: (lambda z: (lo, hi))
    wall_skin(coll, f"{name}_Front", plaster, (xw, y0, 0), (1, 0, 0), (0, -1, 0), flat(0, mw), base_h, wh, holes,
              world_uv=2.5)
    wall_skin(coll, f"{name}_Back", plaster, (xw, y1, 0), (1, 0, 0), (0, 1, 0), flat(0, mw), base_h, wh, world_uv=2.5)
    wall_skin(coll, f"{name}_East", plaster, (x1, y0, 0), (0, 1, 0), (1, 0, 0), flat(0, d), base_h, wh, world_uv=2.5)
    for wx in windows:
        kit_opening(coll, f"{name}_Window", "Window_Wide_Flat1", (wx, y0, 0), (0, -1, 0), (1, 0, 0), z=0.15)
    kit_door(coll, name, (door_x, y0, 0), (0, -1, 0), (1, 0, 0))
    awning(coll, f"{name}_DoorRoof", door_x - 1.1, door_x + 1.1, y0, 2.75, bpy.data.materials["MI_RoundTiles"],
           depth=1.1, slope=24)
    box(coll, f"{name}_Step", door_x, y0 - 0.4, 0, 2.0, 0.8, 0.18, stone, tile=1.6)
    # Toit principal (Roof_RoundTiles_6x10 tourné : faîtage est-ouest), pignon est crépi.
    sx, sy, sz = (d / 2 + 0.75) / 4.12, (mw + 0.9) / 11.85, 0.72
    rz = wh + 0.12
    kit_place(coll, "Roof_RoundTiles_6x10", (xw + x1) / 2 + 0.2, cy, rz, rot=math.pi / 2, scale=(sx, sy, sz),
              name=f"{name}_Roof")
    gable_h = (4.89 - 0.5) * sz + 0.12
    gable = lambda z: (d / 2 * min(1, (z - wh) / gable_h), d - d / 2 * min(1, (z - wh) / gable_h))
    wall_skin(coll, f"{name}_EastGable", plaster, (x1, y0, 0), (0, 1, 0), (1, 0, 0), gable, wh, wh + gable_h,
              world_uv=2.5)
    # Lucarne du kit sur le pan sud, au-dessus de la porte.
    slope_t = 1.25  # recul depuis le mur
    kit_place(coll, "Roof_Dormer_RoundTile", door_x, y0 + slope_t + 1.9 * 0.85, rz + (4.89 - (4.89 + 0.78) * (d / 2 - slope_t) / (4.12 * sx)) * sz - 0.35,
              rot=-math.pi / 2, scale=0.85, name=f"{name}_Dormer")
    # Aile ouest, plus haute et un peu en avant.
    ww, wy0 = 4.1, y0 - 0.5
    wd = y1 - wy0
    box(coll, f"{name}_WingCore", xm, (wy0 + y1) / 2, 0, wing_w - 0.6, wd - 0.6, ww, dark, solid=True)
    box(coll, f"{name}_WingBase", xm, (wy0 + y1) / 2, 0, wing_w + 0.14, wd + 0.14, base_h, stone, tile=1.6)
    wall_skin(coll, f"{name}_WingFront", plaster, (x0, wy0, 0), (1, 0, 0), (0, -1, 0), flat(0, wing_w), base_h, ww,
              [(wing_w / 2 - THIN_HOLE[0], wing_w / 2 + THIN_HOLE[0], THIN_HOLE[1] + 0.3, THIN_HOLE[2] + 0.3)], world_uv=2.5)
    wall_skin(coll, f"{name}_WingWest", plaster, (x0, wy0, 0), (0, 1, 0), (-1, 0, 0), flat(0, wd), base_h, ww, world_uv=2.5)
    wall_skin(coll, f"{name}_WingEast", plaster, (xw, wy0, 0), (0, 1, 0), (1, 0, 0), flat(0, 0.6), base_h, ww, world_uv=2.5)
    kit_opening(coll, f"{name}_WingWindow", "Window_Thin_Flat1", (xm, wy0, 0), (0, -1, 0), (1, 0, 0), z=0.3)
    wsx, wsy, wsz = (wing_w / 2 + 0.55) / 2.76, (wd + 0.9) / 9.68, 1.15
    wrz = ww - 0.1
    kit_place(coll, "Roof_RoundTiles_4x8", xm, (wy0 + y1) / 2, wrz, scale=(wsx, wsy, wsz), name=f"{name}_WingRoof")
    wgable_h = (3.72 - 0.45) * wsz + 0.05
    wgable = lambda z: (wing_w / 2 * min(1, (z - ww) / wgable_h), wing_w - wing_w / 2 * min(1, (z - ww) / wgable_h))
    for side, y, out in (("South", wy0, (0, -1, 0)), ("North", y1, (0, 1, 0))):
        wall_skin(coll, f"{name}_WingGable{side}", plaster, (x0, y, 0), (1, 0, 0), out, wgable, ww, ww + wgable_h,
                  world_uv=2.5)
    kit_place(coll, "Prop_Chimney", x0 + 0.55, y1 - 1.3, ww + 1.2, name=f"{name}_Chimney")
    # Chaînes d'angle en pierre (Corner_Exterior_Brick, 3 m) : sud-ouest et sud-est de l'aile,
    # sud-est et nord-est du bâtiment principal.
    for (x, y), rot, h in ((((x0, wy0), 0.0, ww)), ((xw, wy0), math.pi / 2, ww), ((x1, y0), math.pi / 2, wh),
                           ((x1, y1), math.pi, wh)):
        off = Vector((0.29, 0.32, 0))
        off.rotate(Euler((0, 0, rot)))
        kit_place(coll, "Corner_Exterior_Brick", x + off.x, y + off.y, 0, rot=rot, scale=(1, 1, h / 3.01),
                  name=f"{name}_Quoin")


def rounded_rect(x0, x1, y0, y1, radius, segments=5):
    """Rectangle aux angles arrondis, sens trigonométrique."""
    pts = []
    for cx, cy, a0 in ((x1 - radius, y0 + radius, -math.pi / 2), (x1 - radius, y1 - radius, 0.0),
                       (x0 + radius, y1 - radius, math.pi / 2), (x0 + radius, y0 + radius, math.pi)):
        for k in range(segments + 1):
            a = a0 + (math.pi / 2) * k / segments
            pts.append(Vector((cx + radius * math.cos(a), cy + radius * math.sin(a))))
    return pts


def curb(coll, name, x0, x1, y0, y1, z, width=0.3, height=0.12, radius=0.8):
    """Bordure de pierre claire aux angles arrondis autour d'une pelouse (x0..x1, y0..y1), un
    peu à l'écart de l'herbe pour laisser voir la bande de terre."""
    b = Builder(name)
    stone = color_material("Curb_Stone", (0.72, 0.72, 0.68), roughness=0.85)
    gap = 0.22
    inner = rounded_rect(x0 - gap, x1 + gap, y0 - gap, y1 + gap, radius)
    outer = rounded_rect(x0 - gap - width, x1 + gap + width, y0 - gap - width, y1 + gap + width, radius + width)
    b.loft(stone, outer, outer, z, z + height)
    b.loft(stone, inner, inner, z, z + height)
    b.loft(stone, outer, inner, z + height, z + height)
    b.build(coll)


def raise_new(coll, before, dz):
    """Monte de dz tous les objets ajoutés depuis `before` (bâtiment posé sur un plateau)."""
    for obj in set(coll.objects) - before:
        if obj.parent is None:
            obj.location.z += dz


def apartment(coll, name, x0, x1, yf, depth, door_x, base_z=0.0):
    """Immeuble d'Arabelle : trois niveaux de briques sombres, bandeaux de bois entre les étages,
    trois fenêtres par étage, porte sous un auvent rayé rouge et blanc, toit-terrasse beige bordé
    d'un acrotère ardoise, bouche d'aération sur le toit. Façade au sud."""
    before = set(coll.objects)
    brick = bpy.data.materials["MI_RedBrick_Dark"]
    wood = bpy.data.materials["MI_WoodTrim"]
    slate = color_material("Apartment_Slate", (0.045, 0.11, 0.16), roughness=0.6)
    coping = color_material("Apartment_Coping", (0.09, 0.18, 0.24), roughness=0.55)
    vent = color_material("Apartment_Vent", (0.5, 0.52, 0.54), roughness=0.7)
    dark = color_material("House_Interior", (0.05, 0.04, 0.035))
    w, yb = x1 - x0, yf + depth
    cx, cy = (x0 + x1) / 2, (yf + yb) / 2
    ground, storey, levels = 3.0, 2.6, 3
    h = ground + storey * (levels - 1)
    box(coll, f"{name}_Core", cx, cy, 0, w - 0.8, depth - 0.8, h, dark, solid=True)
    box(coll, f"{name}_Base", cx, cy, 0, w + 0.12, depth + 0.12, 0.35, bpy.data.materials["MI_UnevenBrick"], tile=1.6)
    flat = lambda lo, hi: (lambda z: (lo, hi))
    floor_z = [0.0] + [ground + storey * k for k in range(levels - 1)]
    cols = [x0 + w * f for f in (0.2, 0.5, 0.8)]
    holes, windows = [], []
    for k, z in enumerate(floor_z):
        lift = 0.0 if k == 0 else z - 0.45
        for wx in cols:
            if k == 0 and abs(wx - door_x) < 1.2:
                continue
            holes.append((wx - x0 - WINDOW_HOLE[0], wx - x0 + WINDOW_HOLE[0], lift + WINDOW_HOLE[1], lift + WINDOW_HOLE[2]))
            windows.append((wx, lift))
    holes.append((door_x - x0 - DOOR_HOLE[0], door_x - x0 + DOOR_HOLE[0], 0, DOOR_HOLE[2]))
    wall_skin(coll, f"{name}_Front", brick, (x0, yf, 0), (1, 0, 0), (0, -1, 0), flat(0, w), 0.35, h, holes, world_uv=1.6)
    for wx, lift in windows:
        kit_opening(coll, f"{name}_Window", "Window_Wide_Flat1", (wx, yf, 0), (0, -1, 0), (1, 0, 0), z=lift)
    kit_door(coll, name, (door_x, yf, 0), (0, -1, 0), (1, 0, 0))
    for side, origin, out in (("West", (x0, yf, 0), (-1, 0, 0)), ("East", (x1, yf, 0), (1, 0, 0))):
        side_holes = [(depth / 2 - THIN_HOLE[0], depth / 2 + THIN_HOLE[0], z - 0.45 + THIN_HOLE[1], z - 0.45 + THIN_HOLE[2])
                      for z in floor_z[1:]]
        wall_skin(coll, f"{name}_{side}", brick, origin, (0, 1, 0), out, flat(0, depth), 0.35, h, side_holes, world_uv=1.6)
        for z in floor_z[1:]:
            kit_opening(coll, f"{name}_{side}Window", "Window_Thin_Flat1", (origin[0], yf + depth / 2, 0), out, (0, 1, 0),
                        z=z - 0.45)
    wall_skin(coll, f"{name}_Back", brick, (x0, yb, 0), (1, 0, 0), (0, 1, 0), flat(0, w), 0.35, h, world_uv=1.6)
    # Bandeaux de bois entre les étages, toit-terrasse, acrotère et sa couvertine.
    for z in floor_z[1:]:
        for bx, by, bw, bd in ((cx, yf - 0.05, w + 0.2, 0.2), (cx, yb + 0.05, w + 0.2, 0.2),
                               (x0 - 0.05, cy, 0.2, depth + 0.2), (x1 + 0.05, cy, 0.2, depth + 0.2)):
            trim_uv(box(coll, f"{name}_Band", bx, by, z - 0.12, bw, bd, 0.24, wood), *PLANKS_BAND, u_scale=2.0)
    box(coll, f"{name}_Terrace", cx, cy, h - 0.05, w, depth, 0.1, pixel_material("Apartment_Terrace", "roof-terrace.png"),
        tile=2.5)
    for bx, by, bw, bd in ((cx, yf + 0.25, w + 0.1, 0.6), (cx, yb - 0.25, w + 0.1, 0.6),
                           (x0 + 0.25, cy, 0.6, depth + 0.1), (x1 - 0.25, cy, 0.6, depth + 0.1)):
        box(coll, f"{name}_Parapet", bx, by, h, bw, bd, 0.65, slate)
        box(coll, f"{name}_Coping", bx, by, h + 0.65, bw + 0.06, bd + 0.06, 0.06, coping)
    box(coll, f"{name}_Vent", x1 - 1.3, yb - 1.2, h, 1.0, 0.8, 0.7, vent)
    front_plane(coll, f"{name}_VentGrille", x1 - 1.3, yb - 1.61, h + 0.38, 0.6, 0.3, dark)
    # Auvent rayé au-dessus de la porte, petites plantes au pied de la façade.
    tilted_box(coll, f"{name}_Awning", door_x, yf - 0.45, 2.55, 2.0, 0.95, 0.08,
               pixel_material("Awning_Stripes", "awning-stripes.png"), (math.radians(22), 0, 0))
    for px in (x0 + 0.35, x1 - 0.35, (cols[1] + cols[2]) / 2):
        place(coll, "Bush_Common", px, yf - 0.3, 0, scale=random.uniform(0.3, 0.38))
    raise_new(coll, before, base_z)


def cross_house(coll, name, x0, x1, yf, yb, base_z=0.0):
    """Maison au toit bleu du plateau d'Arabelle : faîtage est-ouest, petit pignon en avant
    au-dessus de la porte, deux fenêtres, cheminée de briques. Façade au sud."""
    before = set(coll.objects)
    siding = bpy.data.materials["MI_WoodTrim"]
    blue = {"MI_RoundTiles": "MI_RoundTiles_Blue"}
    cx, cy, w, d = (x0 + x1) / 2, (yf + yb) / 2, x1 - x0, yb - yf
    wall_h = 2.9
    box(coll, f"{name}_Core", cx, cy, 0, w - 0.8, d - 0.8, wall_h, color_material("House_Interior", (0.05, 0.04, 0.035)),
        solid=True)
    box(coll, f"{name}_Base", cx, cy, 0, w + 0.14, d + 0.14, 0.38, bpy.data.materials["MI_UnevenBrick"], tile=1.6)
    for x in (x0 + 0.17, x1 - 0.17):
        for y in (yf + 0.17, yb - 0.17):
            box(coll, f"{name}_Corner", x, y, 0.36, 0.4, 0.4, wall_h - 0.36, bpy.data.materials["MI_RedBrick_Dark"], tile=1.4)
    flat = lambda lo, hi: (lambda z: (lo, hi))
    win = [cx - 2.0, cx + 2.0]
    holes = [(cx - x0 - DOOR_HOLE[0], cx - x0 + DOOR_HOLE[0], 0, DOOR_HOLE[2])]
    holes += [(wx - x0 - WINDOW_HOLE[0], wx - x0 + WINDOW_HOLE[0], WINDOW_HOLE[1], WINDOW_HOLE[2]) for wx in win]
    wall_skin(coll, f"{name}_Front", siding, (x0, yf, 0), (1, 0, 0), (0, -1, 0), flat(0.4, w - 0.4), 0.38, wall_h, holes)
    kit_door(coll, name, (cx, yf, 0), (0, -1, 0), (1, 0, 0))
    for wx in win:
        kit_opening(coll, f"{name}_Window", "Window_Wide_Flat1", (wx, yf, 0), (0, -1, 0), (1, 0, 0))
    for side, origin, along, out, length in (("West", (x0, yf, 0), (0, 1, 0), (-1, 0, 0), d),
                                             ("East", (x1, yf, 0), (0, 1, 0), (1, 0, 0), d),
                                             ("Back", (x0, yb, 0), (1, 0, 0), (0, 1, 0), w)):
        wall_skin(coll, f"{name}_{side}", siding, origin, along, out, flat(0.4, length - 0.4), 0.38, wall_h)
    # Grand toit (faîtage est-ouest), pignons latéraux en bardage.
    sx, sy = (d / 2 + 0.6) / 2.76, (w + 0.9) / 7.58
    kit_place(coll, "Roof_RoundTiles_4x6", cx, cy, wall_h, rot=math.pi / 2, scale=(sx, sy, 0.8), name=f"{name}_Roof",
              swap=blue)
    gable_h = (3.72 - 0.42) * 0.8 - 0.3
    gable = lambda z: (d / 2 * min(1, (z - wall_h) / gable_h), d - d / 2 * min(1, (z - wall_h) / gable_h))
    for side, x, out in (("GableWest", x0, (-1, 0, 0)), ("GableEast", x1, (1, 0, 0))):
        wall_skin(coll, f"{name}_{side}", siding, (x, yf, 0), (0, 1, 0), out, gable, wall_h, wall_h + gable_h)
    # Petit pignon au-dessus de la porte, en avant du toit.
    gw, gl = 3.2, d / 2 + 0.9
    kit_place(coll, "Roof_RoundTiles_4x6", cx, yf - 0.9 + gl / 2, wall_h, scale=((gw / 2 + 0.3) / 2.76, gl / 7.58, 0.8),
              name=f"{name}_FrontRoof", swap=blue)
    fg_h = 2.2
    front_gable = lambda z: (gw / 2 * min(1, (z - wall_h) / fg_h), gw - gw / 2 * min(1, (z - wall_h) / fg_h))
    wall_skin(coll, f"{name}_FrontGable", siding, (cx - gw / 2, yf - 0.02, 0), (1, 0, 0), (0, -1, 0), front_gable,
              wall_h, wall_h + fg_h)
    box(coll, f"{name}_Lintel", cx, yf - 0.06, 2.45, 2.2, 0.12, 0.22, color_material("House_Cream", (0.85, 0.82, 0.72)))
    kit_place(coll, "Prop_Chimney", x0 + w * 0.68, yb - 0.9, wall_h + 0.6, name=f"{name}_Chimney")
    raise_new(coll, before, base_z)


def gate_building(coll, name, x0, x1, ys, yn):
    """Bâtiment au toit vert, à l'ouest d'Arabelle : toit plat vert clair, façade vitrée à l'est."""
    b = Builder(name)
    plaster = bpy.data.materials["MI_Plaster"]
    green = color_material("Gate_Green", (0.25, 0.7, 0.2), roughness=0.6)
    green_dark = color_material("Gate_GreenDark", (0.12, 0.42, 0.1), roughness=0.6)
    glass = pixel_material("Gate_Glass", "center-glass-low.png", roughness=0.3)
    cx, cy, w, d, h = (x0 + x1) / 2, (ys + yn) / 2, x1 - x0, yn - ys, 3.4
    box(coll, f"{name}_Walls", cx, cy, 0, w, d, h, plaster, tile=2.5, solid=True)
    box(coll, f"{name}_Base", cx, cy, 0, w + 0.1, d + 0.1, 0.3, bpy.data.materials["MI_UnevenBrick"], tile=1.6)
    b.box(green, cx, cy, h, w + 0.4, d + 0.4, 0.3)
    b.box(green_dark, cx - 0.2, cy + 0.1, h + 0.3, w * 0.55, d * 0.45, 0.06)
    n = (d - 0.6) / 1.25
    b.quad(glass, [(x1 + 0.03, ys + 0.3, 0.3), (x1 + 0.03, yn - 0.3, 0.3), (x1 + 0.03, yn - 0.3, h - 0.25),
                   (x1 + 0.03, ys + 0.3, h - 0.25)], [(0, 0), (n, 0), (n, 1), (0, 1)])
    b.build(coll)


def stage(coll, name, outer, platform, sign_x, sign_y):
    """Estrade de la place d'Arabelle : fine dalle d'assise, plateau praticable (cases de niveau
    « p » de la grille) bordé de pierre rosée aux angles adoucis, panneau d'information au fond.
    `outer`, `platform` : (x0, x1, y0, y1)."""
    b = Builder(name)
    slabs = pixel_material("Town_Slabs", "slabs.png")
    rose = color_material("Stage_Rose", (0.6, 0.45, 0.4), roughness=0.8)
    h = TOWN_Z["p"]
    base = chamfered(*outer, 0.5)
    b.ring(slabs, base, 0.0, 0.04)
    b.cap(slabs, base, 0.04)
    top = chamfered(*platform, 0.35)
    b.ring(rose, top, 0.04, h - 0.1)
    b.loft(rose, top, offset_poly(top, -0.12), h - 0.1, h)
    b.cap(slabs, offset_poly(top, -0.12), h)
    grey = color_material("Sign_Grey", (0.42, 0.44, 0.46), roughness=0.6)
    for dx in (-0.75, 0.75):
        b.box(grey, sign_x + dx, sign_y, 0.04, 0.1, 0.1, 1.25)
    b.box(grey, sign_x, sign_y, 0.6, 1.75, 0.14, 0.8)
    b.box(color_material("Sign_Panel", (0.08, 0.1, 0.1), roughness=0.5), sign_x, sign_y - 0.08, 0.68, 1.5, 0.02, 0.62)
    b.build(coll)


def bench(coll, name, x, y, length=1.4):
    """Banc du jardin (assise orientée vers l'est, dossier à l'ouest)."""
    b = Builder(name)
    wood = bpy.data.materials["MI_WoodTrim_Light"]
    metal = color_material("Bench_Metal", (0.08, 0.1, 0.12), roughness=0.5)
    for k in range(3):
        b.box(wood, x - 0.12 + k * 0.15, y, 0.42, 0.12, length, 0.05)
    for k in range(2):
        b.box(wood, x - 0.26, y, 0.55 + k * 0.16, 0.05, length, 0.12)
    for dy in (-length / 2 + 0.12, length / 2 - 0.12):
        b.box(metal, x, y + dy, 0.0, 0.45, 0.06, 0.42)
        b.box(metal, x - 0.26, y + dy, 0.4, 0.05, 0.06, 0.5)
    b.build(coll)
    marker(coll, f"{name}_Collider", x, y, 0)["collider"] = 0.75


def town_railings(coll, tm):
    """Rambardes des bords de niveau d'Arabelle : sur chaque côté d'une case K qui domine sa voisine
    (ou longe un escalier), poteaux tous les 40 cm et deux lisses, un peu en retrait du bord."""
    b = Builder("Railing")
    post = color_material("Railing_Post", (0.06, 0.08, 0.12), roughness=0.5)
    rail = color_material("Railing_Rail", (0.22, 0.27, 0.34), roughness=0.45)
    for c, r in tm.all_cells():
        if r >= 0 or tm.at(c, r) != "K":
            continue
        nw, sw, se, ne = tm.tile_corners(c, r)
        z = max(nw, sw, se, ne)
        x0, x1, yn, ys = tm.x(c), tm.x(c + 1), tm.y(r), tm.y(r + 1)
        for (nc, nr), (p, q), inward in (((c + 1, r), ((x1, yn), (x1, ys)), (-1, 0)), ((c - 1, r), ((x0, yn), (x0, ys)), (1, 0)),
                                         ((c, r + 1), ((x0, ys), (x1, ys)), (0, 1)), ((c, r - 1), ((x0, yn), (x1, yn)), (0, -1))):
            other = tm.at(nc, nr)
            if other == "K" or not 0 <= nc < tm.w:
                continue
            if other != "E" and max(tm.tile_corners(nc, nr)) > z - 0.3:
                continue
            ox, oy = inward[0] * 0.14, inward[1] * 0.14
            (ax, ay), (bx, by) = p, q
            length = math.hypot(bx - ax, by - ay)
            for k in range(int(length / 0.4) + 1):
                t = k * 0.4 / length
                b.box(post, ax + (bx - ax) * t + ox, ay + (by - ay) * t + oy, z, 0.07, 0.07, 0.9)
            for rz, th in ((z + 0.86, 0.09), (z + 0.2, 0.05)):
                along_x = abs(bx - ax) > abs(by - ay)
                b.box(rail, (ax + bx) / 2 + ox, (ay + by) / 2 + oy, rz, length if along_x else 0.09,
                      0.09 if along_x else length, th)
    b.build(coll)


def stair_steps(coll, name, tm, cols, rows, axis, h0, h1, rail_side=None):
    """Escalier de pierre d'Arabelle le long de sa rampe (TOWN_RAMPS) : girons et contremarches,
    limons pleins sur les deux côtés (du pied de l'escalier jusqu'au nez des marches, un peu en
    retrait des murs voisins), rampe facultative côté vide ("north", "south", "east", "west")."""
    b = Builder(name)
    tread = pixel_material("Town_Slabs", "slabs.png")
    riser = color_material("Stair_Riser", (0.55, 0.53, 0.47), roughness=0.85)
    side = pixel_material("Town_Wall", "town-wall.png")
    (c0, c1), (a0, a1) = cols, rows
    x0, x1 = tm.x(c0), tm.x(c1 + 1)
    yn, ys = tm.y(a0 - TOWN_ROWS), tm.y(a1 + 1 - TOWN_ROWS)
    low, high = min(h0, h1), max(h0, h1)
    length = (yn - ys) if axis == "y" else (x1 - x0)
    n = max(4, round((high - low) / 0.18))
    # Abscisse u depuis le pied de l'escalier → coordonnée le long de l'axe ; début = nord ou est.
    start = yn if axis == "y" else x1
    end = ys if axis == "y" else x0
    foot, head = (end, start) if h1 < h0 else (start, end)
    along = lambda u: foot + (head - foot) * u / length
    lo_w, hi_w = (x0, x1) if axis == "y" else (ys, yn)  # largeur de l'escalier
    point = lambda a, w, z: (w, a, z) if axis == "y" else (a, w, z)
    tread_z = lambda k: low + (high - low) * (k + 0.5) / n
    inset = 0.03
    for k in range(n):
        ua, ub = along(length * k / n), along(length * (k + 1) / n)
        z, below = tread_z(k), (tread_z(k - 1) if k else low)
        b.quad(tread, [point(ua, lo_w, z), point(ub, lo_w, z), point(ub, hi_w, z), point(ua, hi_w, z)],
               [(lo_w / 2.5, ua / 2.5), (lo_w / 2.5, ub / 2.5), (hi_w / 2.5, ub / 2.5), (hi_w / 2.5, ua / 2.5)])
        b.face(riser, [point(ua, lo_w, below), point(ua, hi_w, below), point(ua, hi_w, z), point(ua, lo_w, z)])
        for w in (lo_w + inset, hi_w - inset):  # limons
            b.quad(side, [point(ua, w, low), point(ub, w, low), point(ub, w, z), point(ua, w, z)],
                   [(ua / 2.5, low / 2.5), (ub / 2.5, low / 2.5), (ub / 2.5, z / 2.5), (ua / 2.5, z / 2.5)])
    b.face(riser, [point(head, lo_w, tread_z(n - 1)), point(head, hi_w, tread_z(n - 1)), point(head, hi_w, high),
                   point(head, lo_w, high)])
    if rail_side:
        post = color_material("Railing_Post", (0.06, 0.08, 0.12), roughness=0.5)
        rail = color_material("Railing_Rail", (0.22, 0.27, 0.34), roughness=0.45)
        w = (lo_w + 0.12) if rail_side in ("south", "west") else (hi_w - 0.12)
        count = int(length / 0.6)
        for k in range(count + 1):
            u = length * (k + 0.5) / (count + 1)
            step = min(n - 1, int(u / length * n))
            px, py, pz = point(along(u), w, tread_z(step))
            b.box(post, px, py, pz, 0.07, 0.07, 0.92)
        za, zb = low + 0.9, high + 0.9
        b.face(rail, [point(foot, w - 0.045, za), point(head, w - 0.045, zb), point(head, w - 0.045, zb + 0.09),
                      point(foot, w - 0.045, za + 0.09)])
        b.face(rail, [point(foot, w + 0.045, za + 0.09), point(head, w + 0.045, zb + 0.09), point(head, w - 0.045, zb + 0.09),
                      point(foot, w - 0.045, za + 0.09)])
    b.build(coll)


def build_arabelle(coll, tm, tx, ty):
    """Arabelle (Accumula Town), au nord de la Route 1 : grille tools/maps/arabelle.txt, trois
    niveaux (rue, plateau de la maison bleue, place en contrebas), immeubles, Centre Pokémon,
    jardin aux bancs, estrade, bâtiment au toit vert."""
    ay = lambda a: ty(a - TOWN_ROWS)  # ligne de la ville (décimale) → y
    level_walls(coll, tm, pixel_material("Town_Wall", "town-wall.png"), pixel_material("Town_Cliff", "cliff.png"))
    town_railings(coll, tm)
    stair_steps(coll, "Stairs_Plateau", tm, *TOWN_RAMPS[0])
    stair_steps(coll, "Stairs_Square", tm, *TOWN_RAMPS[1], rail_side="south")

    # Bâtiments : trois immeubles, maison bleue du plateau, bâtiment au toit vert, Centre Pokémon.
    apartment(coll, "Apartment_A", tx(12) + 0.1, tx(18) - 0.1, ay(9.75), 6.0, tx(13.6))
    apartment(coll, "Apartment_B", tx(20) + 0.1, tx(26) - 0.1, ay(9.75), 6.0, tx(21.6))
    apartment(coll, "Apartment_C", tx(6) + 0.1, tx(12) - 0.1, ay(23.85), 6.0, tx(7.6), base_z=TOWN_Z["D"])
    cross_house(coll, "BlueHouse", tx(28) + 0.2, tx(34) - 0.3, ay(8.6), ay(4.9), base_z=TOWN_Z["U"])
    gate_building(coll, "GreenGate", tx(2), tx(5.9), ay(13.6), ay(8.8))
    center_x = tx(32.5)
    center_front = pokemon_center(coll, center_x, ay(18.07))
    marker(coll, "Door_PokemonCenter", center_x, center_front - 0.5, 0,
           target="center", spawn="Spawn_Entrance", dir="up", arrive="up")
    marker(coll, "Spawn_FromCenter", center_x, center_front - 1.2, 0)
    stage(coll, "Stage", (tx(29), tx(36), ay(29), ay(22)), (tx(30), tx(35), ay(28), ay(23)), tx(32.6), ay(22.55))

    # Bordures de pierre autour du jardin et de la pelouse du plateau.
    curb(coll, "Curb_Garden", tx(13), tx(20), ay(22), ay(13), 0.0)
    curb(coll, "Curb_Lawn", tx(29), tx(35), ay(11), ay(8), TOWN_Z["U"])
    # Jardin : bancs, arbre, poubelle ; arbres en bacs entre les immeubles.
    bench(coll, "Bench_A", tx(14.5), ay(15.6))
    bench(coll, "Bench_B", tx(14.5), ay(18.8))
    place(coll, "CommonTree_2", tx(12.8), ay(16.6), 0, scale=0.45, name="Tree", collider=0.6)
    bin_ = cylinder(coll, "TrashBin", tx(12.6), ay(20.1), 0, 0.28, 0.8,
                    color_material("Bin_Dark", (0.04, 0.045, 0.05), roughness=0.5), segments=12)
    bin_["collider"] = 0.35
    # Talus boisé à l'ouest (des pins y poussent comme dans la forêt) : rochers et fougères entre
    # les arbres.
    rnd = random.Random(31)
    for _ in range(26):
        x, y = tx(rnd.random() * 6), ay(14 + rnd.random() * 14)
        model = rnd.choice(["Rock_Medium_1", "Rock_Medium_2", "Rock_Medium_3", "Fern_1", "Fern_1", "Bush_Common"])
        place(coll, model, x, y, tm.height(x, y) - 0.05, scale=rnd.uniform(0.35, 0.6), name="Talus_Decor")
    for k, (x, y, sc) in enumerate(((tx(12.5), ay(23.3), 0.55), (tx(13.4), ay(23.6), 0.45), (tx(12.9), ay(24.4), 0.4))):
        place(coll, f"Rock_Medium_{k + 1}", x, y, TOWN_Z["D"], scale=sc, name="Rock")
    for x0, x1 in ((tx(8), tx(12)), (tx(18), tx(20))):
        box(coll, "Planter_Rim", (x0 + x1) / 2, ay(9.2), 0, x1 - x0, 0.7, 0.35, bpy.data.materials["MI_RedBrick_Dark"],
            tile=1.4)

    # Habitants, panneaux, zone nommée.
    marker(coll, "NPC_OldMan", tx(19.5), ay(11.0), 0, sprite="old_man", facing="down")
    marker(coll, "NPC_AccumulaLady", tx(21.7), ay(15.6), 0, sprite="old_woman", facing="left")
    marker(coll, "NPC_TownKid", tx(27.5), ay(18.6), 0, sprite="school_kid_m", facing="down")
    marker(coll, "NPC_AccumulaMan", tx(34.5), ay(3.4), 0, sprite="middle_aged_man", facing="down")
    signpost(coll, "Sign_Arabelle", tx(28.6), ay(30.5), "ARABELLE — La ville où les gens et les Pokémon se tendent la main.")
    marker(coll, "Sign_Stage", tx(32.6), ay(22.55), 0, text="PLACE D'ARABELLE — On y donne des discours devant tout le monde.")
    signpost(coll, "Sign_Route2", tx(7.0), ay(12.6), "ROUTE 2 — Le passage est fermé pour le moment.")
    marker(coll, "Area_Arabelle", (tx(0) + tx(tm.w)) / 2, (ty(0) + ay(0)) / 2, 1, ((tx(tm.w) - tx(0)) / 2, (ay(0) - ty(0)) / 2, 1),
           label="ARABELLE")


def wind_turbine(coll, name, x, y):
    """Petite éolienne blanche ; le jeu fait tourner le rotor (repère `Turbine_Rotor`)."""
    white = color_material("Turbine_White", (0.88, 0.92, 0.95), roughness=0.4)
    blade_mat = color_material("Turbine_Blade", (0.55, 0.85, 0.92), roughness=0.4)
    pole = cylinder(coll, f"{name}_Pole", x, y, 0, 0.09, 5.2, white, segments=10)
    pole["collider"] = 0.3
    box(coll, f"{name}_Nacelle", x, y - 0.1, 5.05, 0.32, 0.65, 0.32, white)
    rotor = bpy.data.objects.new("Turbine_Rotor", None)
    rotor.location = (x, y - 0.5, 5.2)
    coll.objects.link(rotor)
    for k in range(3):
        blade = box(coll, f"{name}_Blade", 0, 0, 0.08, 0.16, 0.04, 1.5, blade_mat)
        blade.rotation_euler = (0, k * math.tau / 3, 0)
        blade.parent = rotor


def hedge(coll, name, x, y0, y1, w=0.95, h=1.5):
    """Haie taillée aux arêtes arrondies, le long d'une maison."""
    obj = box(coll, name, x, (y0 + y1) / 2, 0, w, y1 - y0, h, pixel_material("Hedge", "hedge.png"), tile=1.5, solid=True)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.28, segments=3, affect="EDGES", profile=0.5)
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def mailbox(coll, name, x, y):
    post = box(coll, f"{name}_Post", x, y, 0, 0.12, 0.12, 0.85, color_material("Mail_Post", (0.3, 0.3, 0.32)))
    post["collider"] = 0.35
    box(coll, f"{name}_Box", x, y, 0.8, 0.42, 0.55, 0.36, color_material("Mail_White", (0.82, 0.84, 0.86), 0.5))


def build_route():
    random.seed(9)
    scene = fresh_scene("Route_01")
    coll = scene.collection
    tm = TileMap(GRID, TOWN_GRID, TOWN_LEVELS)
    grass = pixel_material("Ground_Grass", "grass.png")
    rock = pixel_material("Town_Cliff", "cliff.png")
    tx = lambda col: (col - GRID_COL0) * TILE          # colonne (décimale) → x
    ty = lambda row: (tm.h - row) * TILE               # ligne (décimale) → y

    # ---- Sol : herbe, où le jeu peint le sable des chemins et les dalles d'Arabelle (bords
    # adoucis, voir src/engine/paths.js) ; lit de l'eau, falaises ; eau de l'étang et mer.
    cells = tm.all_cells()
    tile_mesh(coll, "Ground", tm, [(c, r) for c, r in cells if tm.at(c, r) not in "CRWE" and tm.town_level(c, r) != "p"],
              grass)
    tile_mesh(coll, "Ground_Bed", tm, [(c, r) for c, r in cells if tm.at(c, r) == "W"],
              color_material("Riverbed", (0.12, 0.2, 0.18)))
    tile_mesh(coll, "Cliff", tm, [(c, r) for c, r in cells if tm.at(c, r) in "CR" and r < SEAWALL_ROW], rock,
              uv_tile=2.0, top_uv=False)
    tile_mesh(coll, "Seawall", tm, [(c, r) for c, r in cells if tm.at(c, r) == "C" and r >= SEAWALL_ROW],
              pixel_material("Town_Brick", "seawall.png"), uv_tile=1.5, top_uv=False)
    pond = [(c, r) for c, r in cells if r < SEAWALL_ROW and (tm.at(c, r) == "W" or (
        tm.at(c, r) in "CR" and any(tm.at(c + a, r + b) == "W" for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))))]
    water_mesh(coll, "Water_Pond", [((tm.x(c), tm.y(r), POND_SURFACE), (tm.x(c), tm.y(r + 1), POND_SURFACE),
                                     (tm.x(c + 1), tm.y(r + 1), POND_SURFACE), (tm.x(c + 1), tm.y(r), POND_SURFACE))
                                    for c, r in pond])
    water_plane(coll, "Water_Sea", -140, 140, -120, ty(SEAWALL_ROW + 1) + 0.3, SEA_SURFACE)
    foam_strips(coll, "Foam", tm)
    # Sol hors de la grille : bandes de forêt sur les côtés et au nord d'Arabelle.
    north = ty(-tm.r0)
    for name, x0, x1, y0, y1 in (("Ground_West", -40, tx(0), ty(SEAWALL_ROW), north),
                                 ("Ground_East", tx(tm.w), 45, ty(SEAWALL_ROW), north),
                                 ("Ground_North", -40, 45, north, north + 45)):
        flat_shape(coll, name, [(x0, y1), (x0, y0), (x1, y0), (x1, y1)], 0, grass)

    # ---- Forêt : des pins sur la trame des arbres du jeu (2 cases), un peu décalés.
    gy = ty(SEAWALL_ROW) + 1.2
    while gy < north + 8:
        gx = tx(0) - 6
        while gx < tx(tm.w) + 6:
            x, y = gx + random.uniform(-0.35, 0.35), gy + random.uniform(-0.35, 0.35)
            if tm.tile_at(x, y) == "T":  # hors de la grille, tout est forêt
                model = weighted(PINES)
                place(coll, model, x, y, tm.height(x, y) - 0.1, scale=random.uniform(*PINE_SCALE), name="Tree")
            gx += 2.5
        gy += 2.5

    # ---- Petites touffes sur l'herbe rase, galets sur le sable.
    small = [("Grass_Common_Short", 5), ("Grass_Wispy_Short", 3), ("Clover_1", 2), ("Clover_2", 2)]
    for c, r in cells:
        ch = tm.at(c, r)
        if ch == "." and random.random() < 0.18:
            x, y = tx(c + random.random()), ty(r + random.random())
            place(coll, weighted(small), x, y, tm.height(x, y), scale=random.uniform(0.4, 0.6))
        elif ch == "S" and random.random() < 0.06:
            x, y = tx(c + random.random()), ty(r + random.random())
            model, scale = f"Pebble_Round_{random.randint(1, 5)}", random.uniform(0.25, 0.4)
            # Seulement au milieu du chemin : ses bords sont arrondis par le jeu.
            if all(tm.at(c + a, r + b) == "S" for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                place(coll, model, x, y, 0.03, scale=scale)

    # ---- Route 1 : clôtures blanches, escalier vers l'étang, panneaux.
    for i, (col, r0, r1) in enumerate(((33.75, 11.1, 17.6), (20.3, 25.1, 31.4), (28.6, 52.0, 58.6), (18.0, 61.4, 68.6))):
        white_fence(coll, f"Fence_{i}", tx(col), ty(r1), tx(col), ty(r0))
    stairs(coll, "Stairs", tx(20), tx(18), ty(49), ty(45), 0.0, LOWER)
    route_sign = "ROUTE 1 — ↑ Arabelle · ↓ Renouet"
    signpost(coll, "Sign_Route1_North", tx(22.9), ty(17.6), route_sign)
    signpost(coll, "Sign_Route1_Tips", tx(27.5), ty(45.3),
             "CONSEIL DE DRESSEUR : affaiblissez un Pokémon sauvage avant de lancer une Poké Ball !")
    signpost(coll, "Sign_Route1_South", tx(27.5), ty(63.1), route_sign)

    # ---- Renouet : labo du Professeur, trois maisons, haies, boîtes aux lettres, digue.
    bw_lab(coll, "Lab", tx(5) + 0.3, tx(15) - 0.3, ty(78) + 0.3, ty(72) - 0.3)
    wind_turbine(coll, "Turbine", tx(5.6), ty(79.2))
    for name, (c0, c1), door_col in (("House_Player", (14, 19), 15.9), ("House_Cheren", (7, 12), 9.06),
                                     ("House_Bianca", (20, 25), 21.8)):
        r0, r1 = (81, 86) if name == "House_Player" else (89, 94)
        bw_house(coll, name, tx(c0) + 0.25, tx(c1) - 0.25, ty(r1) + 0.25, ty(r0) - 0.25, 3.3, door_x=tx(door_col))
    for i, (col, r0, r1) in enumerate(((13.45, 83.5, 86.3), (12.55, 91.0, 94.2), (19.45, 91.0, 94.2))):
        hedge(coll, f"Hedge_{i}", tx(col), ty(r1), ty(r0))
    for i, (col, row) in enumerate(((13.0, 85.5), (6.7, 92.6), (19.6, 93.6))):
        mailbox(coll, f"Mailbox_{i}", tx(col), ty(row))
    signpost(coll, "Sign_Renouet", tx(7.9), ty(80.4), "RENOUET — Là où souffle la brise marine.")
    signpost(coll, "Sign_Lab", tx(19.2), ty(88.6), "LABORATOIRE POKéMON DU PROFESSEUR KETELEERIA ↖")
    white_fence(coll, "Seawall_Rail", tx(2.3), ty(SEAWALL_ROW) + 0.15, tx(29), ty(SEAWALL_ROW) + 0.15)
    # Margelle de pierre claire en haut de la digue, pilotis de bois dans la mer en contrebas.
    box(coll, "Seawall_Coping", (tx(0) + tx(tm.w)) / 2, ty(SEAWALL_ROW) - 0.12, -0.12, tx(tm.w) - tx(0), 0.4, 0.16,
        color_material("Seawall_Coping", (0.8, 0.68, 0.64), roughness=0.9))
    piles = color_material("Pile_Wood", (0.32, 0.2, 0.12), roughness=0.9)
    x = tx(0) + 1.0
    while x < tx(tm.w):
        cylinder(coll, "Seawall_Pile", x, ty(SEAWALL_ROW + 1) - 0.25, SEA_BED, 0.16, SEA_SURFACE - SEA_BED + 0.45, piles,
                 segments=8)
        x += 2.5

    # ---- Arabelle, au nord de la route.
    build_arabelle(coll, tm, tx, ty)

    # ---- PNJ, point de départ, zones nommées, limites.
    marker(coll, "Spawn_Player", tx(15.9), ty(86.6), 0)
    marker(coll, "NPC_Youngster", tx(24.5), ty(6.5), 0, sprite="youngster", facing="right", sight=5.0)
    marker(coll, "NPC_BugCatcher", tx(20.5), ty(19.5), 0, sprite="bug_catcher", facing="right", sight=7.0)
    marker(coll, "NPC_AceTrainer", tx(31.5), ty(44.5), 0, sprite="ace_trainer_f", facing="left", sight=8.0)
    marker(coll, "NPC_Lass", tx(21.5), ty(66.5), 0, sprite="lass", facing="right", sight=4.0)
    marker(coll, "NPC_NuvemaLady", tx(6.5), ty(87.5), 0, sprite="middle_aged_woman", facing="right")
    marker(coll, "NPC_NuvemaSailor", tx(24.5), ty(97.5), 0, sprite="sailor", facing="down")
    marker(coll, "Area_Renouet", 0, (ty(72) + ty(SEAWALL_ROW + 6)) / 2, 1, (40, (ty(72) - ty(SEAWALL_ROW + 6)) / 2, 1),
           label="RENOUET")
    marker(coll, "Area_Route1", 0, (ty(0) + ty(72)) / 2, 1, (40, (ty(0) - ty(72)) / 2, 1), label="ROUTE 1")
    marker(coll, "Bounds", (tx(0) + tx(tm.w)) / 2, (ty(SEAWALL_ROW) + north) / 2, 1,
           ((tx(tm.w) - tx(0)) / 2, (north - ty(SEAWALL_ROW)) / 2, 1))
    write_map_json(tm)
    return scene


def write_map_json(tm):
    """Grille pour le jeu (Arabelle puis Route 1 et Renouet, du nord au sud) : collisions, herbes
    hautes, fleurs, nature du sol et hauteurs (repère Three.js). Hauteurs : par case, un nombre
    si elle est plate, sinon ses quatre coins [nord-ouest, nord-est, sud-ouest, sud-est]."""
    import json
    heights = []
    for r in range(-tm.r0, tm.h):
        row = []
        for c in range(tm.w):
            nw, sw, se, ne = (round(v, 3) for v in tm.tile_corners(c, r))
            row.append(nw if nw == sw == se == ne else [nw, ne, sw, se])
        heights.append(row)
    data = {
        "tile": TILE, "originX": (0 - GRID_COL0) * TILE, "originZ": -(tm.h + tm.r0) * TILE, "cols": tm.w,
        "rows": tm.h + tm.r0, "town": tm.r0, "blocking": "".join(sorted(BLOCKING)), "grid": tm.town + tm.rows,
        "heights": heights,
    }
    with open(os.path.join(OUT, "route-01.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------- intérieurs

def room(coll, w, d, wall_h, floor_texture, trim_color, door_gap=2.4):
    """Pièce ouverte vers la caméra (au sud) : sol carrelé, trois murs hauts, mur avant bas
    percé d'une ouverture au centre, plinthes colorées et tapis d'entrée."""
    floor = pixel_material(f"Floor_{floor_texture[:-4]}", floor_texture)
    wall = pixel_material("Town_Plaster", "plaster.png")
    trim = color_material(f"Trim_{floor_texture[:-4]}", trim_color, roughness=0.5)
    box(coll, "Floor", 0, d / 2, -0.1, w, d, 0.1, floor, tile=2.0)
    box(coll, "Wall_Back", 0, d + 0.15, 0, w + 0.6, 0.3, wall_h, wall, solid=True)
    box(coll, "Trim_Back", 0, d - 0.03, 0, w, 0.06, 0.5, trim)
    seg = (w / 2 + 0.3) - door_gap / 2
    for side in (-1, 1):
        box(coll, "Wall_Side", side * (w / 2 + 0.15), d / 2, 0, 0.3, d, wall_h, wall, solid=True)
        box(coll, "Trim_Side", side * (w / 2 - 0.03), d / 2, 0, 0.06, d, 0.5, trim)
        box(coll, "Wall_Front", side * (door_gap / 2 + seg / 2), -0.15, 0, seg, 0.3, 0.9, wall, solid=True)
    box(coll, "Mat", 0, 0.75, 0, door_gap - 0.4, 1.3, 0.02, trim)


def potted_plant(coll, x, y):
    place(coll, "planter", x, y, 0, rot=0.0, scale=3.5, collider=0.6)
    place(coll, "Plant_1_Big", x, y, 0.55, scale=0.42)


def interior_markers(coll, w, d, exit_spawn, npc_name, npc_x, npc_y, sprite, facing):
    marker(coll, "Spawn_Entrance", 0, 1.6, 0)
    marker(coll, "Door_Exit", 0, 0.35, 0, target="route-01", spawn=exit_spawn, dir="down", arrive="down")
    marker(coll, npc_name, npc_x, npc_y, 0, sprite=sprite, facing=facing)
    marker(coll, "Bounds", 0, d / 2, 1, (w / 2 - 0.4, d / 2 - 0.3, 1))


def build_center():
    random.seed(21)
    scene = fresh_scene("Interior_Center")
    coll = scene.collection
    w, d = 12.0, 9.0
    room(coll, w, d, 3.2, "floor-center.png", (0.85, 0.15, 0.17))
    white = pixel_material("Town_Plaster", "plaster.png")
    red = color_material("Center_Red", (0.85, 0.15, 0.17), roughness=0.5)
    wood = color_material("Town_Wood", (0.36, 0.2, 0.08))

    # Comptoir de l'infirmière, fermé sur les côtés jusqu'au mur du fond.
    box(coll, "Counter", 0, 6.3, 0, 5.0, 0.9, 1.0, white, solid=True)
    box(coll, "Counter_Top", 0, 6.3, 1.0, 5.2, 1.1, 0.1, red)
    box(coll, "Counter_Band", 0, 5.84, 0.55, 5.02, 0.02, 0.18, red)
    for side in (-1, 1):
        box(coll, "Counter_Side", side * 2.6, 7.9, 0, 0.2, 2.3, 1.0, white, solid=True)
    # Machine de soin avec six emplacements de Poké Ball, et emblème au mur.
    box(coll, "Healer", -1.6, 8.5, 0, 1.6, 0.8, 1.2, white)
    front_plane(coll, "Healer_Screen", -1.6, 8.09, 0.8, 1.1, 0.4,
                color_material("Screen_Green", (0.2, 0.75, 0.45), roughness=0.3))
    for i in range(6):
        cylinder(coll, "Healer_Slot", -2.05 + (i % 3) * 0.45, 8.35 + (i // 3) * 0.3, 1.2, 0.13, 0.08, red, segments=10)
    front_plane(coll, "Emblem", 0.9, d - 0.04, 2.2, 1.4, 1.4, pixel_material("Center_Emblem", "emblem-ball.png"))
    # PC de stockage au fond, à gauche de la machine de soin.
    box(coll, "PC", -3.6, 8.4, 0, 1.3, 0.8, 1.0, color_material("PC_Gray", (0.55, 0.58, 0.62)), solid=True)
    box(coll, "PC_Monitor", -3.6, 8.55, 1.0, 1.0, 0.25, 0.7, color_material("PC_Gray", (0.55, 0.58, 0.62)))
    front_plane(coll, "PC_Screen", -3.6, 8.42, 1.35, 0.8, 0.5, color_material("Screen_Blue", (0.25, 0.55, 0.95), 0.3))
    # Boutique à droite, comme dans Noir et Blanc : comptoir bleu, vendeur derrière, étagère murale.
    blue = color_material("Mart_Blue", (0.18, 0.4, 0.85), roughness=0.5)
    box(coll, "Shop_Counter", 4.3, 5.4, 0, 0.9, 3.0, 1.0, white, solid=True)
    box(coll, "Shop_CounterTop", 4.3, 5.4, 1.0, 1.1, 3.2, 0.1, blue)
    for y in (3.75, 7.05):
        box(coll, "Shop_CounterEnd", 5.15, y, 0, 1.7, 0.3, 1.0, white, solid=True)
    box(coll, "Register", 4.3, 6.2, 1.1, 0.5, 0.4, 0.3, color_material("PC_Gray", (0.55, 0.58, 0.62)))
    box(coll, "Shop_Shelf", 5.75, 5.4, 0, 0.45, 2.8, 1.9, color_material("Shelf", (0.86, 0.83, 0.77)), solid=True)
    products = [color_material(f"Product_{i}", c, roughness=0.6) for i, c in enumerate(
        [(0.9, 0.25, 0.2), (0.2, 0.5, 0.9), (0.95, 0.75, 0.2), (0.3, 0.75, 0.4), (0.75, 0.4, 0.85), (0.95, 0.95, 0.92)])]
    for z in (0.3, 0.8, 1.3):
        for i in range(7):
            box(coll, "Product", 5.45, 4.25 + i * 0.36, z, 0.14, 0.26, 0.34, random.choice(products))
    marker(coll, "NPC_Clerk", 5.15, 5.4, 0, sprite="cashier_m", facing="left")
    # Coin salon : deux banquettes et une table basse.
    for y in (2.4, 4.6):
        box(coll, "Sofa", -4.95, y, 0, 1.0, 1.6, 0.45, red, solid=True)
        box(coll, "Sofa_Back", -5.55, y, 0.45, 0.2, 1.6, 0.5, red)
    box(coll, "Table", -3.75, 3.5, 0, 0.8, 1.3, 0.45, wood, solid=True)
    for x, y in ((-5.2, 8.3), (3.0, 8.4), (-5.2, 1.0), (5.2, 1.0)):
        potted_plant(coll, x, y)

    marker(coll, "Spawn_Counter", 0, 5.2, 0)
    interior_markers(coll, w, d, "Spawn_FromCenter", "NPC_Nurse", 0, 7.2, "pokecenter_nurse", "down")
    return scene


# ---------------------------------------------------------------- export

def export(scene, filename):
    bpy.context.window.scene = scene
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=os.path.join(OUT, filename), export_format="GLB", use_active_scene=True,
        export_extras=True, export_cameras=True, export_lights=False, export_yup=True,
        export_apply=False, export_animations=False,
    )


def main():
    ensure_library()
    green_foliage()
    village_materials()
    battle, route = build_battle(), build_route()
    center = build_center()
    old = bpy.data.scenes.get("Interior_Mart")  # ancienne boutique séparée : elle est dans le Centre
    if old:
        for o in list(old.collection.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.scenes.remove(old)
    bpy.data.orphans_purge(do_recursive=True)
    export(battle, "battle-forest.glb")
    export(route, "route-01.glb")
    export(center, "center.glb")
    bpy.context.window.scene = battle
    os.makedirs(os.path.dirname(BLEND), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, relative_remap=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile()
    return {s.name: len(s.collection.all_objects) for s in (battle, route, center)}


result = main()
