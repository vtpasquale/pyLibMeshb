"""
Generic dictionary-driven read/write for .mesh/.meshb and .sol/.solb files
via the LibMeshb C library (libmeshb8.c / libmeshb8.h).

The module uses the bundled libMeshb C library through ``ctypes`` and provides
four main functions:

    list_types(path=None)
        List registered entity names, or entities present in a file.

    read(path, types=None)
        Read selected entities, or automatically detect registered entities.

    write(path, data, version=3, dim=None)
        Write registered entities to a mesh or solution file.

    mesh_info(path)
        Print and return basic file metadata.

The ``TYPES`` registry maps entity names to libMeshb keywords and
describes their data layout:

    vertex
        Floating-point coordinates followed by an integer reference.

    element
        Fixed-width integer vertex indices, optionally followed by a reference.

    solution
        Real-valued fields described by libMeshb field types:
        ``GmfSca``, ``GmfVec``, ``GmfSymMat``, and ``GmfMat``.

    integer
        Fixed-width integer records such as ``ISolAt*`` keywords.

Only keywords registered in ``TYPES`` are supported.
"""

import ctypes
import os
import re
import sys
import importlib.resources
from ctypes import c_char_p, c_int, c_int64, c_void_p, byref
import numpy as np

GmfRead, GmfWrite = 1, 2
GmfSca, GmfVec, GmfSymMat, GmfMat = 1, 2, 3, 4
GmfFloat, GmfDouble, GmfInt, GmfLong = 8, 9, 10, 11
GmfFloatVec, GmfDoubleVec, GmfIntVec, GmfLongVec = 12, 13, 14, 15

# ----------------------------------------------------------------------------
# Entity registry -- the ONLY place that needs to change to support a new
# mesh/solution keyword.
# ----------------------------------------------------------------------------
TYPES = {
    "vertices":              {"kwd": "GmfVertices",       "kind": "vertex"},

    "edges":                 {"kwd": "GmfEdges",           "kind": "element", "n_verts": 2, "has_ref": True},
    "triangles":              {"kwd": "GmfTriangles",       "kind": "element", "n_verts": 3, "has_ref": True},
    "quadrilaterals":         {"kwd": "GmfQuadrilaterals",  "kind": "element", "n_verts": 4, "has_ref": True},
    "tetrahedra":             {"kwd": "GmfTetrahedra",      "kind": "element", "n_verts": 4, "has_ref": True},
    "pyramids":               {"kwd": "GmfPyramids",        "kind": "element", "n_verts": 5, "has_ref": True},
    "prisms":                 {"kwd": "GmfPrisms",          "kind": "element", "n_verts": 6, "has_ref": True},
    "hexahedra":               {"kwd": "GmfHexahedra",       "kind": "element", "n_verts": 8, "has_ref": True},
    "corners":                 {"kwd": "GmfCorners",         "kind": "element", "n_verts": 1, "has_ref": False},
    "ridges":                  {"kwd": "GmfRidges",          "kind": "element", "n_verts": 1, "has_ref": False},

    "sol_at_vertices":         {"kwd": "GmfSolAtVertices",       "kind": "solution"},
    "sol_at_edges":            {"kwd": "GmfSolAtEdges",          "kind": "solution"},
    "sol_at_triangles":        {"kwd": "GmfSolAtTriangles",      "kind": "solution"},
    "sol_at_quadrilaterals":   {"kwd": "GmfSolAtQuadrilaterals", "kind": "solution"},
    "sol_at_tetrahedra":       {"kwd": "GmfSolAtTetrahedra",     "kind": "solution"},
    "sol_at_pyramids":         {"kwd": "GmfSolAtPyramids",       "kind": "solution"},
    "sol_at_prisms":           {"kwd": "GmfSolAtPrisms",         "kind": "solution"},
    "sol_at_hexahedra":        {"kwd": "GmfSolAtHexahedra",      "kind": "solution"},
    "dsol_at_vertices":        {"kwd": "GmfDSolAtVertices",      "kind": "solution"},
    "isol_at_vertices":       {"kwd": "GmfISolAtVertices",      "kind": "integer", "n_cols": 1},
    "isol_at_edges":          {"kwd": "GmfISolAtEdges",         "kind": "integer", "n_cols": 2},
    "isol_at_triangles":      {"kwd": "GmfISolAtTriangles",     "kind": "integer", "n_cols": 3},
    "isol_at_quadrilaterals": {"kwd": "GmfISolAtQuadrilaterals","kind": "integer", "n_cols": 4},
    "isol_at_tetrahedra":     {"kwd": "GmfISolAtTetrahedra",    "kind": "integer", "n_cols": 4},
    "isol_at_pyramids":       {"kwd": "GmfISolAtPyramids",      "kind": "integer", "n_cols": 5},
    "isol_at_prisms":         {"kwd": "GmfISolAtPrisms",        "kind": "integer", "n_cols": 6},
    "isol_at_hexahedra":      {"kwd": "GmfISolAtHexahedra",      "kind": "integer", "n_cols": 8},
}

# ----------------------------------------------------------------------------
# Parse GmfKwdCod enum straight out of the header so keyword indices never
# drift out of sync with the installed library.
# ----------------------------------------------------------------------------
def parse_keyword_enum(header_path):
    text = header_path.read_text()
    m = re.search(r"enum\s+GmfKwdCod\s*\{(.*?)\};", text, re.S)
    if not m:
        raise RuntimeError("Could not locate 'enum GmfKwdCod' in header")
    names = [tok.strip() for tok in m.group(1).split(",") if tok.strip()]
    return {name: idx for idx, name in enumerate(names)}


class LibMeshb:
    def __init__(self, lib_path):
        self.lib = ctypes.CDLL(lib_path)
        self.lib.GmfOpenMesh.argtypes = [c_char_p, c_int]
        self.lib.GmfOpenMesh.restype = c_int64
        self.lib.GmfStatKwd.argtypes = [c_int64, c_int]
        self.lib.GmfStatKwd.restype = c_int64
        self.lib.GmfSetKwd.argtypes = [c_int64, c_int, c_int64]
        self.lib.GmfSetKwd.restype = c_int
        self.lib.GmfCloseMesh.argtypes = [c_int64]
        self.lib.GmfCloseMesh.restype = c_int
        self.lib.GmfGotoKwd.argtypes = [c_int64, c_int]
        self.lib.GmfGotoKwd.restype = c_int
        block_argtypes = [c_int64, c_int, c_int64, c_int64,
                  c_int, c_void_p, c_void_p]
        self.lib.GmfGetBlock.argtypes = block_argtypes
        self.lib.GmfGetBlock.restype = c_int
        self.lib.GmfSetBlock.argtypes = block_argtypes
        self.lib.GmfSetBlock.restype = c_int
        self.lib.GmfGetFloatPrecision.argtypes = [c_int64]
        self.lib.GmfGetFloatPrecision.restype = c_int

    def open_mesh_read(self, path):
        ver, dim = c_int(0), c_int(0)
        handle = self.lib.GmfOpenMesh(os.fsencode(path), c_int(GmfRead), byref(ver), byref(dim))
        if handle == 0:
            raise IOError(f"GmfOpenMesh failed to open '{path}'")
        return handle, ver.value, dim.value

    def open_mesh_write(self, path, version, dim):
        handle = self.lib.GmfOpenMesh(os.fsencode(path), c_int(GmfWrite), c_int(version), c_int(dim))
        if handle == 0:
            raise IOError(f"GmfOpenMesh failed to create '{path}'")
        return handle

    def close_mesh(self, handle):
        self.lib.GmfCloseMesh(c_int64(handle))

    def stat_kwd(self, handle, kwd):
        return self.lib.GmfStatKwd(c_int64(handle), c_int(kwd))

    def stat_kwd_solution(self, handle, kwd, max_types=1000):
        n_types, sol_size = c_int(0), c_int(0)
        type_tab = (c_int * max_types)()
        n_lines = self.lib.GmfStatKwd(c_int64(handle), c_int(kwd), byref(n_types), byref(sol_size), type_tab)
        return n_lines, n_types.value, sol_size.value, list(type_tab[: n_types.value])

    def set_kwd(self, handle, kwd, n_lines):
        ok = self.lib.GmfSetKwd(c_int64(handle), c_int(kwd), c_int64(n_lines))
        if not ok and n_lines > 0:
            raise RuntimeError(f"GmfSetKwd failed for keyword id {kwd}")

    def set_kwd_solution(self, handle, kwd, n_lines, type_tab):
        type_arr = (c_int * len(type_tab))(*type_tab)
        ok = self.lib.GmfSetKwd(c_int64(handle), c_int(kwd), c_int64(n_lines), c_int(len(type_tab)), type_arr)
        if not ok and n_lines > 0:
            raise RuntimeError(f"GmfSetKwd (solution) failed for keyword id {kwd}")

    def goto_kwd(self, handle, kwd):
        if not self.lib.GmfGotoKwd(c_int64(handle), c_int(kwd)):
            raise RuntimeError(f"GmfGotoKwd failed for keyword id {kwd}")

    def float_precision(self, handle):
        return self.lib.GmfGetFloatPrecision(c_int64(handle))

    @staticmethod
    def _build_block_argv(handle, kwd, n_lines, fields):
        argv = [c_int64(handle), c_int(kwd), c_int64(1), c_int64(n_lines),
                c_int(0), c_void_p(None), c_void_p(None)]
        for field in fields:
            if field[0] == "scalar":
                _, type_code, arr = field
                first = arr.ctypes.data
                last = first + (n_lines - 1) * arr.itemsize if n_lines > 1 else first
                argv += [c_int(type_code), c_void_p(first), c_void_p(last)]
            elif field[0] == "vec":
                _, type_code_vec, count, arr2d = field
                stride = arr2d.strides[0]
                first = arr2d.ctypes.data
                last = first + (n_lines - 1) * stride if n_lines > 1 else first
                argv += [c_int(type_code_vec), c_int(count), c_void_p(first), c_void_p(last)]
            else:
                raise ValueError(f"Unknown field kind: {field[0]}")
        return argv

    def get_block(self, handle, kwd, n_lines, fields):
        if not self.lib.GmfGetBlock(*self._build_block_argv(handle, kwd, n_lines, fields)):
            raise RuntimeError(f"GmfGetBlock failed for keyword id {kwd}")

    def set_block(self, handle, kwd, n_lines, fields):
        if not self.lib.GmfSetBlock(*self._build_block_argv(handle, kwd, n_lines, fields)):
            raise RuntimeError(f"GmfSetBlock failed for keyword id {kwd}")


def scalar_field(type_code, arr):
    return ("scalar", type_code, arr)


def vec_field(type_code_vec, count, arr2d):
    return ("vec", type_code_vec, count, arr2d)


def _keyword_count(handle, spec):
    kwd = KWD[spec["kwd"]]
    if spec["kind"] == "solution":
        count, _, _, _ = LM.stat_kwd_solution(handle, kwd)
    else:
        count = LM.stat_kwd(handle, kwd)
    return count


# ----------------------------------------------------------------------------
# Module setup
# ----------------------------------------------------------------------------
HEADER_PATH = importlib.resources.files("pyLibMeshb") / "libmeshb8.h"
KWD = parse_keyword_enum(HEADER_PATH)
_suffix = "_libmeshb.dll" if sys.platform.startswith("win") else "_libmeshb.so"
_lib_path = importlib.resources.files("pyLibMeshb") / _suffix
if not _lib_path.is_file():
    raise ImportError(f"Compiled library '{_suffix}' not found in pyLibMeshb package.")
LM = LibMeshb(str(_lib_path))

_TYPE_WIDTH = {GmfSca: 1, GmfVec: None, GmfSymMat: None, GmfMat: None}  # Vec/SymMat/Mat widths depend on dim


def _field_width(type_code, dim):
    if type_code == GmfSca:
        return 1
    if type_code == GmfVec:
        return dim
    if type_code == GmfSymMat:
        return dim * (dim + 1) // 2
    if type_code == GmfMat:
        return dim * dim
    raise ValueError(f"Unknown solution field type code {type_code}")


def _validate_matrix(payload, name, n_cols):
    arr = np.asarray(payload)
    if arr.ndim != 2 or arr.shape[1] != n_cols:
        raise ValueError(
            f"'{name}' must be a 2D array with {n_cols} columns; "
            f"got shape {arr.shape}"
        )
    return arr


def _validate_solution(payload, name, dim):
    if not isinstance(payload, dict) or "values" not in payload:
        raise ValueError(f"'{name}' must be a dict containing a 'values' array")

    values = np.asarray(payload["values"])
    if values.ndim not in (1, 2):
        raise ValueError(f"'{name}[values]' must be a 1D or 2D array; got shape {values.shape}")
    values = np.atleast_2d(values)
    sol_size = values.shape[1]

    field_types = payload.get("field_types")
    if field_types is None:
        field_types = [GmfSca] * sol_size
    else:
        try:
            field_types = list(field_types)
        except TypeError as exc:
            raise ValueError(f"'{name}[field_types]' must be an iterable of field type codes") from exc

    if not field_types:
        raise ValueError(f"'{name}[field_types]' must not be empty")
    expected_size = sum(_field_width(type_code, dim) for type_code in field_types)
    if expected_size != sol_size:
        raise ValueError(
            f"'{name}[values]' has {sol_size} columns, but field_types require {expected_size}"
        )
    return values, field_types


# ----------------------------------------------------------------------------
# 1. list_types
# ----------------------------------------------------------------------------
def list_types(path=None):
    """
    With no path: return every entity name this module knows how to read/write.
    With a path: open the file and return only the entity names actually
    present (line count > 0).
    """
    if path is None:
        return sorted(TYPES.keys())

    handle, ver, dim = LM.open_mesh_read(path)
    try:
        present = []
        for name, spec in TYPES.items():
            n = _keyword_count(handle, spec)
            if n > 0:
                present.append(name)
        return sorted(present)
    finally:
        LM.close_mesh(handle)

# ----------------------------------------------------------------------------
# 2. read
# ----------------------------------------------------------------------------
def read(path, types=None):
    """
    Read one or more entity types from a .mesh/.meshb or .sol/.solb file.

    types : iterable of names from TYPES (e.g. ['vertices','triangles']).
            If None, auto-detects every registered type present in the file.

    Returns a dict:
        {'version': int, 'dim': int,
         'vertices': (N, dim+1) float64 array,      # coords..., ref
         'triangles': (M, n_verts[+1]) int64 array, # v0..vk[, ref]
         'sol_at_vertices': {'values': (N, sol_size) float64,
                              'field_types': [GmfSca, GmfVec, ...]},
         ...}
    """
    handle, ver, dim = LM.open_mesh_read(path)
    if types is None:
        types = [name for name, spec in TYPES.items()
                 if _keyword_count(handle, spec) > 0]

    float_bits = LM.float_precision(handle)
    float_dtype = np.float32 if float_bits == 32 else np.float64
    float_code = GmfFloat if float_bits == 32 else GmfDouble
    float_code_vec = GmfFloatVec if float_bits == 32 else GmfDoubleVec
    int_dtype = np.int32 if ver < 4 else np.int64
    int_code = GmfInt if ver < 4 else GmfLong

    result = {"version": ver, "dim": dim}
    try:
        for name in types:
            spec = TYPES[name]
            kwd = KWD[spec["kwd"]]

            if spec["kind"] == "vertex":
                n = LM.stat_kwd(handle, kwd)
                arr = np.empty((n, dim + 1), dtype=np.float64)
                if n > 0:
                    cols = [np.empty(n, dtype=float_dtype) for _ in range(dim)]
                    ref = np.empty(n, dtype=int_dtype)
                    LM.goto_kwd(handle, kwd)
                    LM.get_block(handle, kwd, n,
                                 [scalar_field(float_code, c) for c in cols] +
                                 [scalar_field(int_code, ref)])
                    for i, c in enumerate(cols):
                        arr[:, i] = c
                    arr[:, dim] = ref
                result[name] = arr

            elif spec["kind"] == "element":
                n = LM.stat_kwd(handle, kwd)
                n_cols = spec["n_verts"] + (1 if spec["has_ref"] else 0)
                arr = np.empty((n, n_cols), dtype=np.int64)
                if n > 0:
                    cols = [np.empty(n, dtype=int_dtype) for _ in range(n_cols)]
                    LM.goto_kwd(handle, kwd)
                    LM.get_block(handle, kwd, n, [scalar_field(int_code, c) for c in cols])
                    for i, c in enumerate(cols):
                        arr[:, i] = c
                result[name] = arr

            elif spec["kind"] == "integer":
                n = LM.stat_kwd(handle, kwd)
                arr = np.empty((n, spec["n_cols"]), dtype=np.int64)
                if n > 0:
                    cols = [np.empty(n, dtype=int_dtype)
                            for _ in range(spec["n_cols"])]
                    LM.goto_kwd(handle, kwd)
                    LM.get_block(handle, kwd, n,
                                 [scalar_field(int_code, col) for col in cols])
                    for i, col in enumerate(cols):
                        arr[:, i] = col
                result[name] = arr

            elif spec["kind"] == "solution":
                n, n_types_, sol_size, field_types = LM.stat_kwd_solution(handle, kwd)
                if n == 0:
                    result[name] = {"values": np.empty((0, 0)), "field_types": field_types}
                    continue
                buf = np.empty((n, sol_size), dtype=float_dtype)
                LM.goto_kwd(handle, kwd)
                LM.get_block(handle, kwd, n, [vec_field(float_code_vec, sol_size, buf)])
                result[name] = {"values": buf.astype(np.float64, copy=False),
                                 "field_types": field_types}
            else:
                raise ValueError(f"Unknown kind for type '{name}'")
    finally:
        LM.close_mesh(handle)

    return result


# ----------------------------------------------------------------------------
# 3. write
# ----------------------------------------------------------------------------
def write(path, data, version=3, dim=None):
    """
    Write one or more entity types to a .mesh/.meshb or .sol/.solb file.

    data : dict using the same shapes as returned by read(), e.g.
        {'vertices': (N, dim+1) array, 'triangles': (M, 4) array,
         'sol_at_vertices': {'values': (N, sol_size) array,
                              'field_types': [GmfSca]*sol_size}}   # optional
    version : file format version (1-4).
    dim : spatial dimension; if None, inferred from data['vertices'] width - 1,
          else defaults to 2.
    """
    if not isinstance(data, dict):
        raise ValueError("data must be a dictionary")
    if version not in (1, 2, 3, 4):
        raise ValueError(f"version must be one of 1, 2, 3, or 4; got {version}")

    if dim is None:
        if "vertices" in data:
            vertices = np.asarray(data["vertices"])
            if vertices.ndim != 2:
                raise ValueError(f"'vertices' must be a 2D array; got shape {vertices.shape}")
            dim = vertices.shape[1] - 1
        else:
            dim = 2
    if dim not in (2, 3):
        raise ValueError(f"dim must be 2 or 3; got {dim}")

    for name, payload in data.items():
        if name in ("version", "dim"):
            continue
        if name not in TYPES:
            raise ValueError(f"Unknown data type '{name}'")
        spec = TYPES[name]
        if spec["kind"] == "vertex":
            _validate_matrix(payload, name, dim + 1)
        elif spec["kind"] == "element":
            _validate_matrix(payload, name,
                             spec["n_verts"] + (1 if spec["has_ref"] else 0))
        elif spec["kind"] == "integer":
            _validate_matrix(payload, name, spec["n_cols"])
        elif spec["kind"] == "solution":
            _validate_solution(payload, name, dim)

    handle = LM.open_mesh_write(path, version, dim)
    float_dtype = np.float32 if version == 1 else np.float64
    float_code = GmfFloat if version == 1 else GmfDouble
    float_code_vec = GmfFloatVec if version == 1 else GmfDoubleVec
    int_dtype = np.int32 if version < 4 else np.int64
    int_code = GmfInt if version < 4 else GmfLong

    try:
        for name, payload in data.items():
            if name in ("version", "dim"):
                continue
            spec = TYPES[name]
            kwd = KWD[spec["kwd"]]

            if spec["kind"] == "vertex":
                arr = _validate_matrix(payload, name, dim + 1).astype(np.float64, copy=False)
                n = arr.shape[0]
                if n == 0:
                    continue
                cols = [np.ascontiguousarray(arr[:, i], dtype=float_dtype) for i in range(dim)]
                ref = np.ascontiguousarray(arr[:, dim], dtype=int_dtype)
                LM.set_kwd(handle, kwd, n)
                LM.set_block(handle, kwd, n,
                             [scalar_field(float_code, c) for c in cols] +
                             [scalar_field(int_code, ref)])

            elif spec["kind"] == "element":
                n_cols = spec["n_verts"] + (1 if spec["has_ref"] else 0)
                arr = _validate_matrix(payload, name, n_cols).astype(np.int64, copy=False)
                n = arr.shape[0]
                if n == 0:
                    continue
                cols = [np.ascontiguousarray(arr[:, i], dtype=int_dtype) for i in range(n_cols)]
                LM.set_kwd(handle, kwd, n)
                LM.set_block(handle, kwd, n, [scalar_field(int_code, c) for c in cols])

            elif spec["kind"] == "integer":
                arr = _validate_matrix(payload, name, spec["n_cols"]).astype(np.int64, copy=False)
                n = arr.shape[0]
                if n == 0:
                    continue
                cols = [np.ascontiguousarray(arr[:, i], dtype=int_dtype)
                        for i in range(spec["n_cols"])]
                LM.set_kwd(handle, kwd, n)
                LM.set_block(handle, kwd, n,
                             [scalar_field(int_code, c) for c in cols])

            elif spec["kind"] == "solution":
                values, field_types = _validate_solution(payload, name, dim)
                values = values.astype(np.float64, copy=False)
                n, sol_size = values.shape
                if n == 0:
                    continue
                LM.set_kwd_solution(handle, kwd, n, field_types)
                buf = np.ascontiguousarray(values, dtype=float_dtype)
                LM.set_block(handle, kwd, n, [vec_field(float_code_vec, sol_size, buf)])
            else:
                raise ValueError(f"Unknown kind for type '{name}'")
    finally:
        LM.close_mesh(handle)

def mesh_info(path):
    """
    Query a mesh/solution file and report its contents.

    Prints, for every registered entity type present in the file, its name,
    kind (vertex/element/solution), and number of entities (lines). For
    solution-kind entities it also prints the number of real values per line
    (sol_size) and the per-field type codes (Sca=1, Vec=2, SymMat=3, Mat=4).

    Returns
    -------
    (version, dim) : tuple of int
    """
    handle, ver, dim = LM.open_mesh_read(path)
    try:
        print(f"File          : {path}")
        print(f"Version       : {ver}")
        print(f"Dimension     : {dim}")
        print(f"{'Type':<25}{'Kind':<12}{'Count':>10}   Details")
        print("-" * 70)

        for name, spec in TYPES.items():
            kwd = KWD[spec["kwd"]]

            if spec["kind"] == "solution":
                n_lines, n_types_, sol_size, field_types = LM.stat_kwd_solution(handle, kwd)
                if n_lines > 0:
                    print(f"{name:<25}{spec['kind']:<12}{n_lines:>10}   "
                          f"sol_size={sol_size}, field_types={field_types}")
            else:
                n_lines = LM.stat_kwd(handle, kwd)
                if n_lines > 0:
                    details = f"n_cols={spec['n_cols']}" if spec["kind"] == "integer" else ""
                    print(f"{name:<25}{spec['kind']:<12}{n_lines:>10}   {details}")
    finally:
        LM.close_mesh(handle)

    return ver, dim

# ----------------------------------------------------------------------------
# Example
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    print("Registered types:", list_types())

    mesh = read("naca0012.meshb")
    print("Types present in file:", list_types("naca0012.meshb"))
    print("Vertices:", mesh["vertices"].shape, "Triangles:", mesh["triangles"].shape)

    n = mesh["vertices"].shape[0]
    demo_values = np.column_stack([
        np.linspace(1.0, 2.0, n),
        np.linspace(101325.0, 90000.0, n),
        np.linspace(0.1, 3.5, n),
    ])
    write("roundtrip.meshb", {"vertices": mesh["vertices"], "triangles": mesh["triangles"]}, version=3, dim=2)
    write("roundtrip.solb", {"sol_at_vertices": {"values": demo_values}}, version=3, dim=2)

    check = read("roundtrip.meshb", types=["vertices", "triangles"])
    print("Round-trip vertices match:", np.allclose(mesh["vertices"], check["vertices"]))

    sol = read("roundtrip.solb", types=["sol_at_vertices"])
    print("Solution round-trip matches:",
          np.allclose(demo_values, sol["sol_at_vertices"]["values"]))
