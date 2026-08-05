"""
libMeshb.py
-----------
Read/write 2D .mesh/.meshb mesh files (Vertices, Triangles, Edges) and
.sol/.solb solution files (arbitrary number of scalar fields) using the
LibMeshb C library (libmeshb8.c / libmeshb8.h) via ctypes, driven entirely
through GmfGetBlock / GmfSetBlock (bulk block I/O, not per-line).

Mesh I/O
--------
read_mesh_2d(path)                             -> dict of numpy arrays
write_mesh_2d(path, vertices, triangles, edges, version=3)

Solution I/O
------------
read_solution(path, keyword='GmfSolAtVertices') -> dict with an (N, n_scalars) array
write_solution(path, values, version=3, dim=2, keyword='GmfSolAtVertices')

Notes on GmfSetBlock/GmfGetBlock argument forms (from libmeshb8.c / libMeshb docs):
    Scalar field group : <type tag>, &first_elem, &last_elem
    Vector field group : <type tag + 4 (Vec)>, <count>, &first_row, &last_row
        (the "Vec" form treats a contiguous 2D row-major buffer as
        `count` interleaved scalar columns -- perfect for a user-defined
        number of solution scalars stored as one (N, n_scalars) array.)

Solution keyword header must be declared with GmfSetKwd(idx, Kwd, N,
NumberOfTypes, TypeTable) where TypeTable is an int* to NumberOfTypes
entries, each GmfSca(1)/GmfVec(2)/GmfSymMat(3)/GmfMat(4). For n_scalars
independent scalar fields, TypeTable = [GmfSca] * n_scalars, which makes
SolSize == n_scalars.

Integer width and float precision depend on the file version:
    version 1        : 32-bit ints, 32-bit floats
    version 2 or 3    : 32-bit ints, 64-bit floats
    version 4         : 64-bit ints, 64-bit floats

Requirements:
    - numpy
    - Linux: (1) a C compiler on PATH (gcc/cc/clang) 
             (2) OR libmeshb8_shared.so in csrc/libMeshb
    - Windows: libmeshb8.dll in csrc/libMeshb
    - See https://github.com/vtpasquale/pyLibMeshb/releases/tag/v0.0-lib
       for precomplied shared libraries
"""

import ctypes
import os
import re
import subprocess
import sys
from ctypes import c_int, c_int64, c_void_p, byref

import numpy as np

# Library paths and files 
this_dir = os.path.dirname(os.path.abspath(__file__))
LIBMESHB_DIR = os.path.normpath(os.path.join(this_dir,"..","..","csrc","libMeshb'"))

HEADER_PATH = os.path.join(LIBMESHB_DIR, "libmeshb8.h")
SOURCE_PATH = os.path.join(LIBMESHB_DIR, "libmeshb8.c")

if sys.platform.startswith("win"):
    LIBRARY_PATH = os.path.join(LIBMESHB_DIR, "libmeshb8.dll")
else:
    LIBRARY_PATH = os.path.join(LIBMESHB_DIR, "libmeshb8_shared.so")

    
# #define macros in libmeshb8.h -- stable, explicit constants.
GmfRead = 1
GmfWrite = 2
GmfSca = 1
GmfVec = 2
GmfSymMat = 3
GmfMat = 4
GmfFloat = 8
GmfDouble = 9
GmfInt = 10
GmfLong = 11
GmfFloatVec = 12
GmfDoubleVec = 13
GmfIntVec = 14
GmfLongVec = 15


# ----------------------------------------------------------------------------
# 1. Parse the GmfKwdCod enum straight out of the header so keyword indices
#    can never drift out of sync with whatever version of the header you have.
# ----------------------------------------------------------------------------
def parse_keyword_enum(header_path):
    with open(header_path, "r") as f:
        text = f.read()

    m = re.search(r"enum\s+GmfKwdCod\s*\{(.*?)\};", text, re.S)
    if not m:
        raise RuntimeError("Could not locate 'enum GmfKwdCod' in header")

    body = m.group(1)
    names = [tok.strip() for tok in body.split(",")]
    names = [n for n in names if n]
    return {name: idx for idx, name in enumerate(names)}


# ----------------------------------------------------------------------------
# 2. Compile libmeshb8.c into a shared library if it hasn't been built yet.
# ----------------------------------------------------------------------------
def build_shared_library(force=False):
    if os.path.exists(LIBRARY_PATH) and not force:
        return LIBRARY_PATH

    compiler = os.environ.get("CC", "gcc")
    cmd = [
        compiler, "-O2", "-fPIC", "-shared",
        "-o", LIBRARY_PATH,
        SOURCE_PATH,
        "-I", LIBMESHB_DIR,
        "-lz",
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        cmd = [c for c in cmd if c != "-lz"]
        subprocess.run(cmd, check=True)
    return LIBRARY_PATH


# ----------------------------------------------------------------------------
# 3. ctypes bindings
# ----------------------------------------------------------------------------
class LibMeshb:
    def __init__(self, lib_path):
        self.lib = ctypes.CDLL(lib_path)
        self.lib.GmfOpenMesh.restype = c_int64
        self.lib.GmfStatKwd.restype = c_int64
        self.lib.GmfCloseMesh.restype = c_int
        self.lib.GmfGotoKwd.restype = c_int
        self.lib.GmfGetBlock.restype = c_int
        self.lib.GmfSetBlock.restype = c_int
        self.lib.GmfSetKwd.restype = c_int
        self.lib.GmfGetFloatPrecision.restype = c_int

    # -- open / close --------------------------------------------------
    def open_mesh_read(self, path):
        ver = c_int(0)
        dim = c_int(0)
        handle = self.lib.GmfOpenMesh(
            path.encode("utf-8"), c_int(GmfRead), byref(ver), byref(dim)
        )
        if handle == 0:
            raise IOError(f"GmfOpenMesh failed to open '{path}'")
        return handle, ver.value, dim.value

    def open_mesh_write(self, path, version, dim):
        handle = self.lib.GmfOpenMesh(
            path.encode("utf-8"), c_int(GmfWrite), c_int(version), c_int(dim)
        )
        if handle == 0:
            raise IOError(f"GmfOpenMesh failed to create '{path}'")
        return handle

    def close_mesh(self, handle):
        self.lib.GmfCloseMesh(c_int64(handle))

    # -- keyword header --------------------------------------------------
    def stat_kwd(self, handle, kwd):
        return self.lib.GmfStatKwd(c_int64(handle), c_int(kwd))

    def stat_kwd_solution(self, handle, kwd, max_types=1000):
        n_types = c_int(0)
        sol_size = c_int(0)
        type_tab = (c_int * max_types)()
        n_lines = self.lib.GmfStatKwd(
            c_int64(handle), c_int(kwd), byref(n_types), byref(sol_size), type_tab
        )
        types = list(type_tab[: n_types.value])
        return n_lines, n_types.value, sol_size.value, types

    def set_kwd(self, handle, kwd, n_lines):
        ok = self.lib.GmfSetKwd(c_int64(handle), c_int(kwd), c_int64(n_lines))
        if not ok and n_lines > 0:
            raise RuntimeError(f"GmfSetKwd failed for keyword id {kwd}")

    def set_kwd_solution(self, handle, kwd, n_lines, type_tab):
        type_arr = (c_int * len(type_tab))(*type_tab)
        ok = self.lib.GmfSetKwd(
            c_int64(handle), c_int(kwd), c_int64(n_lines),
            c_int(len(type_tab)), type_arr,
        )
        if not ok and n_lines > 0:
            raise RuntimeError(f"GmfSetKwd (solution) failed for keyword id {kwd}")

    def goto_kwd(self, handle, kwd):
        ok = self.lib.GmfGotoKwd(c_int64(handle), c_int(kwd))
        if ok == 0:
            raise RuntimeError(f"GmfGotoKwd failed for keyword id {kwd}")

    def float_precision(self, handle):
        return self.lib.GmfGetFloatPrecision(c_int64(handle))

    # -- bulk block I/O --------------------------------------------------
    @staticmethod
    def _build_block_argv(handle, kwd, n_lines, fields, begin=1):
        argv = [
            c_int64(handle), c_int(kwd),
            c_int64(begin), c_int64(begin + n_lines - 1),
            c_int(0), c_void_p(None), c_void_p(None),
        ]
        for field in fields:
            if field[0] == "scalar":
                _, type_code, arr = field
                first_addr = arr.ctypes.data
                last_addr = first_addr + (n_lines - 1) * arr.itemsize if n_lines > 1 else first_addr
                argv += [c_int(type_code), c_void_p(first_addr), c_void_p(last_addr)]
            elif field[0] == "vec":
                _, type_code_vec, count, arr2d = field
                row_stride = arr2d.strides[0]
                first_addr = arr2d.ctypes.data
                last_addr = first_addr + (n_lines - 1) * row_stride if n_lines > 1 else first_addr
                argv += [c_int(type_code_vec), c_int(count), c_void_p(first_addr), c_void_p(last_addr)]
            else:
                raise ValueError(f"Unknown field kind: {field[0]}")
        return argv

    def get_block(self, handle, kwd, n_lines, fields):
        argv = self._build_block_argv(handle, kwd, n_lines, fields)
        ok = self.lib.GmfGetBlock(*argv)
        if not ok:
            raise RuntimeError(f"GmfGetBlock failed for keyword id {kwd}")

    def set_block(self, handle, kwd, n_lines, fields):
        argv = self._build_block_argv(handle, kwd, n_lines, fields)
        ok = self.lib.GmfSetBlock(*argv)
        if not ok:
            raise RuntimeError(f"GmfSetBlock failed for keyword id {kwd}")


def scalar_field(type_code, arr):
    return ("scalar", type_code, arr)


def vec_field(type_code_vec, count, arr2d):
    return ("vec", type_code_vec, count, arr2d)


# ----------------------------------------------------------------------------
# 4. Mesh reader (Vertices, Triangles, Edges) -- GmfGetBlock
# ----------------------------------------------------------------------------
def read_mesh_2d(path):
    """
    Returns:
        {
          'version': int, 'dim': int,
          'vertices': (N,3) float64 array   -- x, y, ref
          'triangles': (M,4) int64 array    -- v0, v1, v2, ref (1-based)
          'edges': (K,3) int64 array        -- v0, v1, ref (1-based, boundary)
        }
    """
    handle, ver, dim = LM.open_mesh_read(path)
    if dim != 2:
        print(f"Warning: file reports dimension={dim}, expected 2", file=sys.stderr)

    float_bits = LM.float_precision(handle)
    float_dtype = np.float32 if float_bits == 32 else np.float64
    float_code = GmfFloat if float_bits == 32 else GmfDouble

    int_dtype = np.int32 if ver < 4 else np.int64
    int_code = GmfInt if ver < 4 else GmfLong

    try:
        n_vert = LM.stat_kwd(handle, KWD["GmfVertices"])
        n_tri = LM.stat_kwd(handle, KWD["GmfTriangles"])
        n_edg = LM.stat_kwd(handle, KWD["GmfEdges"])

        vertices = np.empty((n_vert, 3), dtype=np.float64)
        if n_vert > 0:
            x = np.empty(n_vert, dtype=float_dtype)
            y = np.empty(n_vert, dtype=float_dtype)
            ref = np.empty(n_vert, dtype=int_dtype)
            LM.goto_kwd(handle, KWD["GmfVertices"])
            LM.get_block(
                handle, KWD["GmfVertices"], n_vert,
                [scalar_field(float_code, x), scalar_field(float_code, y), scalar_field(int_code, ref)],
            )
            vertices[:, 0] = x
            vertices[:, 1] = y
            vertices[:, 2] = ref

        triangles = np.empty((n_tri, 4), dtype=np.int64)
        if n_tri > 0:
            v0, v1, v2, ref = (np.empty(n_tri, dtype=int_dtype) for _ in range(4))
            LM.goto_kwd(handle, KWD["GmfTriangles"])
            LM.get_block(
                handle, KWD["GmfTriangles"], n_tri,
                [scalar_field(int_code, v0), scalar_field(int_code, v1),
                 scalar_field(int_code, v2), scalar_field(int_code, ref)],
            )
            triangles[:, 0] = v0
            triangles[:, 1] = v1
            triangles[:, 2] = v2
            triangles[:, 3] = ref

        edges = np.empty((n_edg, 3), dtype=np.int64)
        if n_edg > 0:
            v0, v1, ref = (np.empty(n_edg, dtype=int_dtype) for _ in range(3))
            LM.goto_kwd(handle, KWD["GmfEdges"])
            LM.get_block(
                handle, KWD["GmfEdges"], n_edg,
                [scalar_field(int_code, v0), scalar_field(int_code, v1), scalar_field(int_code, ref)],
            )
            edges[:, 0] = v0
            edges[:, 1] = v1
            edges[:, 2] = ref

    finally:
        LM.close_mesh(handle)

    return {"version": ver, "dim": dim, "vertices": vertices, "triangles": triangles, "edges": edges}


# ----------------------------------------------------------------------------
# 5. Mesh writer (Vertices, Triangles, Edges) -- GmfSetBlock
# ----------------------------------------------------------------------------
def write_mesh_2d(path, vertices, triangles, edges, version=3):
    """
    vertices  : array-like (Nv,3)  columns x, y, ref
    triangles : array-like (Nt,4)  columns v0, v1, v2, ref (1-based)
    edges     : array-like (Ne,3)  columns v0, v1, ref (1-based, boundary)
    version   : meshb file format version (1-4). 3 is a solid default:
                64-bit-safe file size, 64-bit reals, 32-bit indices.
    """
    vertices = np.asarray(vertices, dtype=np.float64)
    triangles = np.asarray(triangles, dtype=np.int64)
    edges = np.asarray(edges, dtype=np.int64)

    dim = 2
    handle = LM.open_mesh_write(path, version, dim)

    float_dtype = np.float32 if version == 1 else np.float64
    float_code = GmfFloat if version == 1 else GmfDouble
    int_dtype = np.int32 if version < 4 else np.int64
    int_code = GmfInt if version < 4 else GmfLong

    try:
        n_vert = vertices.shape[0]
        if n_vert > 0:
            x = np.ascontiguousarray(vertices[:, 0], dtype=float_dtype)
            y = np.ascontiguousarray(vertices[:, 1], dtype=float_dtype)
            ref = np.ascontiguousarray(vertices[:, 2], dtype=int_dtype)
            LM.set_kwd(handle, KWD["GmfVertices"], n_vert)
            LM.set_block(
                handle, KWD["GmfVertices"], n_vert,
                [scalar_field(float_code, x), scalar_field(float_code, y), scalar_field(int_code, ref)],
            )

        n_tri = triangles.shape[0]
        if n_tri > 0:
            cols = [np.ascontiguousarray(triangles[:, i], dtype=int_dtype) for i in range(4)]
            LM.set_kwd(handle, KWD["GmfTriangles"], n_tri)
            LM.set_block(
                handle, KWD["GmfTriangles"], n_tri,
                [scalar_field(int_code, c) for c in cols],
            )

        n_edg = edges.shape[0]
        if n_edg > 0:
            cols = [np.ascontiguousarray(edges[:, i], dtype=int_dtype) for i in range(3)]
            LM.set_kwd(handle, KWD["GmfEdges"], n_edg)
            LM.set_block(
                handle, KWD["GmfEdges"], n_edg,
                [scalar_field(int_code, c) for c in cols],
            )
    finally:
        LM.close_mesh(handle)


# ----------------------------------------------------------------------------
# 6. Solution reader/writer (.sol / .solb) -- arbitrary number of scalars
# ----------------------------------------------------------------------------
def read_solution(path, keyword="GmfSolAtVertices"):
    """
    Reads a solution file with an arbitrary number of independent scalar
    fields (each declared as GmfSca in the file's type table).

    Returns:
        {
          'version': int, 'dim': int,
          'n_scalars': int,
          'values': (N, n_scalars) float64 array
        }
    """
    handle, ver, dim = LM.open_mesh_read(path)
    kwd = KWD[keyword]

    float_bits = LM.float_precision(handle)
    float_dtype = np.float32 if float_bits == 32 else np.float64
    float_code_vec = GmfFloatVec if float_bits == 32 else GmfDoubleVec

    try:
        n_lines, n_types, sol_size, types = LM.stat_kwd_solution(handle, kwd)
        if n_lines == 0:
            return {"version": ver, "dim": dim, "n_scalars": 0, "values": np.empty((0, 0))}

        if any(t != GmfSca for t in types):
            raise ValueError(
                f"'{keyword}' contains non-scalar fields (types={types}); "
                "this reader expects only GmfSca entries."
            )
        n_scalars = sol_size  # each GmfSca contributes exactly one real

        buf = np.empty((n_lines, n_scalars), dtype=float_dtype)
        LM.goto_kwd(handle, kwd)
        LM.get_block(handle, kwd, n_lines, [vec_field(float_code_vec, n_scalars, buf)])

        values = buf.astype(np.float64, copy=False)
    finally:
        LM.close_mesh(handle)

    return {"version": ver, "dim": dim, "n_scalars": n_scalars, "values": values}


def write_solution(path, values, version=3, dim=2, keyword="GmfSolAtVertices"):
    """
    Writes a solution file with an arbitrary number of independent scalar
    fields, one GmfSca entry per column.

    values  : array-like (N, n_scalars)
    version : file format version (1-4); governs real/int precision.
    dim     : spatial dimension the solution refers to (2 or 3); mandatory
              header field for .sol/.solb files, same as for .mesh/.meshb.
    keyword : solution keyword, e.g. 'GmfSolAtVertices', 'GmfSolAtTriangles'.
    """
    values = np.atleast_2d(np.asarray(values, dtype=np.float64))
    n_lines, n_scalars = values.shape

    kwd = KWD[keyword]
    handle = LM.open_mesh_write(path, version, dim)

    float_dtype = np.float32 if version == 1 else np.float64
    float_code_vec = GmfFloatVec if version == 1 else GmfDoubleVec

    try:
        if n_lines > 0:
            type_tab = [GmfSca] * n_scalars
            LM.set_kwd_solution(handle, kwd, n_lines, type_tab)

            buf = np.ascontiguousarray(values, dtype=float_dtype)
            LM.set_block(handle, kwd, n_lines, [vec_field(float_code_vec, n_scalars, buf)])
    finally:
        LM.close_mesh(handle)


# ----------------------------------------------------------------------------
# Module-level setup: parse header, build/load library
# ----------------------------------------------------------------------------
KWD = parse_keyword_enum(HEADER_PATH)
_lib_path = build_shared_library()
LM = LibMeshb(_lib_path)


# ----------------------------------------------------------------------------
# Example / CLI entry point
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    # if len(sys.argv) < 2:
    #     print("Usage: python meshb_io.py <mesh_file.mesh[b]> [solution_file.sol[b]]")
    #     sys.exit(1)

    # mesh = read_mesh_2d(sys.argv[1])
    
    mesh = read_mesh_2d("naca0012.meshb")
    
    print(f"File version : {mesh['version']}")
    print(f"Dimension    : {mesh['dim']}")
    print(f"Vertices     : {mesh['vertices'].shape[0]}")
    print(f"Triangles    : {mesh['triangles'].shape[0]}")
    print(f"Boundary edges: {mesh['edges'].shape[0]}")

    # Round-trip demo: write it back out and read it again.
    write_mesh_2d("roundtrip.meshb", mesh["vertices"], mesh["triangles"], mesh["edges"], version=3)
    check = read_mesh_2d("roundtrip.meshb")
    print("Round-trip vertices match:", np.allclose(mesh["vertices"], check["vertices"]))

    # Solution demo: 3 synthetic scalar fields (e.g. density, pressure, Mach).
    n = mesh["vertices"].shape[0]
    demo_values = np.column_stack([
        np.linspace(1.0, 2.0, n),
        np.linspace(101325.0, 90000.0, n),
        np.linspace(0.1, 3.5, n),
    ])
    write_solution("roundtrip.solb", demo_values, version=3, dim=2)
    sol = read_solution("roundtrip.solb")
    print(f"Solution scalars: {sol['n_scalars']}, lines: {sol['values'].shape[0]}")
    print("Solution round-trip matches:", np.allclose(demo_values, sol["values"]))

    if len(sys.argv) == 3:
        sol2 = read_solution(sys.argv[2])
        print(f"'{sys.argv[2]}' scalars: {sol2['n_scalars']}, lines: {sol2['values'].shape[0]}")
