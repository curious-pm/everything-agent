import { useEffect, useState, type FormEvent } from "react";
import { api, MIN_PIN_LENGTH } from "./api/client";
import { useLive } from "./api/live";
import { Rail } from "./components/Rail";
import { ReachyMark } from "./components/ReachyMark";
import { isTauri, useCore, type CoreState } from "./host";
import { useNav } from "./nav";
import { Home } from "./screens/Home";
import { Settings } from "./screens/Settings";
import { Setup } from "./screens/Setup";
import "./App.css";

const SCREEN_COMPONENTS = { home: Home, settings: Settings };

export default function App() {
  const connection = useLive((s) => s.connection);
  const state = useLive((s) => s.state);
  const connect = useLive((s) => s.connect);
  const screen = useNav((s) => s.screen);
  const core = useCore((s) => s.core);
  const waitingForCore = isTauri() && core?.state !== "RUNNING";

  useEffect(() => {
    if (!waitingForCore) connect();
  }, [waitingForCore, connect]);

  useEffect(() => () => useLive.getState().disconnect(), []);

  useEffect(() => {
    document.documentElement.dataset.phase = state.phase ?? "idle";
  }, [state.phase]);

  if (waitingForCore) return <CoreWaiting core={core} />;
  if (connection === "login") return <SignIn onDone={connect} />;
  if (connection !== "live") {
    return (
      <div className="waiting" role="status">
        <ReachyMark size={56} />
        <p className="voice">{connection === "offline" ? "I lost touch for a moment. Reconnecting…" : "Waking up…"}</p>
      </div>
    );
  }
  if (state.session === "needs_setup") return <Setup />;

  const Screen = SCREEN_COMPONENTS[screen];
  return (
    <div className="frame">
      <Rail />
      <Screen />
    </div>
  );
}

const CORE_WORDS: Record<string, string> = {
  STARTING: "Waking up…",
  RESTARTING: "Something went wrong, so I'm starting again…",
  ROBOT_NOT_FOUND: "I can't find my robot body.",
  DAEMON_CONFLICT: "Another Reachy app is using my body.",
  NO_CORE: "Part of me is missing.",
  STOPPING: "Going to sleep…",
  STOPPED: "Asleep.",
};

function CoreWaiting({ core }: { core: CoreState | null }) {
  return (
    <div className="waiting" role="status" aria-live="polite">
      <ReachyMark size={56} />
      <p className="voice">{(core && CORE_WORDS[core.state]) || "Waking up…"}</p>
      {core?.detail && <p className="waiting-detail">{core.detail}</p>}
    </div>
  );
}

export function SignIn({ onDone }: { onDone: () => void }) {
  const [pinSet, setPinSet] = useState<boolean | null>(null);
  const [pin, setPin] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.auth().then((a) => (a.signed_in ? onDone() : setPinSet(a.pin_set)), (e: Error) => setError(e.message));
  }, [onDone]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (pinSet === false && pin !== again) {
      setError("The two PINs don't match.");
      return;
    }
    setBusy(true);
    try {
      await (pinSet ? api.login(pin) : api.setPin(pin));
      onDone();
    } catch (err) {
      setError((err as Error).message);
      setPin("");
      setAgain("");
    } finally {
      setBusy(false);
    }
  };

  if (pinSet === null) {
    return (
      <div className="waiting" role="status">
        <ReachyMark size={56} />
        {error ? <p className="page-error" role="alert">{error}</p> : <p className="voice">Waking up…</p>}
      </div>
    );
  }
  return (
    <form className="waiting login" onSubmit={submit}>
      <ReachyMark size={56} />
      <p className="voice">{pinSet ? "Hi! Enter the PIN to open Reachy." : "Hi! Choose a PIN to keep this page yours."}</p>
      <label htmlFor="pin" className="visually-hidden">PIN</label>
      <input
        id="pin" className="field" type="password" inputMode="numeric" placeholder="PIN" value={pin}
        autoComplete={pinSet ? "current-password" : "new-password"} onChange={(e) => setPin(e.target.value)} autoFocus
      />
      {!pinSet && (
        <>
          <label htmlFor="pin-again" className="visually-hidden">PIN again</label>
          <input
            id="pin-again" className="field" type="password" inputMode="numeric" placeholder="PIN again" value={again}
            autoComplete="new-password" onChange={(e) => setAgain(e.target.value)}
          />
        </>
      )}
      <button className="btn primary" type="submit" disabled={busy || pin.length < (pinSet ? 1 : MIN_PIN_LENGTH)}>
        {pinSet ? "Open Reachy" : "Set PIN"}
      </button>
      {error && <p className="page-error" role="alert">{error}</p>}
      <p className="waiting-detail">
        {pinSet ? "Forgot it? Remove WEB_PIN_HASH from Reachy's settings file and restart." : `At least ${MIN_PIN_LENGTH} characters. Anyone on your network who has it can talk to Reachy.`}
      </p>
    </form>
  );
}
