#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 07:05:33 2026

@author: vtpasquale
"""

import numpy as np
from pyLibMeshb.libMeshb import list_types, read, write, mesh_info

types_all = list_types()

types_file = list_types("naca0012.meshb")

mesh_info("naca0012.meshb")

mesh = read("naca0012.meshb")

# mesh = read("naca0012.meshb", types=["vertices", "triangles", "edges"])


# Round-trip demo: write it back out and read it again.
write("roundtrip.meshb",
      {"vertices": mesh["vertices"], "triangles": mesh["triangles"], "edges": mesh["edges"]},
      version=3, dim=2)
check = read("roundtrip.meshb", types=["vertices"])
print("Round-trip vertices match:", np.allclose(mesh["vertices"], check["vertices"]))


# write("roundtrip.mesh",
#       {"vertices": mesh["vertices"], "triangles": mesh["triangles"], "edges": mesh["edges"]},
#       version=3, dim=2)


# Solution demo: 3 synthetic scalar fields (e.g. density, pressure, Mach).
n = mesh["vertices"].shape[0]
demo_values = np.column_stack([
    np.linspace(1.0, 2.0, n),
    np.linspace(101325.0, 90000.0, n),
    np.linspace(0.1, 3.5, n),
])
write("roundtrip.solb", {"sol_at_vertices": {"values": demo_values}}, version=3, dim=2)
sol = read("roundtrip.solb", types=["sol_at_vertices"])
print(f"Solution scalars: {sol['sol_at_vertices']['values'].shape[1]}, "
      f"lines: {sol['sol_at_vertices']['values'].shape[0]}")
print("Solution round-trip matches:", np.allclose(demo_values, sol["sol_at_vertices"]["values"]))

sol2 = read("roundtrip.solb", types=["sol_at_vertices"])
print(f"roundtrip.solb scalars: {sol2['sol_at_vertices']['values'].shape[1]}, "
      f"lines: {sol2['sol_at_vertices']['values'].shape[0]}")

# What entities does this file actually contain?
print("Types present in roundtrip.meshb:", list_types("roundtrip.meshb"))