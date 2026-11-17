# PyInstaller spec: builds dist/VisualCommand/VisualCommand.exe (one-folder, no console).
# Run through scripts/build.ps1.
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

ROOT = Path(SPECPATH)
sys.path.insert(0, str(ROOT))
from visualcommand import __version__  # noqa: E402

nums = tuple(int(x) for x in __version__.split(".")) + (0,) * (4 - len(__version__.split(".")))
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=nums, prodvers=nums),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("CompanyName", "VisualCommand"),
            StringStruct("FileDescription", "VisualCommand - hand gesture shortcuts"),
            StringStruct("FileVersion", __version__),
            StringStruct("InternalName", "VisualCommand"),
            StringStruct("OriginalFilename", "VisualCommand.exe"),
            StringStruct("ProductName", "VisualCommand"),
            StringStruct("ProductVersion", __version__),
        ])]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

datas = [
    (str(ROOT / "models" / "gesture_recognizer.task"), "models"),
    (str(ROOT / "assets" / "icon.ico"), "assets"),
    (str(ROOT / "assets" / "sounds"), "assets/sounds"),
]
datas += collect_data_files("mediapipe", excludes=["**/*.pyc", "**/testdata/**"])
binaries = collect_dynamic_libs("mediapipe")
hiddenimports = (
    collect_submodules("visualcommand")
    + collect_submodules("mediapipe.tasks.python")
    + ["pystray._win32", "comtypes.stream", "PIL._tkinter_finder"]
)

a = Analysis(
    [str(ROOT / "visualcommand" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "IPython", "notebook", "PyQt5", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="VisualCommand",
    console=False,
    icon=str(ROOT / "assets" / "icon.ico"),
    version=version_info,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="VisualCommand", upx=False)
