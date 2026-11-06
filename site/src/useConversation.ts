import { useCallback, useEffect, useRef, useState } from "react";
import type { Beat, Phase } from "./content";

export type StageState = {
  phase: Phase;
  heard: string;
  reply: string;
  cut: boolean;
  ducking: boolean;
  busy: boolean;
};

const WORD_MS = 150;
const DUCK_MS = 450;
export const TALKED_OVER = "You talked over Reachy, so it stopped to listen.";

function finalState(beats: Beat[]): StageState {
  const lastHeard = [...beats].reverse().find((b) => b.kind === "hear");
  const lastSaid = [...beats].reverse().find((b) => b.kind === "say");
  return {
    phase: "speaking",
    heard: lastHeard?.kind === "hear" ? lastHeard.text : "",
    reply: lastSaid?.kind === "say" ? lastSaid.text : "",
    cut: false,
    ducking: false,
    busy: false,
  };
}

function prefersStill(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

const idle: StageState = { phase: "listening", heard: "", reply: "", cut: false, ducking: false, busy: false };

export function useConversation(intro: Beat[]) {
  const still = prefersStill();
  const [state, setState] = useState<StageState>(() => (still ? finalState(intro) : idle));
  const run = useRef(0);

  const wait = useCallback((id: number, ms: number) =>
    new Promise<boolean>((resolve) => {
      const tick = () => {
        if (document.hidden) {
          setTimeout(tick, 250);
          return;
        }
        resolve(run.current === id);
      };
      setTimeout(tick, ms);
    }), []);

  const play = useCallback(async (beats: Beat[]) => {
    const id = ++run.current;
    if (still) {
      setState(finalState(beats));
      return;
    }
    setState({ ...idle, busy: true });
    for (const beat of beats) {
      if (beat.kind === "rest") {
        if (!(await wait(id, beat.pause))) return;
      } else if (beat.kind === "hear") {
        setState((s) => ({ ...s, phase: "listening", heard: beat.text, cut: s.reply !== "" }));
        if (!(await wait(id, beat.pause))) return;
      } else if (beat.kind === "think") {
        setState((s) => ({ ...s, phase: "thinking" }));
        if (!(await wait(id, beat.pause))) return;
      } else {
        const words = beat.text.split(" ");
        const count = beat.stopAfterWords ?? words.length;
        for (let i = 1; i <= count; i += 1) {
          const shown = words.slice(0, i).join(" ") + (i === count && count < words.length ? "…" : "");
          setState((s) => ({ ...s, phase: "speaking", reply: shown, cut: false }));
          if (!(await wait(id, WORD_MS))) return;
        }
      }
    }
    setState((s) => ({ ...s, phase: "listening", busy: false }));
  }, [still, wait]);

  const interrupt = useCallback(async () => {
    const id = ++run.current;
    setState((s) => ({ ...s, ducking: true }));
    if (!(await wait(id, DUCK_MS))) return;
    setState((s) => ({
      ...s,
      phase: "listening",
      heard: TALKED_OVER,
      reply: s.reply.endsWith("…") ? s.reply : `${s.reply}…`,
      cut: true,
      ducking: false,
      busy: false,
    }));
  }, [wait]);

  useEffect(() => () => {
    run.current += 1;
  }, []);

  return { state, play, interrupt, still };
}
