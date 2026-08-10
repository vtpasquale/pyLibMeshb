#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 07:05:33 2026

@author: vtpasquale
"""

import pyLibMeshb.libMeshb as lm


# Check mesh information
lm.mesh_info("naca0012.meshb")

# Read a mesh
mesh = lm.read("naca0012.meshb")

# Mesh data is stored in a dictionary with keys for each data type
print(mesh.keys())

# Write the mesh back out
lm.write("roundtrip.meshb",mesh)

# Verify consistency
import numpy as np
check = lm.read("roundtrip.meshb", types=["vertices"])
print("Round-trip vertices match:", np.allclose(mesh["vertices"], check["vertices"]))

# Solution demo: 3 synthetic scalar fields (e.g. density, pressure, Mach).
n = mesh["vertices"].shape[0]
demo_values = np.column_stack([
    np.linspace(1.0, 2.0, n),
    np.linspace(101325.0, 90000.0, n),
    np.linspace(0.1, 3.5, n),
])
lm.write("naca0012.solb", {"sol_at_vertices": {"values": demo_values}}, version=3, dim=2)

# Check solution file information
lm.mesh_info("naca0012.solb")

# The mesh and solution can be visualized with Vizir4

# Get lists of types in this mesh file
mesh_types = lm.list_types("naca0012.meshb")
print(mesh_types)

# Get lists of types in this solution file
solution_types =  lm.list_types("naca0012.solb")
print(solution_types)

# Get list of all types supported by pyLibMeshb
all_types = lm.list_types()
print(all_types)