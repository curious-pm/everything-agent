import { useEffect, useRef } from "react";
import { beatsFor, conversation, conversationSummary, questions } from "../content";
import { TALKED_OVER, useConversation } from "../useConversation";
import { Robot3D } from "./Robot3D";
import "./Stage.css";

const LABEL = { listening: "Listening", thinking: "Thinking", speaking: "Speaking" };

export function Stage() {
  const { state, play, interrupt, still } = useConversation(conversation);
  const figure = useRef<HTMLElement>(null);

  useEffect(() => {
    const node = figure.current;
    if (still || !node) return;
    if (typeof IntersectionObserver === "undefined") {
      void play(conversation);
      return;
    }
    const watcher = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        watcher.disconnect();
        void play(conversation);
      }
    }, { threshold: 0.4 });
    watcher.observe(node);
    return () => watcher.disconnect();
  }, [play, still]);

  const said = state.heard === TALKED_OVER ? state.heard : state.heard ? `You said: “${state.heard}”` : "";
  const canInterrupt = state.phase === "speaking" && state.busy && !state.ducking;

  return (
    <figure ref={figure} className="stage" data-phase={state.phase} aria-label="A sample conversation with Reachy">
      <Robot3D phase={state.phase} still={still} />
      <figcaption className="caption">
        <span className="phase" aria-hidden="true">{LABEL[state.phase]}</span>
        <span className="said" aria-hidden="true">{said}</span>
        <span className={`reply voice${state.cut ? " cut" : ""}${state.ducking ? " ducking" : ""}`} aria-hidden="true">
          {state.reply}
        </span>
        <span className="visually-hidden">{conversationSummary}</span>
      </figcaption>
      <div className="try">
        {canInterrupt ? (
          <button className="talk-over" type="button" onClick={() => void interrupt()}>
            Talk over Reachy
          </button>
        ) : (
          <>
            <span className="try-label">Ask Reachy</span>
            <div className="chips">
              {questions.map((question) => (
                <button
                  key={question.ask}
                  type="button"
                  className="chip"
                  disabled={state.busy}
                  onClick={() => void play(beatsFor(question))}
                >
                  {question.ask}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </figure>
  );
}
