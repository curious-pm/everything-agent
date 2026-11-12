import type { Line, LiveState } from "./api/types";

export function caption(state: LiveState, lines: Line[], saying = ""): string {
  if (state.phase === "asleep") return "I'm asleep. Wake me up when you want to talk.";
  if (state.mic_muted) return "I can't hear you right now.";
  switch (state.phase) {
    case "speaking":
      return saying || (lines.at(-1)?.role === "assistant" ? lines.at(-1)!.text : "");
    case "thinking":
      return "Let me think…";
    case "listening":
      return "I'm listening.";
    default:
      return "Say hello when you're ready.";
  }
}
