"""Pack the Reachy Mini model and a table of head poses for the web page.

Run with the Python that has reachy_mini installed: python site/scripts/build_robot.py
"""

import json
import re
import struct
from pathlib import Path

import numpy as np
import reachy_mini
from reachy_mini.kinematics import AnalyticalKinematics
from reachy_mini.utils import create_head_pose

OUT = Path(__file__).resolve().parent.parent / "src" / "robot"
URDF_DIR = Path(reachy_mini.__file__).parent / "descriptions" / "reachy_mini" / "urdf"
HIDDEN = ("5w_speaker", "arducam", "pp01102", "bearing", "bts2", "b3b_", "phs_", "dc15_a01_case", "dc15_a01_led")
YAWS = np.arange(-30, 30.1, 7.5)
PITCHES = np.arange(-15, 15.1, 7.5)
ROLLS = np.arange(-10, 10.1, 10)


def read_stl(path: Path) -> np.ndarray:
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    record = np.dtype([("normal", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")])
    return np.frombuffer(data, dtype=record, count=count, offset=84)["v"].reshape(-1, 3)


def pack_meshes(urdf: str) -> tuple[bytes, dict]:
    names = sorted({m for m in re.findall(r'filename="package://assets/([^"]+)"', urdf) if not m.startswith(HIDDEN)})
    blob = bytearray()
    manifest = {}
    for name in names:
        corners = read_stl(URDF_DIR / "assets" / name)
        low, high = corners.min(axis=0), corners.max(axis=0)
        span = np.where(high - low > 0, high - low, 1.0)
        quantized = np.round((corners - low) / span * 65535).astype(np.uint16)
        unique, index = np.unique(quantized, axis=0, return_inverse=True)
        index = index.reshape(-1)
        wide = len(unique) > 65535
        while len(blob) % 4:
            blob.append(0)
        manifest[name] = {
            "offset": len(blob),
            "vertices": len(unique),
            "indices": len(index),
            "wide": wide,
            "min": low.tolist(),
            "span": span.tolist(),
        }
        blob += unique.astype("<u2").tobytes()
        while len(blob) % 4:
            blob.append(0)
        blob += index.astype("<u4" if wide else "<u2").tobytes()
    return bytes(blob), manifest


def pose_table() -> dict:
    kinematics = AnalyticalKinematics(automatic_body_yaw=False)
    entries = []
    for roll in ROLLS:
        for pitch in PITCHES:
            for yaw in YAWS:
                pose = create_head_pose(roll=roll, pitch=pitch, yaw=yaw, degrees=True)
                joints = kinematics.ik(pose, body_yaw=0.0)
                entries.append({
                    "pose": np.round(pose, 6).tolist(),
                    "joints": np.round(joints, 6).tolist(),
                })
    return {"yaws": YAWS.tolist(), "pitches": PITCHES.tolist(), "rolls": ROLLS.tolist(), "entries": entries}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    urdf = (URDF_DIR / "robot_no_collision.urdf").read_text(encoding="utf-8")
    blob, manifest = pack_meshes(urdf)
    (OUT / "robot.urdf").write_text(urdf, encoding="utf-8", newline="\n")
    (OUT / "meshes.bin").write_bytes(blob)
    (OUT / "meshes.json").write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    (OUT / "poses.json").write_text(json.dumps(pose_table(), separators=(",", ":")), encoding="utf-8")
    print(f"{len(manifest)} meshes, {len(blob) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
