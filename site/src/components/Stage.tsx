import { useEffect, useRef } from "react";
import { conversation, conversationSummary } from "../content";
import { useConversation } from "../useConversation";
import { Robot } from "./Robot";
import "./Stage.css";

const LABEL = { listening: "Listening", thinking: "Thinking", speaking: "Speaking" };

export function Stage() {
  const { state, play, still } = useConversation(conversation);
  const figure = useRef<HTMLElement>(null);

  useEffect(() => {
    const node = figure.current;
    if (still || !node) return;
    if (typeof IntersectionObserver === "undefined") {
      void play();
      return;
    }
    const watcher = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        watcher.disconnect();
        void play();
      }
    }, { threshold: 0.4 });
    watcher.observe(node);
    return () => watcher.disconnect();
  }, [play, still]);

  return (
    <figure ref={figure} className="stage" data-phase={state.phase} aria-label="A sample conversation with Reachy">
      <Robot />
      <figcaption className="caption">
        <span className="phase" aria-hidden="true">{LABEL[state.phase]}</span>
        <span className="said" aria-hidden="true">{state.heard ? `You said: “${state.heard}”` : ""}</span>
        <span className={`reply voice${state.cut ? " cut" : ""}`} aria-hidden="true">{state.reply}</span>
        <span className="visually-hidden">{conversationSummary}</span>
      </figcaption>
      {state.done && !still && (
        <button className="replay" type="button" onClick={() => void play()}>Play again</button>
      )}
    </figure>
  );
}
