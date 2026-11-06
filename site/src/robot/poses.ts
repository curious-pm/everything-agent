import table from "./poses.json";

export type Look = { yaw: number; pitch: number; roll: number };
export type Posture = { headPose: number[][]; headJoints: number[] };

type Entry = { pose: number[][]; joints: number[] };

const entries = table.entries as Entry[];

function bracket(axis: number[], value: number): [number, number, number] {
  const v = Math.min(axis[axis.length - 1], Math.max(axis[0], value));
  let i = 0;
  while (i < axis.length - 2 && v > axis[i + 1]) i += 1;
  const span = axis[i + 1] - axis[i];
  return [i, i + 1, span ? (v - axis[i]) / span : 0];
}

export function clampLook(look: Look): Look {
  const clamp = (axis: number[], v: number) => Math.min(axis[axis.length - 1], Math.max(axis[0], v));
  return { yaw: clamp(table.yaws, look.yaw), pitch: clamp(table.pitches, look.pitch), roll: clamp(table.rolls, look.roll) };
}

export function postureFor(look: Look): Posture {
  const [y0, y1, ty] = bracket(table.yaws, look.yaw);
  const [p0, p1, tp] = bracket(table.pitches, look.pitch);
  const [r0, r1, tr] = bracket(table.rolls, look.roll);
  const at = (r: number, p: number, y: number) => entries[(r * table.pitches.length + p) * table.yaws.length + y];

  const headPose = [0, 1, 2, 3].map(() => [0, 0, 0, 0]);
  const headJoints = [0, 0, 0, 0, 0, 0, 0];
  for (const [r, wr] of [[r0, 1 - tr], [r1, tr]]) {
    for (const [p, wp] of [[p0, 1 - tp], [p1, tp]]) {
      for (const [y, wy] of [[y0, 1 - ty], [y1, ty]]) {
        const w = wr * wp * wy;
        if (!w) continue;
        const entry = at(r, p, y);
        for (let i = 0; i < 4; i += 1) for (let j = 0; j < 4; j += 1) headPose[i][j] += entry.pose[i][j] * w;
        for (let k = 0; k < 7; k += 1) headJoints[k] += entry.joints[k] * w;
      }
    }
  }
  return { headPose, headJoints };
}
