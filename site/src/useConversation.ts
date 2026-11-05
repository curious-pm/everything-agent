import { useCallback, useEffect, useRef, useState } from "react";
import type { Beat, Phase } from "./content";

export type StageState = { phase: Phase; heard: string; reply: string; cut: boolean; done: boolean };

const WORD_MS = 150;

function finalState(beats: Beat[]): StageState {
  const lastHeard = [...beats].reverse().find((b) => b.kind === "hear");
  const lastSaid = [...beats].reverse().find((b) => b.kind === "say");
  return {
    phase: "speaking",
    heard: lastHeard?.kind === "hear" ? lastHeard.text : "",
    reply: lastSaid?.kind === "say" ? lastSaid.text : "",
    cut: false,
    done: true,
  };
}

function prefersStill(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function useConversation(beats: Beat[]) {
  const still = prefersStill();
  const [state, setState] = useState<StageState>(() =>
    still ? finalState(beats) : { phase: "listening", heard: "", reply: "", cut: false, done: false },
  );
  const run = useRef(0);

  const play = useCallback(async () => {
    const id = ++run.current;
    const wait = (ms: number) =>
      new Promise<boolean>((resolve) => {
        const tick = () => {
          if (document.hidden) {
            setTimeout(tick, 250);
            return;
          }
          resolve(run.current === id);
        };
        setTimeout(tick, ms);
      });

    setState({ phase: "listening", heard: "", reply: "", cut: false, done: false });
    for (const beat of beats) {
      if (beat.kind === "rest") {
        if (!(await wait(beat.pause))) return;
      } else if (beat.kind === "hear") {
        setState((s) => ({ ...s, phase: "listening", heard: beat.text, cut: s.reply !== "" }));
        if (!(await wait(beat.pause))) return;
      } else if (beat.kind === "think") {
        setState((s) => ({ ...s, phase: "thinking" }));
        if (!(await wait(beat.pause))) return;
      } else {
        const words = beat.text.split(" ");
        const count = beat.stopAfterWords ?? words.length;
        for (let i = 1; i <= count; i += 1) {
          const shown = words.slice(0, i).join(" ") + (i === count && count < words.length ? "…" : "");
          setState((s) => ({ ...s, phase: "speaking", reply: shown, cut: false }));
          if (!(await wait(WORD_MS))) return;
        }
      }
    }
    setState((s) => ({ ...s, phase: "listening", done: true }));
  }, [beats]);

  useEffect(() => () => {
    run.current += 1;
  }, []);

  return { state, play, still };
}
