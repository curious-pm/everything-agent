import type { Line, LiveState } from "./api/types";

export function caption(state: LiveState, lines: Line[]): string {
  if (state.phase === "asleep") return "I'm asleep. Wake me up when you want to talk.";
  if (state.mic_muted) return "I can't hear you right now.";
  switch (state.phase) {
    case "speaking":
      return lines.findLast((l) => l.role === "assistant")?.text ?? "";
    case "thinking":
      return "Let me think…";
    case "listening":
      return "I'm listening.";
    default:
      return "Say hello when you're ready.";
  }
}
