import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent
APP_NAME = "Everything Agent Core"

GI_STDLIB_DEPENDENCIES = ["optparse", "pkgutil", "inspect", "selectors", "typing_extensions"]
GSTREAMER_WHEELS = (
    "gstreamer_libs", "gstreamer_bundle", "gstreamer_python", "gstreamer_plugins", "gstreamer_plugins_libs",
    "gstreamer_ext_runtime", "gstreamer_cli", "gstreamer_gtk",
)
GPL_AND_RESTRICTED_WHEELS = ["gstreamer_plugins_restricted", "gstreamer_plugins_gpl", "gstreamer_plugins_gpl_restricted"]
PATENT_ENCUMBERED_CODECS = (
    "gstlibav", "gstopenh264", "openh264", "avcodec", "avformat", "avfilter", "avutil", "avdevice",
    "swresample", "swscale", "postproc",
)


def shippable(entry):
    name = Path(entry[0]).name.lower()
    return not any(name.startswith((codec, "lib" + codec)) for codec in PATENT_ENCUMBERED_CODECS)


datas = collect_data_files("everything_agent", excludes=["web/robot/**"])
binaries = []
hiddenimports = collect_submodules("everything_agent") + collect_submodules("reachy_mini.daemon") + GI_STDLIB_DEPENDENCIES

for package in ("reachy_mini", "tzdata", "anthropic", "claude_agent_sdk"):
    if importlib.util.find_spec(package):
        d, b, h = collect_all(package)
        datas += d
        binaries += b
        hiddenimports += h

for package in GSTREAMER_WHEELS:
    spec = importlib.util.find_spec(package)
    if spec is None:
        continue
    datas += collect_data_files(package, include_py_files=True)
    hiddenimports.append(package)
    root = Path(spec.submodule_search_locations[0])
    for f in root.rglob("*"):
        if f.suffix in (".pyd", ".so"):
            datas.append((str(f), str(Path(package) / f.parent.relative_to(root))))

datas = [entry for entry in datas if shippable(entry)]

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["gi", "cairo", "pygtkcompat", "tkinter", "pytest", "_pytest", "IPython", *GPL_AND_RESTRICTED_WHEELS],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=APP_NAME, console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME, upx=False)
