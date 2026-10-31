export type Phase = "asleep" | "idle" | "listening" | "thinking" | "speaking";

export type LiveState = {
  session?: "starting" | "needs_setup" | "running" | "restarting" | "stopped";
  phase?: Phase;
  asleep?: boolean;
  listening?: boolean;
  in_turn?: boolean;
  mic_muted?: boolean;
  speaker_muted?: boolean;
  missing?: string[];
  problem?: string;
};

export type SessionEvent = { seq: number; at: number; kind: string; [field: string]: unknown };

export type ServerMessage =
  | ({ type: "state" } & LiveState)
  | { type: "levels"; mic: number; speaker: number }
  | ({ type: "event" } & SessionEvent);

export type Line = { role: "user" | "assistant"; text: string };

export type SettingField = {
  key: string;
  label: string;
  kind: "secret" | "text" | "textarea" | "bool" | "choice";
  hint: string;
  required: boolean;
  is_set: boolean;
  value: string;
  default: string;
};

export type DeviceInfo = {
  inputs: string[];
  outputs: string[];
  selected: { input: string; output: string };
  can_choose: boolean;
  error: string;
};

export type Info = { version: string; desktop: boolean; address: string; lan: boolean; pin_set: boolean };

export type Voice = { id: string; name: string; description?: string; language: string; gender: string };

export type Check = { status: "ok" | "warn" | "fail" | "off"; detail: string };
