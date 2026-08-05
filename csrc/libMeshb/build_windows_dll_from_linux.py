"""
build_windows_dll_from_linux.py
---------------------------------
Cross-compile libmeshb8.c into a Windows .dll from a Linux host using the
MinGW-w64 cross-toolchain (x86_64-w64-mingw32-gcc), so you can build the
DLL on your usual Linux/Cygwin dev box and simply copy it to a Windows
machine for ctypes to load there.

Install the cross-compiler (Debian/Ubuntu):
    sudo apt install gcc-mingw-w64-x86-64

Then just run this script on Linux:
    python build_windows_dll_from_linux.py
It produces libmeshb8.dll in the current directory (or LIBMESHB_DIR).
Copy that single file to the Windows machine alongside libmeshb8.h and
your Python scripts -- no other DLLs are needed because of -static.
"""

import os
import shutil
import subprocess
# import sys

LIBMESHB_DIR = os.getcwd() # os.environ.get("LIBMESHB_DIR", os.path.dirname(os.path.abspath(__file__)))
SOURCE_PATH = os.path.join(LIBMESHB_DIR, "libmeshb8.c")
OUTPUT_DLL = os.path.join(LIBMESHB_DIR, "libmeshb8.dll")

MINGW_TRIPLES = ("x86_64-w64-mingw32-gcc", "x86_64-w64-mingw32-gcc-posix")


def find_mingw_cross_compiler():
    for name in MINGW_TRIPLES:
        found = shutil.which(name)
        if found:
            return found
    raise RuntimeError(
        "No MinGW-w64 cross-compiler found on PATH.\n"
        "Install it with:\n"
        "    sudo apt install gcc-mingw-w64-x86-64\n"
        "(or the -posix variant if that's what your distro ships)."
    )


def cross_compile_windows_dll(static=True):
    compiler = find_mingw_cross_compiler()

    cmd = [compiler, "-O2", "-shared", "-o", OUTPUT_DLL, SOURCE_PATH, "-I", LIBMESHB_DIR]
    if static:
        cmd.insert(2, "-static")

    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        if not static:
            raise
        # Fall back to explicit static winpthread linkage if plain
        # -static didn't fully resolve the thread-model dependency.
        fallback = [
            compiler, "-O2", "-shared", "-static-libgcc",
            "-o", OUTPUT_DLL, SOURCE_PATH, "-I", LIBMESHB_DIR,
            "-Wl,-Bstatic,--whole-archive", "-lwinpthread",
            "-Wl,-Bdynamic,--no-whole-archive",
        ]
        print("Retrying with explicit static winpthread linkage:")
        print("Running:", " ".join(fallback))
        subprocess.run(fallback, check=True)

    return OUTPUT_DLL


def verify_no_dynamic_mingw_deps(dll_path):
    """
    Best-effort check (requires 'objdump', which ships with the mingw-w64
    toolchain) that the DLL doesn't still reference libgcc_s_seh-1.dll or
    libwinpthread-1.dll -- if it does, those two files must be copied
    alongside the DLL on the Windows machine.
    """
    objdump = shutil.which("x86_64-w64-mingw32-objdump") or shutil.which("objdump")
    if not objdump:
        print("objdump not found -- skipping dependency check.")
        return

    result = subprocess.run([objdump, "-p", dll_path], capture_output=True, text=True)
    deps = [line.split()[-1] for line in result.stdout.splitlines() if "DLL Name:" in line]
    risky = [d for d in deps if "libgcc" in d.lower() or "winpthread" in d.lower()]
    if risky:
        print(f"Warning: DLL still depends on {risky} -- copy these DLLs alongside it on Windows,")
        print("or find them under /usr/lib/gcc/x86_64-w64-mingw32/*/ on this machine.")
    else:
        print("No lingering libgcc/winpthread dependency detected -- DLL should be self-contained.")


if __name__ == "__main__":
    dll_path = cross_compile_windows_dll()
    print(f"Built: {dll_path}")
    verify_no_dynamic_mingw_deps(dll_path)
    print("\nCopy this .dll (and libmeshb8.h, if your Python script parses it) to the Windows machine.")
