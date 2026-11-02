"""BFRES model -> glTF 2.0 binary (.glb).

* Units and axes are kept exactly as stored in the BFRES (Y-up, right handed).
* Every bone becomes a node; one skin covers the whole skeleton.
* Vertex skinning follows BFRES rules: skin_count 0 -> vertices are in the
  space of shape.bone, 1 -> in the space of the rigid matrix's bone, >=2 ->
  model space with smooth matrices. _i0/_i1 index skeleton.matrix_to_bone.
* Only LOD 0 becomes the glTF mesh; the LOD count is kept in extras.
* Materials carry the full FMAT (shader options, params, render info, all
  texture slots) in extras for the Park_UBER port; the glTF PBR slots are
  filled only from what the sampler names say (_a0 albedo, _n0 normal).
"""
import json
import math
import struct

# ---- small affine matrix helpers (row-major 4x4 as flat lists) -------------


def _mat_trs(t, r, s):
    x, y, z, w = r
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz, wx, wy, wz = x * y, x * z, y * z, w * x, w * y, w * z
    rot = [1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy),
           2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx),
           2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy)]
    return [rot[0] * s[0], rot[1] * s[1], rot[2] * s[2], t[0],
            rot[3] * s[0], rot[4] * s[1], rot[5] * s[2], t[1],
            rot[6] * s[0], rot[7] * s[1], rot[8] * s[2], t[2],
            0.0, 0.0, 0.0, 1.0]


def _mul(a, b):
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4)]


def _inv_affine(m):
    a, b, c, d, e, f, g, h, i = m[0], m[1], m[2], m[4], m[5], m[6], m[8], m[9], m[10]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-12:
        det = 1e-12
    inv = [(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det,
           (f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det,
           (d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det]
    t = [m[3], m[7], m[11]]
    it = [-(inv[0] * t[0] + inv[1] * t[1] + inv[2] * t[2]),
          -(inv[3] * t[0] + inv[4] * t[1] + inv[5] * t[2]),
          -(inv[6] * t[0] + inv[7] * t[1] + inv[8] * t[2])]
    return [inv[0], inv[1], inv[2], it[0], inv[3], inv[4], inv[5], it[1],
            inv[6], inv[7], inv[8], it[2], 0.0, 0.0, 0.0, 1.0]


def _xform_point(m, p):
    return (m[0] * p[0] + m[1] * p[1] + m[2] * p[2] + m[3],
            m[4] * p[0] + m[5] * p[1] + m[6] * p[2] + m[7],
            m[8] * p[0] + m[9] * p[1] + m[10] * p[2] + m[11])


def _xform_dir(m, v):
    x = m[0] * v[0] + m[1] * v[1] + m[2] * v[2]
    y = m[4] * v[0] + m[5] * v[1] + m[6] * v[2]
    z = m[8] * v[0] + m[9] * v[1] + m[10] * v[2]
    n = math.sqrt(x * x + y * y + z * z) or 1.0
    return (x / n, y / n, z / n)


# ---- glb builder -----------------------------------------------------------


class _Glb:
    def __init__(self):
        self.bin = bytearray()
        self.gltf = {"asset": {"version": "2.0", "generator": "acnh_rip"},
                     "buffers": [{}], "bufferViews": [], "accessors": []}

    def accessor(self, values, ctype, typ, target=None, minmax=False, normalized=False):
        fmt = {5126: "f", 5123: "H", 5125: "I", 5121: "B"}[ctype]
        comps = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[typ]
        flat = values if comps == 1 else [c for v in values for c in v]
        while len(self.bin) % 4:
            self.bin.append(0)
        off = len(self.bin)
        self.bin += struct.pack(f"<{len(flat)}{fmt}", *flat)
        bv = {"buffer": 0, "byteOffset": off, "byteLength": len(self.bin) - off}
        if target:
            bv["target"] = target
        self.gltf["bufferViews"].append(bv)
        acc = {"bufferView": len(self.gltf["bufferViews"]) - 1, "componentType": ctype,
               "count": len(values), "type": typ}
        if normalized:
            acc["normalized"] = True
        if minmax:
            acc["min"] = [min(v[i] for v in values) for i in range(comps)]
            acc["max"] = [max(v[i] for v in values) for i in range(comps)]
        self.gltf["accessors"].append(acc)
        return len(self.gltf["accessors"]) - 1

    def write(self, path):
        while len(self.bin) % 4:
            self.bin.append(0)
        self.gltf["buffers"][0]["byteLength"] = len(self.bin)
        js = json.dumps(self.gltf, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        while len(js) % 4:
            js += b" "
        total = 12 + 8 + len(js) + 8 + len(self.bin)
        with open(path, "wb") as f:
            f.write(struct.pack("<4sII", b"glTF", 2, total))
            f.write(struct.pack("<I4s", len(js), b"JSON") + js)
            f.write(struct.pack("<I4s", len(self.bin), b"BIN\0") + bytes(self.bin))


def _alpha_mode(mat):
    ri = mat.get("render_info", {})
    mode = (ri.get("gsys_render_state_mode") or ["opaque"])[0]
    if mode in ("translucent", "xlu", "custom") and (ri.get("gsys_render_state_blend_preset") or ["none"])[0] != "none":
        return "BLEND"
    if (ri.get("gsys_alpha_test_enable") or ["false"])[0] == "true" or mode == "mask":
        return "MASK"
    return "OPAQUE"


def export_model(bf, model, out_path, texture_uri):
    """texture_uri(name) -> relative uri string or None when the texture lives elsewhere."""
    g = _Glb()
    gl = g.gltf
    sk = model["skeleton"]
    bones = sk["bones"]
    # nodes
    world = []
    nodes = []
    for b in bones:
        local = _mat_trs(b["translation"], b["rotation"], b["scale"])
        world.append(_mul(world[b["parent"]], local) if b["parent"] >= 0 else local)
        nodes.append({"name": b["name"], "translation": list(b["translation"]),
                      "rotation": [float(v) for v in b["rotation"]], "scale": list(b["scale"])})
    for i, b in enumerate(bones):
        if b["parent"] >= 0:
            nodes[b["parent"]].setdefault("children", []).append(i)
    roots = [i for i, b in enumerate(bones) if b["parent"] < 0]
    ibm = [_inv_affine(w) for w in world]
    # glTF stores matrices column-major
    ibm_cm = [[m[r * 4 + c] for c in range(4) for r in range(4)] for m in ibm]
    skin = {"joints": list(range(len(bones))),
            "inverseBindMatrices": g.accessor(ibm_cm, 5126, "MAT4")}
    if roots:
        skin["skeleton"] = roots[0]
    gl["skins"] = [skin]

    # images / textures / materials
    images, tex_index = [], {}

    def tex(name):
        if name in tex_index:
            return tex_index[name]
        uri = texture_uri(name)
        if uri is None:
            return None
        images.append({"uri": uri, "name": name})
        gl.setdefault("textures", []).append({"source": len(images) - 1})
        tex_index[name] = len(images) - 1
        return tex_index[name]

    materials = []
    for m in model["materials"]:
        slots = {}
        for i, s in enumerate(m["samplers"]):
            if i < len(m["textures"]):
                slots[s["name"]] = m["textures"][i]
        gm = {"name": m["name"], "pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 1.0},
              "alphaMode": _alpha_mode(m),
              "doubleSided": (m["render_info"].get("gsys_render_state_display_face") or ["front"])[0] == "both"}
        if "_a0" in slots:
            t = tex(slots["_a0"])
            if t is not None:
                gm["pbrMetallicRoughness"]["baseColorTexture"] = {"index": t}
        if "_n0" in slots:
            t = tex(slots["_n0"])
            if t is not None:
                gm["normalTexture"] = {"index": t}
        gm["extras"] = {"texture_slots": slots, "shader": m.get("shader"), "render_info": m["render_info"],
                        "params": m["params"], "samplers": m["samplers"]}
        materials.append(gm)
    if images:
        gl["images"] = images
    gl["materials"] = materials

    # meshes: one glTF mesh node per shape
    mesh_nodes = []
    m2b = sk["matrix_to_bone"]
    for s in model["shapes"]:
        vb = s["vb"]
        attrs = vb["attrs"]
        pos = bf.read_attribute(vb, "_p0")
        pos = [p[:3] for p in pos]
        nrm = [n[:3] for n in bf.read_attribute(vb, "_n0")] if "_n0" in attrs else None
        n = len(pos)
        sc = s["skin_count"]
        joints = weights = None
        if sc == 0 or sc == 1:
            if sc == 0:
                bidx = [s["bone"]] * n
            else:
                bidx = [m2b[i[0]] for i in bf.read_attribute(vb, "_i0")]
            pos = [_xform_point(world[b], p) for b, p in zip(bidx, pos)]
            if nrm:
                nrm = [_xform_dir(world[b], v) for b, v in zip(bidx, nrm)]
            joints = [(b, 0, 0, 0) for b in bidx]
            weights = [(1.0, 0.0, 0.0, 0.0)] * n
        else:
            idx = bf.read_attribute(vb, "_i0")
            wts = bf.read_attribute(vb, "_w0") if "_w0" in attrs else [(1.0,)] * n
            joints, weights = [], []
            for iv, wv in zip(idx, wts):
                j = [m2b[iv[k]] if k < min(sc, len(iv)) else 0 for k in range(4)]
                w = [wv[k] if k < min(sc, len(wv)) else 0.0 for k in range(4)]
                tot = sum(w) or 1.0
                joints.append(tuple(j))
                weights.append(tuple(v / tot for v in w))
        prim = {"attributes": {"POSITION": g.accessor(pos, 5126, "VEC3", 34962, minmax=True)},
                "material": s["material"], "mode": 4}
        if nrm:
            prim["attributes"]["NORMAL"] = g.accessor(nrm, 5126, "VEC3", 34962)
        for k in range(4):
            name = f"_u{k}"
            if name in attrs:
                prim["attributes"][f"TEXCOORD_{k}"] = g.accessor([u[:2] for u in bf.read_attribute(vb, name)],
                                                                 5126, "VEC2", 34962)
        if "_t0" in attrs and nrm:
            tans = []
            for t in bf.read_attribute(vb, "_t0"):
                l = math.sqrt(t[0] ** 2 + t[1] ** 2 + t[2] ** 2) or 1.0
                tans.append((t[0] / l, t[1] / l, t[2] / l, -1.0 if len(t) > 3 and t[3] < 0 else 1.0))
            if sc in (0, 1):
                tans = [(*_xform_dir(world[j[0]], t[:3]), t[3]) for j, t in zip(joints, tans)]
            prim["attributes"]["TANGENT"] = g.accessor(tans, 5126, "VEC4", 34962)
        if "_c0" in attrs:
            prim["attributes"]["COLOR_0"] = g.accessor([tuple((c + (1.0,) * 4)[:4]) for c in bf.read_attribute(vb, "_c0")],
                                                       5126, "VEC4", 34962)
        prim["attributes"]["JOINTS_0"] = g.accessor(joints, 5123, "VEC4", 34962)
        prim["attributes"]["WEIGHTS_0"] = g.accessor(weights, 5126, "VEC4", 34962)
        lod0 = s["lods"][0]
        if lod0["primitive"] != 3:
            raise ValueError(f"unexpected primitive type {lod0['primitive']}")
        prim["indices"] = g.accessor(lod0["indices"], 5125 if n > 65535 else 5123, "SCALAR", 34963)
        gl.setdefault("meshes", []).append({"name": s["name"], "primitives": [prim],
                                            "extras": {"lod_count": len(s["lods"]), "skin_count": sc}})
        nodes.append({"name": s["name"], "mesh": len(gl["meshes"]) - 1, "skin": 0})
        mesh_nodes.append(len(nodes) - 1)

    gl["nodes"] = nodes
    gl["scenes"] = [{"name": model["name"], "nodes": roots + mesh_nodes}]
    gl["scene"] = 0
    gl["extras"] = {"source": "bfres", "skeleton_flags": sk["flags"]}
    g.write(out_path)
    return {"shapes": len(model["shapes"]), "bones": len(bones), "materials": len(materials),
            "textures_linked": len(images)}
