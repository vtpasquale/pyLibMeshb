# pyLibMeshb

Python bindings for [LibMeshb](https://github.com/LoicMarechal/libMeshb) (the
Gamma Mesh Format / `.mesh`/`.meshb`/`.sol`/`.solb` library) via `ctypes`,
built directly against the `libmeshb8.c` / `libmeshb8.h` source files. 
The C library is compiled once into a shared library (`.so` / `.dll`) and driven
from Python through `ctypes`.

- The shared library (`libmeshb8_shared.so`) will be compiled automatically on Linux if a C compiler is available.  
- The shared library (`libmeshb8.dll`) must be provided on Windows — placed at `pyLibMeshb/csrc/libMeshb/libmeshb8.dll`.
   - The user can cross-compile the Windows binary on Linux using [build_windows_dll_from_linux.py](pyLibMeshb/csrc/libMeshb/build_windows_dll_from_linux.py)
   - Alternatively, prebuilt Windows and Linux binaries are available at the [release page](https://github.com/vtpasquale/pyLibMeshb/releases/tag/v0.0-lib)
- The software should be extendable to macOS (`.dylib`), but this has not been tested.

An included example file shows:
- Reading and writing 2D meshes: `Vertices`, `Triangles`, `Edges`
- Reading and writing solution files (`.sol` / `.solb`) with an arbitrary,
  user-defined number of independent scalar fields per vertex
  
## Credits
- [LibMeshb](https://github.com/LoicMarechal/libMeshb) — Loïc Maréchal, INRIA
- LibMeshb license — [/csrc/libMeshb/LICENSE.txt](/csrc/libMeshb/LICENSE.txt)
