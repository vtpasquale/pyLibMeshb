# pyLibMeshb

Python module for accessing mesh and solution files in Gamma Mesh Format 
(`.mesh`/`.meshb`/`.sol`/`.solb`). Implemented by compiling the vendored
 [libMeshb](https://github.com/LoicMarechal/libMeshb) source 
 (`libmeshb8.c` / `libmeshb8.h`) directly and binding via Python ctypes.

## Installation

`pyLibMeshb` ships as prebuilt wheels for **Linux**, **macOS**, and **Windows** (x86_64), attached to each [GitHub Release](https://github.com/vtpasquale/pyLibMeshb/releases). No C compiler is required to install — the compiled library is bundled inside the wheel.

### Option 1: Install directly from a GitHub Release (recommended)

1. Go to the [Releases page](https://github.com/vtpasquale/pyLibMeshb/releases) and find the version you want.
2. Under **Assets**, right-click the wheel matching your platform and copy the link:
   - `pylibmeshb-<version>-*-linux_x86_64.whl` for Linux
   - `pylibmeshb-<version>-*-win_amd64.whl` for Windows
3. Install it directly from the URL:

   ```bash
   pip install https://github.com/vtpasquale/pyLibMeshb/releases/download/v0.1.0/pylibmeshb-0.1.0-cp312-cp312-linux_x86_64.whl
   ```

   Replace the URL with the actual asset link for your platform and Python version. 

### Option 2: Download, then install locally

If you'd rather download the file first (e.g. to inspect it, or install on an air-gapped machine):

```bash
# after downloading the .whl file to your machine
pip install ./pylibmeshb-0.1.0-cp312-cp312-linux_x86_64.whl
```

### Option 3: Install from source

If no prebuilt wheel matches your platform or Python version, you can build from source. This requires a C compiler. 

```bash
git clone https://github.com/vtpasquale/pyLibMeshb.git
cd pyLibMeshb
pip install .
```

### Requirements

- Python 3.12 or later
- `numpy` (installed automatically as a dependency)
- Supported platforms: Linux x86_64, Windows x86_64 (64-bit)

### Verifying the install

```python
import pyLibMeshb
print("pyLibMeshb installed successfully")
```

If you see an `ImportError` mentioning a missing compiled library (`_libmeshb.so` / `_libmeshb.dll`), double-check that you downloaded the wheel matching your operating system and Python version — mixing platforms (e.g. installing the Windows wheel on Linux) will fail at import time.

  
## Credits
- [LibMeshb](https://github.com/LoicMarechal/libMeshb) — Loïc Maréchal, INRIA
- LibMeshb license — [/csrc/libMeshb/LICENSE.txt](/csrc/libMeshb/LICENSE.txt)
