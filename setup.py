"""
setup.py
--------
Builds the libmeshb8 C library as a shared object (Linux) or DLL
(cross-compiled via MinGW for Windows) and packages it inside the
pyLibMeshb wheel. The compiled binary is loaded via ctypes at runtime
(see src/pyLibMeshb/libMeshb.py) -- it is not a CPython extension
module (no PyInit_ entry point), so build_ext is customized to:

  1. swap in the MinGW cross-compiler when TARGET=win-amd64 is set
  2. emit a stable, un-tagged filename (_libmeshb.so / _libmeshb.dll)
     instead of the default ABI-tagged extension filename

Usage
-----
Native Linux build:
    python -m build --wheel

Cross-compiled Windows build (requires gcc-mingw-w64-x86-64 on PATH):
    TARGET=win-amd64 python setup.py build_ext
    TARGET=win-amd64 python setup.py bdist_wheel --plat-name win_amd64
"""

import os
import shutil
from pathlib import Path

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext
from setuptools.errors import LinkError

MINGW_CC = "x86_64-w64-mingw32-gcc"
TARGET = os.environ.get("TARGET")  # None (native) or "win-amd64"

libmeshb_ext = Extension(
    "pyLibMeshb._libmeshb",
    sources=["csrc/libMeshb/libmeshb8.c"],
    include_dirs=["csrc/libMeshb"],
    extra_compile_args=["-O2"],
    libraries=[] if TARGET == "win-amd64" else ["z"],
)

HEADER_SRC = Path("csrc/libMeshb/libmeshb8.h")

class cross_build_ext(build_ext):
    
    def run(self):
        build_ext.run(self)
        self._copy_header()

    def _copy_header(self):
        for ext in self.extensions:
            dest_dir = Path(self.get_ext_fullpath(ext.name)).parent
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(HEADER_SRC, dest_dir / HEADER_SRC.name)
    
    def build_extensions(self):
        if TARGET == "win-amd64":
            if not self._mingw_available():
                raise RuntimeError(
                    f"{MINGW_CC} not found on PATH. Install it with:\n"
                    "  sudo apt install gcc-mingw-w64-x86-64"
                )
            self.compiler.set_executable("compiler_so", [MINGW_CC, "-O2"])
            self.compiler.set_executable(
                "linker_so", [MINGW_CC, "-shared", "-static"]
            )

        try:
            build_ext.build_extensions(self)
        except LinkError:
            if TARGET != "win-amd64":
                raise
            # Fall back to explicit static winpthread linkage if plain
            # -static didn't fully resolve the thread-model dependency.
            self.compiler.set_executable(
                "linker_so",
                [
                    MINGW_CC, "-shared", "-static-libgcc",
                    "-Wl,-Bstatic,--whole-archive", "-lwinpthread",
                    "-Wl,-Bdynamic,--no-whole-archive",
                ],
            )
            build_ext.build_extensions(self)

    def get_ext_filename(self, ext_name):
        ext_path = ext_name.split(".")
        suffix = ".dll" if TARGET == "win-amd64" else ".so"
        return os.path.join(*ext_path) + suffix

    @staticmethod
    def _mingw_available():
        return shutil.which(MINGW_CC) is not None


setup(
    ext_modules=[libmeshb_ext],
    cmdclass={"build_ext": cross_build_ext},
)
