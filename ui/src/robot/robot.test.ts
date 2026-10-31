import { describe, expect, it } from "vitest";
import { partFor } from "./materials";
import { parseFrame } from "./robotStream";

describe("daemon state frames", () => {
  const joints = [0, 0.7, -0.7, 0.7, -0.7, 0.7, -0.7];
  const flat = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, -0.005, 0, 0, 0, 1];

  it("accepts the flat 16-number pose the daemon sends", () => {
    const frame = parseFrame(JSON.stringify({ head_pose: { m: flat }, head_joints: joints, antennas_position: [-0.17, 0.17] }));
    expect(frame?.headPose[2][3]).toBe(-0.005);
    expect(frame?.antennas).toEqual([-0.17, 0.17]);
  });

  it("accepts a 4x4 pose too", () => {
    const rows = [flat.slice(0, 4), flat.slice(4, 8), flat.slice(8, 12), flat.slice(12)];
    expect(parseFrame(JSON.stringify({ head_pose: rows, head_joints: joints }))?.headPose).toEqual(rows);
  });

  it("skips frames without a pose", () => {
    expect(parseFrame(JSON.stringify({ head_pose: null, head_joints: joints }))).toBeNull();
  });
});

describe("robot materials", () => {
  it("lights the eyes, darkens the mechanics, keeps the shell white", () => {
    expect(partFor("./robot/assets/big_lens_d40.stl")).toBe("eye");
    expect(partFor("./robot/assets/antenna.stl")).toBe("dark");
    expect(partFor("./robot/assets/antenna_body_3dprint.stl")).toBe("shell");
    expect(partFor("./robot/assets/head_front_3dprint.stl")).toBe("shell");
  });
});
