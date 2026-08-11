"""
setup.py
--------
Builds the libmeshb8 C library as a shared object (Linux) or DLL
and packages it inside the
pyLibMeshb wheel. The compiled binary is loaded via ctypes at runtime
(see src/pyLibMeshb/libMeshb.py) -- it is not a CPython extension
module (no PyInit_ entry point), so build_ext is customized to:

    1. emit a stable, un-tagged filename (_libmeshb.so / _libmeshb.dll)
     instead of the default ABI-tagged extension filename

Usage
-----
Native Linux build:
    python -m build --wheel

Native Windows build:
    python -m build --wheel
"""

import os
import shutil
from pathlib import Path

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext

NATIVE_WINDOWS = os.name == "nt"

libmeshb_ext = Extension(
    "pyLibMeshb._libmeshb",
    sources=["csrc/libMeshb/libmeshb8.c"],
    include_dirs=["csrc/libMeshb"],
    extra_compile_args=["-O2"],
    libraries=[] if NATIVE_WINDOWS else ["z"],
)

HEADER_SRC = Path("csrc/libMeshb/libmeshb8.h")
EXPORTED_SYMBOLS = [
    "GmfOpenMesh",
    "GmfCloseMesh",
    "GmfStatKwd",
    "GmfSetKwd",
    "GmfGotoKwd",
    "GmfGetBlock",
    "GmfSetBlock",
    "GmfGetFloatPrecision",
]

class cross_build_ext(build_ext):

    def run(self):
        build_ext.run(self)
        self._copy_header()

    def _copy_header(self):
        for ext in self.extensions:
            dest_dir = Path(self.get_ext_fullpath(ext.name)).parent
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(HEADER_SRC, dest_dir / HEADER_SRC.name)

    def build_extension(self, ext):
        objects = self.compiler.compile(
            ext.sources,
            output_dir=self.build_temp,
            macros=ext.define_macros,
            include_dirs=ext.include_dirs,
            debug=self.debug,
            extra_postargs=ext.extra_compile_args,
        )
        output_path = Path(self.get_ext_fullpath(ext.name))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.compiler.link_shared_object(
            objects,
            str(output_path),
            libraries=ext.libraries,
            library_dirs=ext.library_dirs,
            runtime_library_dirs=ext.runtime_library_dirs,
            extra_postargs=ext.extra_link_args,
            export_symbols=EXPORTED_SYMBOLS,
            debug=self.debug,
        )

    def get_ext_filename(self, ext_name):
        ext_path = ext_name.split(".")
        suffix = ".dll" if NATIVE_WINDOWS else ".so"
        return os.path.join(*ext_path) + suffix


setup(
    ext_modules=[libmeshb_ext],
    cmdclass={"build_ext": cross_build_ext},
)
