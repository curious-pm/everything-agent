import { useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { api } from "../api/client";
import { useLive } from "../api/live";
import type { Line, Phase } from "../api/types";
import { Icon } from "../components/Icon";
import { RobotView } from "../robot/RobotView";
import { caption } from "../wording";
import "./Home.css";

const PHASE_LABEL: Record<Phase, string> = {
  asleep: "Asleep",
  idle: "Ready",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
};

export function Home() {
  const { state, lines, notice } = useLive();
  const [drawer, setDrawer] = useState(false);
  const [error, setError] = useState("");
  const captionBox = useRef<HTMLParagraphElement>(null);
  const words = caption(state, lines);
  const lastYou = lines.findLast((l) => l.role === "user");
  const asleep = state.phase === "asleep";
  const speakerLabel = state.speaker_muted ? "Turn Reachy's speaker on" : "Mute Reachy's speaker";
  const micLabel = state.mic_muted ? "Turn Reachy's microphone on" : "Turn Reachy's microphone off";

  useLayoutEffect(() => {
    const el = captionBox.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [words]);

  const run = (action: () => Promise<unknown>) => {
    setError("");
    action().catch((e: Error) => setError(e.message));
  };

  return (
    <main className="home">
      <div className="home-top">
        <span className="muted" />
        <div className="home-actions">
          <button className="btn" aria-expanded={drawer} onClick={() => setDrawer(!drawer)}>
            <Icon name="chat" size={18} />
            Conversation
          </button>
        </div>
      </div>

      <div className="stage">
        <div className="stage-robot">
          <RobotView />
        </div>
        <p className="phase">{PHASE_LABEL[state.phase ?? "idle"]}</p>
        <p className="caption voice" aria-live="polite" ref={captionBox}>{words}</p>
        {lastYou && !asleep && <p className="heard muted">You said: “{lastYou.text}”</p>}
      </div>

      <div className="controls">
        <button
          className="round"
          aria-label={speakerLabel}
          title={speakerLabel}
          onClick={() => run(() => api.mute({ speaker: !state.speaker_muted }))}
        >
          <Icon name={state.speaker_muted ? "speakerOff" : "speaker"} />
        </button>
        <button
          className={`round big${state.mic_muted ? " off" : ""}`}
          aria-label={micLabel}
          title={micLabel}
          onClick={() => run(() => api.mute({ mic: !state.mic_muted }))}
        >
          <Icon name={state.mic_muted ? "micOff" : "mic"} size={28} />
        </button>
        <button className="btn pill" onClick={() => run(asleep ? api.wake : api.sleep)}>
          <Icon name="moon" size={18} />
          {asleep ? "Wake up" : "Put to sleep"}
        </button>
      </div>
      {(error || notice) && <p className="home-error" role="alert">{error || notice}</p>}

      {drawer && <ConversationDrawer lines={lines} onClose={() => setDrawer(false)} />}
    </main>
  );
}

const NEAR_END_PX = 80;

function ConversationDrawer({ lines, onClose }: { lines: Line[]; onClose: () => void }) {
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const list = useRef<HTMLOListElement>(null);
  const followNewest = useRef(true);

  useLayoutEffect(() => {
    const el = list.current;
    if (el && followNewest.current) el.scrollTop = el.scrollHeight;
  }, [lines]);

  const send = async (e: FormEvent) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setSending(true);
    setError("");
    try {
      await api.say(text);
      setDraft("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSending(false);
    }
  };

  const clear = async () => {
    if (!window.confirm("Forget this conversation? Reachy starts afresh.")) return;
    await api.clearConversation().catch((e: Error) => setError(e.message));
  };

  return (
    <aside className="drawer" aria-label="Conversation">
      <div className="drawer-head">
        <h2>Conversation</h2>
        <button className="icon-btn" aria-label="Close the conversation" onClick={onClose}>
          <Icon name="close" size={18} />
        </button>
      </div>
      <ol
        className="lines"
        ref={list}
        onScroll={(e) => {
          const el = e.currentTarget;
          followNewest.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_END_PX;
        }}
      >
        {lines.length === 0 && <li className="muted">Nothing said yet.</li>}
        {lines.map((line, i) => (
          <li key={i}>
            <span className="who">{line.role === "assistant" ? "Reachy" : "You"}</span>
            <span className={line.role === "assistant" ? "voice said" : "said"}>{line.text}</span>
          </li>
        ))}
      </ol>
      <p className="drawer-note muted">
        Saved on this device only.{" "}
        {lines.length > 0 && <button className="link-btn" onClick={clear}>Start over</button>}
      </p>
      <form className="type-box" onSubmit={send}>
        <label htmlFor="draft" className="visually-hidden">Type to Reachy</label>
        <input id="draft" className="field" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Type to Reachy" />
        <button className="btn primary" type="submit" disabled={sending || !draft.trim()}>Send</button>
      </form>
      {error && <p className="home-error" role="alert">{error}</p>}
    </aside>
  );
}
