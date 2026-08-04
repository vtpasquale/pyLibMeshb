#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 07:05:33 2026

@author: vtpasquale
"""

import numpy as np
from pylibmeshb.libMeshb import read_mesh_2d, read_solution, write_mesh_2d, write_solution

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

sol2 = read_solution("roundtrip.solb")
print(f"roundtrip.solb scalars: {sol2['n_scalars']}, lines: {sol2['values'].shape[0]}")