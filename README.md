# pyLibMeshb

Python module to read/write mesh and solution files in Gamma Mesh Format 
(`.mesh`/`.meshb`/`.sol`/`.solb`). Implemented by compiling the vendored
 [libMeshb](https://github.com/LoicMarechal/libMeshb) source 
 (`libmeshb8.c` / `libmeshb8.h`) directly and binding via Python ctypes.

## Getting Started

### Install

```bash
pip install pyLibMeshb
```

### Read and write mesh data

Import `pyLibMeshb`

```Python
import pyLibMeshb.libMeshb as lm
```

Check mesh information.

```Python
lm.mesh_info("naca0012.meshb")
```

```text
 File          : naca0012.meshb
 Version       : 2
 Dimension     : 2
 Type                     Kind             Count   Details
 ----------------------------------------------------------------------
 vertices                 vertex            4796
 edges                    element            192
 triangles                element           9400
```

Read a mesh.
```Python
mesh = lm.read("naca0012.meshb")
```

Mesh data is stored in a dictionary with keys for each data type.
```Python
print(mesh.keys())
```

```text
dict_keys(['version', 'dim', 'vertices', 'edges', 'triangles'])
```

Write the mesh back out.
```Python
lm.write("roundtrip.meshb",mesh)
```

Verify consistency.
```Python
import numpy as np
check = lm.read("roundtrip.meshb", types=["vertices"])
print("Round-trip vertices match:", np.allclose(mesh["vertices"], check["vertices"]))
```

```text
Round-trip vertices match: True
```

## Testing

Install the package with its test dependencies and run the automated tests:

```bash
python -m pip install -e ".[test]"
python -m pytest
```

### Read and write solution data
Solution demo: 3 synthetic scalar fields (e.g. density, pressure, Mach).
```Python
n = mesh["vertices"].shape[0]
demo_values = np.column_stack([
    np.linspace(1.0, 2.0, n),
    np.linspace(101325.0, 90000.0, n),
    np.linspace(0.1, 3.5, n),
])
lm.write("naca0012.solb", {"sol_at_vertices": {"values": demo_values}}, version=3, dim=2)
```
Check solution file information.
```Python
lm.mesh_info("naca0012.solb")
```

```text
File          : naca0012.solb
Version       : 3
Dimension     : 2
Type                     Kind             Count   Details
----------------------------------------------------------------------
sol_at_vertices          solution          4796   sol_size=3, field_types=[1, 1, 1]
```

Solution data can be read using `lm.read()`. The mesh and solution can be visualized with Vizir4.

### Query data types
Get lists of types in this mesh file.
```Python
mesh_types = lm.list_types("naca0012.meshb")
print(mesh_types)
```

```text
['edges', 'triangles', 'vertices']
```

Get lists of types in this solution file.
```Python
solution_types =  lm.list_types("naca0012.solb")
print(solution_types)
```

```text
['sol_at_vertices']
```

Get list of all types supported by pyLibMeshb.
```Python
all_types = lm.list_types()
print(all_types)
```

`['corners', 'dsol_at_vertices', 'edges', 'hexahedra', 'isol_at_edges', 'isol_at_hexahedra', 'isol_at_prisms', 'isol_at_quadrilaterals', 'isol_at_tetrahedra', 'isol_at_triangles', 'isol_at_vertices', 'prisms', 'pyramids', 'quadrilaterals', 'ridges', 'sol_at_edges', 'sol_at_hexahedra', 'sol_at_prisms', 'sol_at_quadrilaterals', 'sol_at_tetrahedra', 'sol_at_triangles', 'sol_at_vertices', 'tetrahedra', 'triangles', 'vertices']`


## Credits
- [LibMeshb](https://github.com/LoicMarechal/libMeshb) — Loïc Maréchal, INRIA
- LibMeshb license — [/csrc/libMeshb/LICENSE.txt](/csrc/libMeshb/LICENSE.txt)
