"""Usage: python packaging/third_party_licenses.py <output file>; lists what the desktop app ships, with licenses."""

import hashlib
import json
import re
import subprocess
import sys
from importlib.metadata import distributions
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LICENSE_FILE = re.compile(r"^(licen[cs]e|copying|notice|copyright|authors)", re.I)
NOT_SHIPPED = {
    "everything-agent", "pip", "setuptools", "wheel", "pyinstaller", "pyinstaller-hooks-contrib", "altgraph",
    "pefile", "pywin32-ctypes", "macholib", "pytest", "pytest-asyncio", "pluggy", "iniconfig",
    "gstreamer-plugins-gpl", "gstreamer-plugins-gpl-restricted", "gstreamer-plugins-restricted",
}
GSTREAMER = """GStreamer and its plugins are licensed under the GNU Lesser General Public License 2.1
(full text below). The app loads them as separate libraries, which you may replace with your
own builds. Source code: https://gstreamer.freedesktop.org/src/ (the version is in the
gstreamer-* entries above). GPL-licensed and patent-restricted plugins are not included."""


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def license_texts(folder: Path, names=None) -> list[str]:
    files = names if names is not None else sorted(p for p in folder.iterdir() if p.is_file() and LICENSE_FILE.match(p.name))
    texts = []
    for path in files:
        try:
            texts.append(path.read_text(encoding="utf-8", errors="replace").strip())
        except OSError:
            pass
    return [t for t in texts if t]


def python_components():
    seen = set()
    for dist in distributions():
        name = dist.metadata["Name"]
        if not name or normalize(name) in NOT_SHIPPED or normalize(name) in seen:
            continue
        seen.add(normalize(name))
        meta = dist.metadata
        license_name = (meta.get("License-Expression") or "").strip()
        if not license_name:
            classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
            license_name = "; ".join(classifiers) or (meta.get("License") or "").strip().split("\n")[0][:80]
        files = [Path(dist.locate_file(f)) for f in dist.files or [] if LICENSE_FILE.match(Path(str(f)).name)]
        yield "Python", name, dist.version, license_name or "see text", license_texts(None, [f for f in files if f.is_file()])
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.exists():
        python_license = Path(sys.base_prefix) / "lib" / f"python{sys.version_info[0]}.{sys.version_info[1]}" / "LICENSE.txt"
    yield "Python", "CPython", sys.version.split()[0], "PSF-2.0", license_texts(None, [python_license] if python_license.exists() else [])


def npm_components(folder: Path):
    lock = json.loads((folder / "package-lock.json").read_text(encoding="utf-8"))
    for path, info in lock.get("packages", {}).items():
        if not path or info.get("dev") or info.get("devOptional"):
            continue
        package = folder / path
        if not package.is_dir():
            continue
        name = path.split("node_modules/")[-1]
        yield "JavaScript", name, info.get("version", ""), info.get("license", "see text"), license_texts(package)


def rust_components(manifest: Path):
    host = re.search(r"host: (\S+)", subprocess.check_output(["rustc", "-vV"], text=True, encoding="utf-8")).group(1)
    meta = json.loads(subprocess.check_output(
        ["cargo", "metadata", "--format-version", "1", "--locked", "--filter-platform", host, "--manifest-path", str(manifest)],
        text=True, encoding="utf-8",
    ))
    members = set(meta["workspace_members"])
    used = {node["id"] for node in meta["resolve"]["nodes"]}
    for package in meta["packages"]:
        if package["id"] in members or package["id"] not in used:
            continue
        folder = Path(package["manifest_path"]).parent
        yield "Rust", package["name"], package["version"], package.get("license") or "see text", license_texts(folder)


def render(components) -> str:
    texts: dict[str, str] = {}
    lines = [
        "Third-party software in Everything Agent",
        "",
        "Everything Agent is licensed under the Apache License 2.0. The desktop app also contains the",
        "components below, each under its own license. Each entry names its license and the",
        "[n] numbers of the license texts at the end of this file.",
        "",
    ]
    for kind in ("Python", "JavaScript", "Rust"):
        lines += [f"== {kind} ==", ""]
        for _, name, version, license_name, bodies in sorted((c for c in components if c[0] == kind), key=lambda c: c[1].lower()):
            refs = []
            for body in bodies:
                key = hashlib.sha256(body.encode()).hexdigest()
                texts.setdefault(key, body)
                refs.append(str(list(texts).index(key) + 1))
            refs = list(dict.fromkeys(refs))
            lines.append(f"{name} {version}: {license_name}" + (f" [{', '.join(refs)}]" if refs else ""))
        lines.append("")
    lgpl = (ROOT / "packaging" / "licenses" / "LGPL-2.1.txt").read_text(encoding="utf-8").strip()
    lines += ["== GStreamer ==", "", GSTREAMER, "", "== License texts ==", ""]
    for number, body in enumerate(texts.values(), 1):
        lines += [f"---- [{number}] ----", body, ""]
    lines += ["---- GNU Lesser General Public License 2.1 ----", lgpl, ""]
    return "\n".join(lines)


def main() -> int:
    out = Path(sys.argv[1])
    components = [
        *python_components(),
        *npm_components(ROOT / "ui"),
        *rust_components(ROOT / "desktop" / "src-tauri" / "Cargo.toml"),
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(components), encoding="utf-8")
    missing = [f"{c[1]} {c[2]}" for c in components if not c[4]]
    print(f"{len(components)} components written to {out}; {len(missing)} without a license file in their package")
    return 0


if __name__ == "__main__":
    sys.exit(main())
