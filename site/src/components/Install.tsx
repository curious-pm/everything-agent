import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { keys, RELEASES, REPO } from "../content";
import { detectPlatform, installerFor, useLatestRelease } from "../useRelease";
import "./Install.css";

function Installers() {
  const release = useLatestRelease();
  const mine = detectPlatform(navigator.userAgent);
  const installers = (["windows", "mac"] as const).map((platform) => installerFor(platform, release));
  const ready = installers.some((installer) => installer.direct);
  return (
    <div className="installers">
      <div className="actions">
        {installers.map((installer) => (
          <a
            key={installer.platform}
            className={`btn download${installer.platform === mine ? " primary" : ""}`}
            href={installer.href}
          >
            <span>{installer.label}</span>
            <small>{installer.detail}</small>
          </a>
        ))}
      </div>
      {!ready && (
        <p className="fine">
          The first release isn't published yet, so these open the <a href={RELEASES}>Releases</a> page for now.
          Once it is, they download the installer directly.
        </p>
      )}
    </div>
  );
}

function Command({ text }: { text: string }) {
  const [label, setLabel] = useState("Copy");
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setLabel("Copied");
    } catch {
      setLabel("Select and copy");
    }
    setTimeout(() => setLabel("Copy"), 1800);
  };
  return (
    <div className="cmd">
      <code>{text}</code>
      <button className="copy" type="button" onClick={() => void copy()} aria-label={`Copy: ${text}`}>
        {label}
      </button>
    </div>
  );
}

type Tab = { id: string; label: string; body: ReactNode };

const tabs: Tab[] = [
  {
    id: "robot",
    label: "On Reachy Mini",
    body: (
      <>
        <ol className="steps">
          <li>
            In a terminal on the robot, install the app:
            <Command text={`pip install git+${REPO}`} />
          </li>
          <li>
            Start it from the robot's dashboard, then open <code>http://reachy-mini.local:8042</code> on your
            phone or laptop.
          </li>
          <li>Choose a PIN, then add your keys. Do this yourself right after installing: the first visitor sets the PIN.</li>
        </ol>
        <p className="fine">Reachy uses its own microphone, with hardware echo cancelling, and its own speaker.</p>
      </>
    ),
  },
  {
    id: "desktop",
    label: "Windows and macOS",
    body: (
      <ol className="steps">
        <li>
          Download the installer:
          <Installers />
        </li>
        <li>
          The installers aren't code-signed yet. On Windows choose <em>More info</em>, then <em>Run anyway</em>;
          on macOS right-click the app and choose <em>Open</em> the first time.
        </li>
        <li>
          It starts the robot software for you. With Reachy plugged in over USB it uses the robot; without one,
          your computer's microphone and speaker.
        </li>
      </ol>
    ),
  },
  {
    id: "source",
    label: "From source",
    body: (
      <ol className="steps">
        <li>
          Clone and install:
          <Command text={`git clone ${REPO} && cd Everything-Agent && uv sync --extra dev`} />
        </li>
        <li>
          Start the robot software, or the simulator if you have no robot:
          <Command text="uv run reachy-mini-daemon --mockup-sim" />
        </li>
        <li>
          In another terminal, start the app, then open <code>http://127.0.0.1:8042</code>:
          <Command text="uv run python -m everything_agent" />
        </li>
      </ol>
    ),
  },
];

export function Install() {
  const [active, setActive] = useState(tabs[0].id);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const section = useRef<HTMLElement>(null);

  useEffect(() => {
    const openFromHash = () => {
      const tab = tabs.find((t) => `#${t.id}` === window.location.hash);
      if (!tab) return;
      setActive(tab.id);
      section.current?.scrollIntoView({ block: "start" });
    };
    openFromHash();
    window.addEventListener("hashchange", openFromHash);
    return () => window.removeEventListener("hashchange", openFromHash);
  }, []);

  const onKey = (event: KeyboardEvent, index: number) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    const next = (index + step + tabs.length) % tabs.length;
    setActive(tabs[next].id);
    buttons.current[next]?.focus();
  };

  return (
    <section ref={section} className="install" id="install" aria-labelledby="install-title">
      <h2 id="install-title">Install</h2>
      <div className="tabs" role="tablist" aria-label="Where to run it">
        {tabs.map((tab, index) => (
          <button
            key={tab.id}
            ref={(node) => {
              buttons.current[index] = node;
            }}
            role="tab"
            id={`tab-${tab.id}`}
            aria-controls={`pane-${tab.id}`}
            aria-selected={active === tab.id}
            tabIndex={active === tab.id ? 0 : -1}
            onClick={() => setActive(tab.id)}
            onKeyDown={(event) => onKey(event, index)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {tabs.map((tab) => (
        <div
          key={tab.id}
          className="pane"
          role="tabpanel"
          id={`pane-${tab.id}`}
          aria-labelledby={`tab-${tab.id}`}
          hidden={active !== tab.id}
        >
          {tab.body}
        </div>
      ))}

      <h3 className="need-title">You'll need two keys</h3>
      <table className="need">
        <thead>
          <tr>
            <th scope="col">For</th>
            <th scope="col">Service</th>
            <th scope="col">Get one</th>
          </tr>
        </thead>
        <tbody>
          {keys.map((key) => (
            <tr key={key.what}>
              <td>{key.what}</td>
              <td>{key.service}</td>
              <td><a href={key.link}>{key.label}</a></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
