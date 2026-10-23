# Build on Windows with Python 3.12: pyinstaller --noconfirm packaging/windows.spec
from pathlib import Path
import os
import sys
import importlib.metadata as metadata
from PyInstaller.utils.hooks import collect_all, copy_metadata

root = Path(SPECPATH).parent
binaries = []
datas = [(str(root / 'models/yamnet'), 'models/yamnet'),
         (str(root / 'src/now_playing/web'), 'now_playing/web'),
         (str(root / 'packaging/licenses'), 'licenses')]
hiddenimports = []
# TensorFlow uses its maintained PyInstaller hook; these packages have dynamic
# Rust/audio/data loading which must be included explicitly.
for package in ('shazamio', 'shazamio_core', 'sounddevice', '_sounddevice_data'):
    data, binary, hidden = collect_all(package)
    datas += data
    binaries += binary
    hiddenimports += hidden
for package in ('shazamio', 'tensorflow', 'numpy', 'aiohttp'):
    datas += copy_metadata(package, recursive=True)
# App-local Microsoft runtime: no separate user installation or admin prompt.
# These redistributable runtime DLLs ship on the Windows build host.
system = Path(os.environ['SystemRoot']) / 'System32'
for pattern in ('msvcp140*.dll', 'vcruntime140*.dll', 'concrt140.dll', 'vcomp140.dll'):
    binaries += [(str(path), '.') for path in system.glob(pattern)]
# Preserve runtime notices which live outside wheel metadata directories.
python_license = Path(sys.base_prefix) / 'LICENSE.txt'
if python_license.exists():
    datas.append((str(python_license), 'licenses/python'))
for package in ('tensorflow', 'sounddevice', 'shazamio', 'shazamio-core'):
    distribution = metadata.distribution(package)
    for file in distribution.files or []:
        if Path(str(file)).name.lower() in ('license', 'license.txt', 'copying', 'notice'):
            source = Path(distribution.locate_file(file))
            if source.is_file():
                datas.append((str(source), str(Path('licenses') / package / Path(str(file)).parent)))

a = Analysis([str(root / 'packaging/desktop_entry.py')], pathex=[str(root / 'src')],
             binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['IPython', 'pytest', 'matplotlib'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Now Playing',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Now Playing')
