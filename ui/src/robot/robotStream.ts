import { daemonWsUrl } from "../host";

export type RobotFrame = { headPose: number[][]; headJoints: number[]; antennas: number[] };

const STATE_PATH =
  "/api/state/ws/full?frequency=30&with_head_joints=true&with_head_pose=true&use_pose_matrix=true" +
  "&with_antenna_positions=true&with_body_yaw=true&with_control_mode=false";
const RETRY_MS = 1500;

function poseRows(pose: unknown): number[][] | null {
  const m = pose && typeof pose === "object" && "m" in pose ? pose.m : pose;
  if (!Array.isArray(m)) return null;
  if (Array.isArray(m[0])) return m;
  if (m.length === 16) return [m.slice(0, 4), m.slice(4, 8), m.slice(8, 12), m.slice(12, 16)];
  return null;
}

export function parseFrame(raw: string): RobotFrame | null {
  let msg;
  try {
    msg = JSON.parse(raw);
  } catch {
    return null;
  }
  const headPose = poseRows(msg.head_pose);
  if (!headPose || !Array.isArray(msg.head_joints)) return null;
  return { headPose, headJoints: msg.head_joints, antennas: msg.antennas_position ?? [0, 0] };
}

export function streamRobot(onFrame: (frame: RobotFrame) => void, onOpenChange: (open: boolean) => void): () => void {
  let ws: WebSocket | null = null;
  let retry: number | undefined;
  let stopped = false;

  const open = () => {
    ws = new WebSocket(daemonWsUrl(STATE_PATH));
    ws.onopen = () => onOpenChange(true);
    ws.onmessage = (ev) => {
      const frame = parseFrame(ev.data);
      if (frame) onFrame(frame);
    };
    ws.onclose = () => {
      onOpenChange(false);
      if (!stopped) retry = window.setTimeout(open, RETRY_MS);
    };
  };
  open();

  return () => {
    stopped = true;
    window.clearTimeout(retry);
    if (ws) {
      ws.onclose = null;
      ws.close();
    }
  };
}
